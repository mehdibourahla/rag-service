"""API route handlers."""

import json
import logging
import time
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent import Agent, ActionType, AgentExecutor
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
from src.services.document_service import process_document

logger = logging.getLogger(__name__)

router = APIRouter()


class Message(BaseModel):
    """Chat message format compatible with AI SDK."""
    role: str
    content: str

    class Config:
        extra = "allow"  # Allow extra fields from AI SDK


class ChatRequest(BaseModel):
    """Chat request format compatible with AI SDK."""
    messages: List[Message]

    class Config:
        extra = "allow"  # Allow extra fields from AI SDK


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

        # Process document synchronously
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


@router.post("/chat")
async def chat_stream(
    request: ChatRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: Generator = Depends(get_generator),
):
    """
    Streaming chat endpoint compatible with AI SDK.

    Args:
        request: Chat request with messages
        retriever: Hybrid retriever instance
        generator: Generator instance

    Returns:
        StreamingResponse with AI SDK Data Stream Protocol format
    """
    try:
        # Extract the last user message as the query
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")

        query = user_messages[-1].content

        # Execute agent with ReAct pattern
        executor = AgentExecutor(
            retriever=retriever,
            max_iterations=2,
            quality_threshold=0.5,
            enable_reflection=False,  # Disabled for speed (1 LLM call vs 2-3)
        )

        chunks, execution_steps, plan = executor.execute(
            query=query, top_k=settings.final_top_k
        )

        logger.info(
            f"Agent execution completed: action={plan.action}, "
            f"needs_retrieval={plan.needs_retrieval}, "
            f"steps_taken={len(execution_steps)}, "
            f"chunks_found={len(chunks)}"
        )

        async def generate():
            """Generate AI SDK compatible streaming response."""
            import uuid
            text_id = str(uuid.uuid4())

            try:
                # Start text block
                start_event = {"type": "text-start", "id": text_id}
                yield f'data: {json.dumps(start_event)}\n\n'

                if plan.needs_retrieval:
                    if not chunks:
                        response = "I couldn't find any relevant information in the uploaded documents for your question. The agent tried multiple search strategies but couldn't locate useful content. Could you try rephrasing or ask about something else?"
                        for char in response:
                            delta_event = {"type": "text-delta", "id": text_id, "delta": char}
                            yield f'data: {json.dumps(delta_event)}\n\n'
                    else:
                        logger.info(f"Generating answer from {len(chunks)} chunks")
                        for token in generator.generate_stream(query=query, chunks=chunks):
                            delta_event = {"type": "text-delta", "id": text_id, "delta": token}
                            yield f'data: {json.dumps(delta_event)}\n\n'

                        for chunk in chunks:
                            filename = chunk.metadata.source.split("/")[-1]
                            page_info = f" (Page {chunk.metadata.page_number})" if chunk.metadata.page_number else ""
                            score_info = f" [{(chunk.score * 100):.0f}%]"

                            source_event = {
                                "type": "source-document",
                                "sourceId": str(chunk.metadata.chunk_id),
                                "mediaType": "file",
                                "title": f"{filename}{page_info}{score_info}",
                            }
                            yield f'data: {json.dumps(source_event)}\n\n'

                else:
                    logger.info(f"Executing {plan.action} without RAG")
                    response = plan.suggested_response if plan.suggested_response else generator.generate(query=query, chunks=[])

                    for char in response:
                        delta_event = {"type": "text-delta", "id": text_id, "delta": char}
                        yield f'data: {json.dumps(delta_event)}\n\n'

                end_event = {"type": "text-end", "id": text_id}
                yield f'data: {json.dumps(end_event)}\n\n'

            except Exception as e:
                logger.error(f"Error during stream generation: {e}")
                yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'
            finally:
                yield 'data: [DONE]\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "x-vercel-ai-data-stream": "v1",
            }
        )

    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
