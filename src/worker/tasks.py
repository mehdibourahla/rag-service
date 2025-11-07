"""Worker tasks for async document processing."""

import logging
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)


def process_document(document_id: UUID, file_path: str):
    """
    Process a document: extract content, chunk, embed, and index.

    Args:
        document_id: Document ID
        file_path: Path to the file

    This function is designed to be called either synchronously or
    via RQ worker for async processing.
    """
    logger.info(f"Processing document {document_id}: {file_path}")

    try:
        from src.ingestion import Embedder, ProcessorRouter, TextChunker
        from src.retrieval import BM25Index, VectorStore

        # Initialize components
        router = ProcessorRouter()
        chunker = TextChunker()
        embedder = Embedder()
        vector_store = VectorStore()
        bm25_index = BM25Index()

        # 1. Route to processor and extract text
        text, modality = router.route(Path(file_path))
        logger.info(f"Extracted text: {len(text)} chars, modality: {modality}")

        # 2. Chunk text
        chunks = chunker.chunk(
            text=text,
            document_id=document_id,
            source=file_path,
            modality=modality,
        )
        logger.info(f"Created {len(chunks)} chunks")

        if not chunks:
            raise ValueError("No chunks created from document")

        # 3. Generate embeddings
        chunks_with_embeddings = embedder.embed_chunks(chunks)

        # 4. Add to vector store
        vector_count = vector_store.add_chunks(chunks_with_embeddings)
        logger.info(f"Added {vector_count} chunks to vector store")

        # 5. Add to BM25 index
        bm25_count = bm25_index.add_chunks(chunks)
        logger.info(f"Added {bm25_count} chunks to BM25 index")

        logger.info(f"Successfully processed document {document_id}")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        raise


# RQ task wrapper (for async execution via Redis Queue)
def process_document_task(document_id: str, file_path: str):
    """
    RQ task wrapper for document processing.

    Args:
        document_id: Document ID (as string)
        file_path: Path to the file
    """
    from uuid import UUID

    process_document(UUID(document_id), file_path)
