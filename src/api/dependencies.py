"""FastAPI dependencies for dependency injection."""

import logging
from functools import lru_cache

from src.ingestion import Embedder, ProcessorRouter, TextChunker
from src.retrieval import BM25Index, HybridRetriever, VectorStore
from src.retrieval.generator import Generator

logger = logging.getLogger(__name__)


@lru_cache()
def get_vector_store() -> VectorStore:
    """Get or create vector store instance."""
    return VectorStore()


@lru_cache()
def get_bm25_index() -> BM25Index:
    """Get or create BM25 index instance."""
    return BM25Index()


@lru_cache()
def get_embedder() -> Embedder:
    """Get or create embedder instance."""
    return Embedder()


@lru_cache()
def get_chunker() -> TextChunker:
    """Get or create chunker instance."""
    return TextChunker()


@lru_cache()
def get_processor_router() -> ProcessorRouter:
    """Get or create processor router instance."""
    return ProcessorRouter()


@lru_cache()
def get_retriever() -> HybridRetriever:
    """Get or create hybrid retriever instance."""
    return HybridRetriever(
        vector_store=get_vector_store(),
        bm25_index=get_bm25_index(),
        embedder=get_embedder(),
    )


@lru_cache()
def get_generator() -> Generator:
    """Get or create generator instance."""
    return Generator()
