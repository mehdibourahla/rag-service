"""FastAPI dependencies for dependency injection."""

import logging
from functools import lru_cache
from typing import Optional
from uuid import UUID

from src.ingestion.chunker import TextChunker
from src.ingestion.embedder import Embedder
from src.ingestion.router import ProcessorRouter
from src.retrieval.bm25_index import BM25Index
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import VectorStore
from src.retrieval.generator import Generator

logger = logging.getLogger(__name__)


# Global/shared instances (no tenant isolation)
@lru_cache()
def get_vector_store() -> VectorStore:
    """Get or create vector store instance (shared, tenant filtering done at query time)."""
    return VectorStore()


@lru_cache()
def get_embedder() -> Embedder:
    """Get or create embedder instance (shared)."""
    return Embedder()


@lru_cache()
def get_chunker() -> TextChunker:
    """Get or create chunker instance (shared)."""
    return TextChunker()


@lru_cache()
def get_processor_router() -> ProcessorRouter:
    """Get or create processor router instance (shared)."""
    return ProcessorRouter()


@lru_cache()
def get_generator() -> Generator:
    """Get or create generator instance (shared)."""
    return Generator()


# Tenant-specific instances
def get_tenant_bm25_index(tenant_id: Optional[UUID] = None) -> BM25Index:
    """
    Get BM25 index for a specific tenant.

    Args:
        tenant_id: Tenant ID (if None, uses global index)

    Returns:
        Tenant-specific BM25Index instance
    """
    return BM25Index(tenant_id=tenant_id)


def get_tenant_retriever(tenant_id: Optional[UUID] = None) -> HybridRetriever:
    """
    Get hybrid retriever for a specific tenant.

    Args:
        tenant_id: Tenant ID for tenant-scoped retrieval

    Returns:
        Tenant-specific HybridRetriever instance
    """
    return HybridRetriever(
        vector_store=get_vector_store(),
        bm25_index=get_tenant_bm25_index(tenant_id),
        embedder=get_embedder(),
        tenant_id=tenant_id,  # Pass to retriever for filtering
    )


@lru_cache()
def get_bm25_index() -> BM25Index:
    """Get or create BM25 index instance."""
    return BM25Index()


@lru_cache()
def get_retriever() -> HybridRetriever:
    """Get or create hybrid retriever instance."""
    return HybridRetriever(
        vector_store=get_vector_store(),
        bm25_index=get_bm25_index(),
        embedder=get_embedder(),
    )
