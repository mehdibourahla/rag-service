"""RAG generation using OpenAI GPT-4o-mini with structured outputs."""

import logging
from typing import List

from openai import OpenAI
from pydantic import BaseModel, Field

from src.core.config import settings
from src.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class RAGAnswer(BaseModel):
    """Structured output for RAG answers."""

    answer: str = Field(description="The answer to the user's question based on the provided context")
    sources_used: List[int] = Field(
        description="List of source indices (1-indexed) that were used to generate the answer"
    )
    confidence: str = Field(
        description="Confidence level: 'high', 'medium', or 'low' based on context relevance"
    )


class Generator:
    """Generates answers using OpenAI GPT-4o-mini with structured outputs."""

    def __init__(self, model_name: str = None):
        """
        Initialize generator.

        Args:
            model_name: OpenAI model name (defaults to config)
        """
        self.model_name = model_name or settings.llm_model
        self._client = None

    def _get_client(self) -> OpenAI:
        """Lazy load the OpenAI client."""
        if self._client is None:
            logger.info(f"Initializing OpenAI client with model: {self.model_name}")
            self._client = OpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI client initialized successfully")
        return self._client

    def _build_prompt(self, query: str, chunks: List[RetrievedChunk]) -> str:
        """
        Build RAG prompt from query and retrieved chunks.

        Args:
            query: User query
            chunks: Retrieved context chunks

        Returns:
            Formatted prompt
        """
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.metadata.source.split("/")[-1]
            context_parts.append(
                f"[{i}] Source: {source} (modality: {chunk.metadata.modality})\n{chunk.text}\n"
            )

        context = "\n".join(context_parts)

        # System message and user prompt
        system_message = """You are a helpful AI assistant that answers questions based on provided context.
Always cite your sources using the source numbers [1], [2], etc.
If the context doesn't contain relevant information, state that clearly.
Provide accurate, concise answers based on the evidence in the context."""

        user_prompt = f"""Context:
{context}

Question: {query}

Please answer the question based on the provided context. Indicate which sources you used and your confidence level."""

        return system_message, user_prompt

    def generate(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        """
        Generate answer using retrieved chunks with structured output.

        Args:
            query: User query
            chunks: Retrieved context chunks
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Generated answer
        """
        client = self._get_client()

        # Build prompt
        system_message, user_prompt = self._build_prompt(query, chunks)

        logger.info(f"Generating answer for query: '{query[:50]}...' using {self.model_name}")

        # Generate with structured output
        try:
            completion = client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=RAGAnswer,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Extract structured response
            rag_answer = completion.choices[0].message.parsed

            # Format the answer with metadata
            answer_parts = [rag_answer.answer]

            if rag_answer.sources_used:
                sources_str = ", ".join([f"[{i}]" for i in rag_answer.sources_used])
                answer_parts.append(f"\n\nSources: {sources_str}")

            answer_parts.append(f"\nConfidence: {rag_answer.confidence}")

            final_answer = "".join(answer_parts)

            logger.info(
                f"Generated answer: {len(final_answer)} chars "
                f"(confidence: {rag_answer.confidence}, "
                f"sources: {len(rag_answer.sources_used)})"
            )

            return final_answer

        except Exception as e:
            logger.error(f"Error generating answer with structured output: {e}")
            # Fallback to regular completion if structured output fails
            logger.info("Falling back to regular completion")
            return self._generate_fallback(client, system_message, user_prompt, max_tokens, temperature)

    def _generate_fallback(
        self,
        client: OpenAI,
        system_message: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Fallback to regular completion if structured output fails.

        Args:
            client: OpenAI client
            system_message: System message
            user_prompt: User prompt
            max_tokens: Maximum tokens
            temperature: Temperature

        Returns:
            Generated answer
        """
        completion = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        answer = completion.choices[0].message.content.strip()
        logger.info(f"Generated fallback answer: {len(answer)} chars")
        return answer
