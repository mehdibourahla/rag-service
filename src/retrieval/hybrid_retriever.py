"""Hybrid retrieval combining dense and sparse search with LLM-based reranking."""

import logging
from typing import List

from openai import OpenAI
from pydantic import BaseModel, Field

from src.core.config import settings
from src.ingestion.embedder import Embedder
from src.models.schemas import RetrievedChunk
from src.retrieval.bm25_index import BM25Index
from src.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RelevanceScore(BaseModel):
    """Structured output for LLM-based relevance scoring."""

    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0, where 1.0 is most relevant",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(description="Brief explanation of why this score was assigned")


class HybridRetriever:
    """Hybrid retrieval using dense + BM25 + LLM-based reranking."""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        embedder: Embedder,
        use_llm_reranking: bool = True,
    ):
        """
        Initialize hybrid retriever.

        Args:
            vector_store: Qdrant vector store
            bm25_index: BM25 index
            embedder: Embedding generator
            use_llm_reranking: Whether to use LLM-based reranking
        """
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedder = embedder
        self.use_llm_reranking = use_llm_reranking
        self._client = None

    def _get_client(self) -> OpenAI:
        """Lazy load OpenAI client for reranking."""
        if self._client is None:
            logger.info("Initializing OpenAI client for reranking")
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[dict],
        sparse_results: List[dict],
        k: int = 60,
    ) -> List[dict]:
        """
        Combine results using Reciprocal Rank Fusion.

        Args:
            dense_results: Results from vector search
            sparse_results: Results from BM25
            k: RRF constant (default 60)

        Returns:
            Fused results with combined scores
        """
        # Build score map
        score_map = {}

        # Add dense results
        for rank, result in enumerate(dense_results):
            chunk_id = result["metadata"].get("chunk_id", result["text"])
            score_map[chunk_id] = {
                "rrf_score": 1.0 / (k + rank + 1),
                "result": result,
            }

        # Add sparse results (accumulate scores)
        for rank, result in enumerate(sparse_results):
            chunk_id = result["metadata"].get("chunk_id", result["text"])
            rrf_score = 1.0 / (k + rank + 1)

            if chunk_id in score_map:
                score_map[chunk_id]["rrf_score"] += rrf_score
            else:
                score_map[chunk_id] = {
                    "rrf_score": rrf_score,
                    "result": result,
                }

        # Sort by RRF score
        fused_results = sorted(
            score_map.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        # Extract results with RRF scores
        output = []
        for item in fused_results:
            result = item["result"].copy()
            result["rrf_score"] = item["rrf_score"]
            output.append(result)

        return output

    def _rerank_with_llm(self, query: str, candidates: List[dict]) -> List[dict]:
        """
        Rerank candidates using LLM-based relevance scoring.

        Args:
            query: User query
            candidates: Candidate results to rerank

        Returns:
            Reranked results with LLM scores
        """
        client = self._get_client()

        logger.info(f"Reranking {len(candidates)} candidates with LLM")

        reranked = []
        for candidate in candidates:
            try:
                # Ask LLM to score relevance
                completion = client.beta.chat.completions.parse(
                    model=settings.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a relevance scoring system. Given a query and a text passage, score how relevant the passage is to answering the query.",
                        },
                        {
                            "role": "user",
                            "content": f"Query: {query}\n\nPassage: {candidate['text']}\n\nScore the relevance of this passage to the query.",
                        },
                    ],
                    response_format=RelevanceScore,
                    max_tokens=150,
                    temperature=0.0,
                )

                score_result = completion.choices[0].message.parsed
                candidate["llm_score"] = score_result.relevance_score
                candidate["llm_reasoning"] = score_result.reasoning
                reranked.append(candidate)

            except Exception as e:
                logger.warning(f"Failed to score candidate with LLM: {e}")
                # Keep candidate with original score
                candidate["llm_score"] = candidate.get("rrf_score", 0.5)
                candidate["llm_reasoning"] = "LLM scoring failed"
                reranked.append(candidate)

        # Sort by LLM score
        reranked.sort(key=lambda x: x["llm_score"], reverse=True)

        return reranked

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        use_reranker: bool = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks using hybrid search.

        Args:
            query: Query text
            top_k: Number of final results (defaults to config final_top_k)
            use_reranker: Whether to use reranker (defaults to instance setting)

        Returns:
            List of retrieved chunks with scores
        """
        top_k = top_k or settings.final_top_k
        retrieval_k = settings.retrieval_top_k
        use_reranker = use_reranker if use_reranker is not None else self.use_llm_reranking

        logger.info(f"Retrieving for query: '{query[:50]}...' (top_k={top_k})")

        # 1. Dense retrieval
        query_embedding = self.embedder.embed_query(query)
        dense_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=retrieval_k,
        )

        # 2. Sparse retrieval
        sparse_results = self.bm25_index.search(query=query, top_k=retrieval_k)

        # 3. Reciprocal rank fusion
        fused_results = self._reciprocal_rank_fusion(dense_results, sparse_results)

        # Take top candidates for reranking
        candidates = fused_results[:min(len(fused_results), retrieval_k)]

        # 4. LLM-based reranking (optional)
        if use_reranker and candidates and len(candidates) > 1:
            reranked = self._rerank_with_llm(query, candidates)
            final_results = reranked[:top_k]
            score_key = "llm_score"
        else:
            # Use RRF scores
            final_results = candidates[:top_k]
            score_key = "rrf_score"

        # Convert to RetrievedChunk objects
        retrieved_chunks = []
        for result in final_results:
            from uuid import UUID

            from src.models.schemas import ChunkMetadata

            metadata = ChunkMetadata(
                chunk_id=UUID(result["metadata"]["chunk_id"]),
                document_id=UUID(result["metadata"]["document_id"]),
                source=result["metadata"]["source"],
                modality=result["metadata"]["modality"],
                chunk_index=result["metadata"]["chunk_index"],
                section_title=result["metadata"].get("section_title"),
                page_number=result["metadata"].get("page_number"),
            )

            retrieved_chunks.append(
                RetrievedChunk(
                    text=result["text"],
                    score=result[score_key],
                    metadata=metadata,
                )
            )

        logger.info(f"Retrieved {len(retrieved_chunks)} final chunks")
        return retrieved_chunks
