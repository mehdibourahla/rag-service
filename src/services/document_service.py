"""Document processing service."""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from src.core.config import settings
from src.ingestion.chunker import TextChunker
from src.ingestion.embedder import Embedder
from src.ingestion.router import ProcessorRouter
from src.retrieval.bm25_index import BM25Index
from src.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


def process_document(document_id: UUID, file_path: str, tenant_id: Optional[UUID] = None):
    """
    Process a document: extract, chunk, embed, and index.

    Args:
        document_id: Unique document identifier
        file_path: Path to the uploaded file
        tenant_id: Tenant ID for multi-tenancy

    Raises:
        Exception: If processing fails
    """
    try:
        path = Path(file_path)
        logger.info(f"Processing document {document_id} for tenant {tenant_id}: {path.name}")

        # Initialize components
        router = ProcessorRouter()
        chunker = TextChunker(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        embedder = Embedder(model=settings.embedding_model)
        vector_store = VectorStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection,
        )

        # Use tenant-specific BM25 index if tenant_id is provided
        if tenant_id:
            bm25_index = BM25Index(tenant_id=tenant_id)
        else:
            bm25_index = BM25Index(index_path=settings.chunks_dir / "bm25_index.json")

        # Step 1: Extract content
        content, modality = router.route(path)
        logger.info(f"Extracted content from {path.name} (modality: {modality})")

        # Step 2: Chunk content
        chunks = chunker.chunk(
            text=content,
            document_id=document_id,
            source=str(path),
            modality=modality,
        )
        logger.info(f"Created {len(chunks)} chunks")

        # Step 3: Generate embeddings
        embedder.embed_chunks(chunks)
        logger.info(f"Generated embeddings for {len(chunks)} chunks")

        # Step 4: Index in vector store (with tenant_id)
        vector_store.add_chunks(chunks, tenant_id=tenant_id)
        logger.info(f"Indexed {len(chunks)} chunks in vector store")

        # Step 5: Index in BM25 (with tenant_id)
        bm25_index.add_chunks(chunks, tenant_id=tenant_id)
        logger.info(f"Indexed {len(chunks)} chunks in BM25 index")

        logger.info(f"Successfully processed document {document_id} for tenant {tenant_id}")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        raise
