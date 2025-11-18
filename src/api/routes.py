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

from src.agent import Agent, ActionType, AgentExecutor, ConversationMemory
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


class Message(BaseModel):
    """Chat message format compatible with AI SDK."""
    role: str
    content: str

    class Config:
        extra = "allow"  # Allow extra fields from AI SDK


class ChatRequest(BaseModel):
    """Chat request format compatible with AI SDK."""
    messages: List[Message]
    use_rag: bool = True  # Default to RAG-augmented

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


@router.delete("/indexes/clear")
async def clear_all_indexes():
    """
    Clear all indexes (vector store and BM25).

    This will delete all documents and chunks from the knowledge base.

    Returns:
        Status of the operation
    """
    try:
        from src.api.dependencies import get_bm25_index, get_vector_store

        vector_store = get_vector_store()
        bm25_index = get_bm25_index()

        logger.info("Clearing all indexes...")

        # Clear both stores
        vector_success = vector_store.clear_all()
        bm25_success = bm25_index.clear_all()

        if vector_success and bm25_success:
            logger.info("All indexes cleared successfully")
            return {
                "message": "All indexes cleared successfully",
                "vector_store_cleared": True,
                "bm25_index_cleared": True,
            }
        else:
            logger.warning("Some indexes failed to clear")
            return {
                "message": "Some indexes failed to clear",
                "vector_store_cleared": vector_success,
                "bm25_index_cleared": bm25_success,
            }

    except Exception as e:
        logger.error(f"Clear indexes error: {e}")
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
        logger.info(f"Received use_rag parameter: {request.use_rag}")
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")

        query = user_messages[-1].content

        # Manage conversation context
        from src.agent.memory import Message as MemMessage
        memory = ConversationMemory(max_recent_messages=10)
        msg_objects = [MemMessage(role=m.role, content=m.content) for m in request.messages]
        optimized_context = memory.manage_context(msg_objects)
        context_enhanced_query = memory.extract_query_context(optimized_context, query)

        # Execute agent planning
        executor = AgentExecutor(
            retriever=retriever,
            max_iterations=2,
            quality_threshold=0.5,
            enable_reflection=False,
        )

        # Only execute retrieval if use_rag is True
        if request.use_rag:
            chunks, execution_steps, plan = executor.execute(
                query=context_enhanced_query, top_k=settings.final_top_k
            )
        else:
            # Skip retrieval, use vanilla LLM
            plan = executor.agent.plan(query=context_enhanced_query)
            chunks = []
            execution_steps = []
            # Force general chat mode
            plan.needs_retrieval = False

        logger.info(
            f"Agent execution completed: action={plan.action}, "
            f"needs_retrieval={plan.needs_retrieval}, "
            f"steps_taken={len(execution_steps)}, "
            f"chunks_found={len(chunks)}"
        )

        # Prepare sources metadata for response header
        sources_metadata = []
        if plan.needs_retrieval and chunks:
            for chunk in chunks:
                filename = chunk.metadata.source.split("/")[-1]
                page_info = f" (Page {chunk.metadata.page_number})" if chunk.metadata.page_number else ""
                score_info = f" [{(chunk.score * 100):.0f}%]"

                # Truncate chunk text for preview (first 200 chars)
                text_preview = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text

                sources_metadata.append({
                    "chunk_id": str(chunk.metadata.chunk_id),
                    "source": filename,
                    "title": f"{filename}{page_info}{score_info}",
                    "page_number": chunk.metadata.page_number,
                    "score": chunk.score,
                    "modality": chunk.metadata.modality.value,
                    "text_preview": text_preview,
                })

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
                        logger.info("No documents found, using general knowledge")
                        for token in generator.generate_stream(query=query, chunks=[]):
                            delta_event = {"type": "text-delta", "id": text_id, "delta": token}
                            yield f'data: {json.dumps(delta_event)}\n\n'
                    else:
                        logger.info(f"Generating answer from {len(chunks)} chunks")

                        # Stream the text response
                        for token in generator.generate_stream(query=query, chunks=chunks):
                            delta_event = {"type": "text-delta", "id": text_id, "delta": token}
                            yield f'data: {json.dumps(delta_event)}\n\n'

                else:
                    logger.info(f"Executing {plan.action} without RAG")
                    if plan.suggested_response:
                        # Use pre-generated response (e.g., for greetings)
                        for char in plan.suggested_response:
                            delta_event = {"type": "text-delta", "id": text_id, "delta": char}
                            yield f'data: {json.dumps(delta_event)}\n\n'
                    else:
                        # Use vanilla LLM streaming (no RAG prompt) with conversation history
                        # Convert request messages to OpenAI format (exclude the current query)
                        conversation_history = [
                            {"role": msg.role, "content": msg.content}
                            for msg in request.messages[:-1]  # Exclude last message (current query)
                        ]
                        for token in generator.generate_vanilla_stream(
                            query=query,
                            conversation_history=conversation_history
                        ):
                            delta_event = {"type": "text-delta", "id": text_id, "delta": token}
                            yield f'data: {json.dumps(delta_event)}\n\n'

                end_event = {"type": "text-end", "id": text_id}
                yield f'data: {json.dumps(end_event)}\n\n'

            except Exception as e:
                logger.error(f"Error during stream generation: {e}")
                yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'
            finally:
                yield 'data: [DONE]\n\n'

        # Prepare headers with sources metadata
        response_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-data-stream": "v1",
        }

        # Add sources as a custom header (URL-encoded JSON)
        if sources_metadata:
            import urllib.parse
            sources_json = json.dumps(sources_metadata)
            response_headers["x-rag-sources"] = urllib.parse.quote(sources_json)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers=response_headers
        )

    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
