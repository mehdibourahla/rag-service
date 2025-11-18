"""Chat and query API routes."""

import json
import logging
import time
import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from src.agent import Agent, ActionType, AgentExecutor, ConversationMemory
from src.api.dependencies import get_embedder, get_generator, get_tenant_retriever
from src.core.config import settings
from src.db import get_db
from src.middleware import get_current_tenant_id
from src.models.schemas import QueryRequest, QueryResponse
from src.models.session import MessageRole
from src.retrieval.generator import Generator
from src.retrieval.hybrid_retriever import HybridRetriever
from src.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class Message(BaseModel):
    """Chat message format compatible with AI SDK."""
    role: str
    content: str

    class Config:
        extra = "allow"  # Allow extra fields from AI SDK


class ChatRequest(BaseModel):
    """Chat request format compatible with AI SDK."""
    messages: List[Message]
    session_id: UUID | None = None  # Optional session tracking

    class Config:
        extra = "allow"  # Allow extra fields from AI SDK


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> QueryResponse:
    """
    Query documents using RAG (tenant-scoped).

    Requires: X-API-Key header

    Args:
        request: Query request
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Query response with answer and citations
    """
    try:
        start_time = time.time()

        # Get tenant-specific retriever
        retriever = get_tenant_retriever(tenant_id)
        generator = get_generator()

        # Retrieve relevant chunks (automatically filtered by tenant)
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

        logger.info(f"Tenant {tenant_id} query completed in {processing_time:.2f}s")

        return QueryResponse(
            query=request.query,
            answer=answer,
            chunks=chunks,
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"Query error for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/chat")
async def chat_stream(
    request: ChatRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
):
    """
    Streaming chat endpoint compatible with AI SDK (tenant-scoped).

    Requires: X-API-Key header

    Args:
        request: Chat request with messages
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        StreamingResponse with AI SDK Data Stream Protocol format
    """
    try:
        # Extract the last user message as the query
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user message found")

        query = user_messages[-1].content

        # Get or create session
        session_id = request.session_id
        if not session_id:
            # Create new session
            from src.models.session import CreateSessionRequest
            session = SessionService.create_session(
                db, tenant_id, CreateSessionRequest()
            )
            session_id = session.session_id
            logger.info(f"Created new session {session_id} for tenant {tenant_id}")

        # Save user message
        start_time = time.time()
        user_message = SessionService.add_message(
            db, session_id, tenant_id, MessageRole.USER, query
        )

        # Load conversation history from database and manage context
        from src.agent.memory import Message as MemMessage
        memory = ConversationMemory(max_recent_messages=10)

        # Convert request messages to memory format
        msg_objects = [MemMessage(role=m.role, content=m.content) for m in request.messages]
        optimized_context = memory.manage_context(msg_objects)
        context_enhanced_query = memory.extract_query_context(optimized_context, query)

        # Get tenant-specific retriever
        retriever = get_tenant_retriever(tenant_id)
        generator = get_generator()

        # Execute agent with retry logic using context-enhanced query
        executor = AgentExecutor(
            retriever=retriever,
            max_retries=1,  # Single retry with query expansion if no results
        )

        chunks, execution_steps, plan = executor.execute(
            query=context_enhanced_query, top_k=settings.final_top_k
        )

        logger.info(
            f"Tenant {tenant_id} agent execution: action={plan.action}, "
            f"needs_retrieval={plan.needs_retrieval}, "
            f"chunks_found={len(chunks)}"
        )

        # Prepare enhanced source metadata for response
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
            text_id = str(uuid.uuid4())
            full_response = ""

            try:
                # Start text block
                start_event = {"type": "text-start", "id": text_id}
                yield f'data: {json.dumps(start_event)}\n\n'

                if plan.needs_retrieval:
                    if not chunks:
                        # No documents found - fall back to general knowledge
                        logger.info("No documents found, using general knowledge")
                        for token in generator.generate_stream(query=query, chunks=[]):
                            delta_event = {"type": "text-delta", "id": text_id, "delta": token}
                            yield f'data: {json.dumps(delta_event)}\n\n'
                            full_response += token
                    else:
                        logger.info(f"Generating answer from {len(chunks)} chunks")
                        for token in generator.generate_stream(query=query, chunks=chunks):
                            delta_event = {"type": "text-delta", "id": text_id, "delta": token}
                            yield f'data: {json.dumps(delta_event)}\n\n'
                            full_response += token

                        # Send enhanced source documents
                        for source_meta in sources_metadata:
                            source_event = {
                                "type": "source-document",
                                "sourceId": source_meta["chunk_id"],
                                "mediaType": "file",
                                "title": source_meta["title"],
                                "page_number": source_meta["page_number"],
                                "score": source_meta["score"],
                                "modality": source_meta["modality"],
                                "text_preview": source_meta["text_preview"],
                            }
                            yield f'data: {json.dumps(source_event)}\n\n'

                else:
                    logger.info(f"Executing {plan.action} without RAG")
                    if plan.suggested_response:
                        # Use pre-generated response (e.g., for greetings)
                        for char in plan.suggested_response:
                            delta_event = {"type": "text-delta", "id": text_id, "delta": char}
                            yield f'data: {json.dumps(delta_event)}\n\n'
                            full_response += char
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
                            full_response += token

                # End text block
                end_event = {"type": "text-end", "id": text_id}
                yield f'data: {json.dumps(end_event)}\n\n'

                # Save assistant message
                processing_time_ms = (time.time() - start_time) * 1000
                SessionService.add_message(
                    db, session_id, tenant_id, MessageRole.ASSISTANT, full_response,
                    processing_time_ms=processing_time_ms,
                    chunks_retrieved=len(chunks) if chunks else None,
                    sources_used=[chunk.metadata.source for chunk in chunks] if chunks else [],
                    agent_action=plan.action.value if plan.action else None,
                    needs_retrieval=plan.needs_retrieval,
                )

            except Exception as e:
                logger.error(f"Error during stream generation for tenant {tenant_id}: {e}")
                yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'
            finally:
                yield 'data: [DONE]\n\n'

        # Prepare response headers with enhanced metadata
        response_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Vercel-AI-Data-Stream": "v1",
            "X-Session-Id": str(session_id),  # Return session ID to client
        }

        # Add source metadata to headers if available
        if sources_metadata:
            response_headers["X-Source-Count"] = str(len(sources_metadata))
            # Include compact source info in header (just filenames and scores)
            sources_compact = [
                f"{s['source']}:{s['score']:.2f}" for s in sources_metadata
            ]
            response_headers["X-Sources"] = ";".join(sources_compact[:5])  # Limit to 5 for header size

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers=response_headers
        )

    except Exception as e:
        logger.error(f"Chat stream error for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
