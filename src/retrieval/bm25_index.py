"""BM25 sparse retrieval index."""

import json
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from rank_bm25 import BM25Okapi

from src.core.config import settings
from src.models.schemas import TextChunk

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25 index for sparse retrieval."""

    def __init__(self, index_path: Path = None, tenant_id: Optional[UUID] = None):
        """
        Initialize BM25 index.

        Args:
            index_path: Path to save/load index (defaults to chunks_dir)
            tenant_id: Tenant ID for multi-tenant indexing (optional)
        """
        self.tenant_id = tenant_id

        # Use tenant-specific path if tenant_id is provided
        if tenant_id:
            self.index_path = index_path or settings.chunks_dir / f"bm25_index_{tenant_id}.json"
        else:
            self.index_path = index_path or settings.chunks_dir / "bm25_index.json"

        self.corpus: List[str] = []
        self.metadata: List[dict] = []
        self.bm25: Optional[BM25Okapi] = None
        self._load_index()

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace tokenization."""
        return text.lower().split()

    def _load_index(self):
        """Load index from disk if it exists."""
        if self.index_path.exists():
            logger.info(f"Loading BM25 index from {self.index_path}")
            with open(self.index_path, "r") as f:
                data = json.load(f)
                self.corpus = data["corpus"]
                self.metadata = data["metadata"]

            if self.corpus:
                tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
                self.bm25 = BM25Okapi(tokenized_corpus)
                logger.info(f"Loaded BM25 index with {len(self.corpus)} documents")
        else:
            logger.info("No existing BM25 index found, starting fresh")

    def _save_index(self):
        """Save index to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w") as f:
            json.dump({"corpus": self.corpus, "metadata": self.metadata}, f)
        logger.info(f"Saved BM25 index to {self.index_path}")

    def add_chunks(self, chunks: List[TextChunk], tenant_id: Optional[UUID] = None) -> int:
        """
        Add chunks to BM25 index.

        Args:
            chunks: List of TextChunk objects
            tenant_id: Tenant ID for validation (optional)

        Returns:
            Number of chunks added

        Raises:
            ValueError: If tenant_id mismatch
        """
        if not chunks:
            return 0

        # Validate tenant_id if this is a tenant-specific index
        if self.tenant_id and tenant_id and self.tenant_id != tenant_id:
            raise ValueError(f"Tenant ID mismatch: index={self.tenant_id}, chunks={tenant_id}")

        for chunk in chunks:
            self.corpus.append(chunk.text)
            metadata_dict = {
                "chunk_id": str(chunk.metadata.chunk_id),
                "document_id": str(chunk.metadata.document_id),
                "source": chunk.metadata.source,
                "modality": chunk.metadata.modality.value,
                "section_title": chunk.metadata.section_title,
                "page_number": chunk.metadata.page_number,
            }

            # Add tenant_id to metadata if provided
            if tenant_id or self.tenant_id:
                metadata_dict["tenant_id"] = str(tenant_id or self.tenant_id)

            self.metadata.append(metadata_dict)

        # Rebuild BM25 index
        tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # Save to disk
        self._save_index()

        logger.info(f"Added {len(chunks)} chunks to BM25 index")
        return len(chunks)

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """
        Search using BM25.

        Args:
            query: Query text
            top_k: Number of results to return

        Returns:
            List of search results with text, metadata, and scores
        """
        if not self.bm25 or not self.corpus:
            logger.warning("BM25 index is empty")
            return []

        logger.info(f"Searching BM25 index (top_k={top_k})")

        # Tokenize query and get scores
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        # Format results
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include non-zero scores
                results.append(
                    {
                        "text": self.corpus[idx],
                        "score": float(scores[idx]),
                        "metadata": self.metadata[idx],
                    }
                )

        logger.info(f"Found {len(results)} BM25 results")
        return results

    def delete_by_document(self, document_id: UUID) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            Number of chunks deleted
        """
        doc_id_str = str(document_id)
        indices_to_remove = [
            i for i, meta in enumerate(self.metadata) if meta["document_id"] == doc_id_str
        ]

        if not indices_to_remove:
            return 0

        # Remove in reverse order to maintain indices
        for idx in sorted(indices_to_remove, reverse=True):
            del self.corpus[idx]
            del self.metadata[idx]

        # Rebuild index
        if self.corpus:
            tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

        # Save to disk
        self._save_index()

        logger.info(f"Deleted {len(indices_to_remove)} chunks for document {document_id}")
        return len(indices_to_remove)

    def count(self) -> int:
        """Get total number of chunks in index."""
        return len(self.corpus)

    def clear_all(self) -> bool:
        """
        Clear all chunks from the BM25 index.

        Returns:
            True if successful
        """
        logger.info("Clearing all chunks from BM25 index")

        try:
            self.corpus = []
            self.metadata = []
            self.bm25 = None

            # Save empty index to disk
            self._save_index()

            logger.info("BM25 index cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing BM25 index: {e}")
            return False
