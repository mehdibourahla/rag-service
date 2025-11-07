"""API route handlers."""

import logging
import time
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.api.dependencies import get_embedder, get_generator, get_retriever
from src.core.config import settings
from src.ingestion import Embedder, ProcessorRouter, TextChunker
from src.models.schemas import (
    DocumentStatus,
    ProcessingStatus,
    QueryRequest,
    QueryResponse,
    UploadResponse,
)
from src.retrieval import BM25Index, HybridRetriever, VectorStore
from src.retrieval.generator import Generator
from src.worker.tasks import process_document_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a document for processing.

    Args:
        file: Uploaded file

    Returns:
        Upload response with document ID and status
    """
    try:
        # Save uploaded file
        from src.ingestion.file_detector import FileDetector
        from src.models.schemas import DocumentMetadata

        file_path = settings.upload_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)

        # Detect file type
        file_type = FileDetector.detect(file_path)

        # Create metadata
        metadata = DocumentMetadata(
            filename=file.filename,
            file_type=file_type,
            source_path=str(file_path),
            size_bytes=len(content),
        )

        logger.info(f"Uploaded {file.filename} ({file_type}) - {metadata.document_id}")

        # Enqueue processing task (async)
        # For now, process synchronously - can be moved to RQ later
        from src.worker.tasks import process_document

        try:
            process_document(metadata.document_id, str(file_path))
            status = ProcessingStatus.COMPLETED
            message = "Document processed successfully"
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            status = ProcessingStatus.FAILED
            message = f"Processing failed: {str(e)}"

        return UploadResponse(
            document_id=metadata.document_id,
            filename=metadata.filename,
            file_type=metadata.file_type,
            size_bytes=metadata.size_bytes,
            status=status,
            message=message,
        )

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: Generator = Depends(get_generator),
) -> QueryResponse:
    """
    Query documents using RAG.

    Args:
        request: Query request
        retriever: Hybrid retriever instance
        generator: Generator instance

    Returns:
        Query response with answer and citations
    """
    try:
        start_time = time.time()

        # Retrieve relevant chunks
        chunks = retriever.retrieve(query=request.query, top_k=request.top_k)

        if not chunks:
            return QueryResponse(
                query=request.query,
                answer="I couldn't find any relevant information in the knowledge base.",
                chunks=[],
                processing_time=time.time() - start_time,
            )

        # Generate answer
        answer = generator.generate(query=request.query, chunks=chunks)

        processing_time = time.time() - start_time

        return QueryResponse(
            query=request.query,
            answer=answer,
            chunks=chunks,
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    from src.api.dependencies import get_bm25_index, get_vector_store

    vector_store = get_vector_store()
    bm25_index = get_bm25_index()

    return {
        "status": "healthy",
        "vector_store_count": vector_store.count(),
        "bm25_index_count": bm25_index.count(),
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: UUID):
    """
    Delete a document and all its chunks.

    Args:
        document_id: Document ID to delete

    Returns:
        Deletion status
    """
    try:
        from src.api.dependencies import get_bm25_index, get_vector_store

        vector_store = get_vector_store()
        bm25_index = get_bm25_index()

        # Delete from both stores
        vector_store.delete_by_document(document_id)
        bm25_index.delete_by_document(document_id)

        logger.info(f"Deleted document {document_id}")

        return {"message": f"Document {document_id} deleted successfully"}

    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
