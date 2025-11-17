"""Chat session API routes."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from src.db import get_db
from src.middleware import get_current_tenant_id
from src.models.session import (
    ConversationHistory,
    CreateSessionRequest,
    EndSessionRequest,
    FeedbackResponse,
    MessageResponse,
    SendFeedbackRequest,
    SessionResponse,
    SessionStatus,
)
from src.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> SessionResponse:
    """
    Create a new chat session.

    Requires: X-API-Key header

    Args:
        request: Session creation request
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Created session
    """
    try:
        session = SessionService.create_session(db, tenant_id, request)

        return SessionResponse(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            status=session.status,
            started_at=session.started_at,
            message_count=session.message_count,
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> SessionResponse:
    """
    Get session by ID.

    Requires: X-API-Key header

    Args:
        session_id: Session ID
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Session information

    Raises:
        HTTPException: If session not found or not owned by tenant
    """
    session = SessionService.get_session(db, session_id, tenant_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionResponse(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        status=session.status,
        started_at=session.started_at,
        message_count=session.message_count,
    )


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: UUID,
    request: EndSessionRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> SessionResponse:
    """
    End a chat session.

    Requires: X-API-Key header

    Args:
        session_id: Session ID
        request: End session request
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Updated session

    Raises:
        HTTPException: If session not found
    """
    session = SessionService.end_session(db, session_id, tenant_id, request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionResponse(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        status=session.status,
        started_at=session.started_at,
        message_count=session.message_count,
    )


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: UUID,
    limit: int = 100,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> List[MessageResponse]:
    """
    Get messages for a session.

    Requires: X-API-Key header

    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        List of messages
    """
    messages = SessionService.get_messages(db, session_id, tenant_id, limit)

    return [
        MessageResponse(
            message_id=msg.message_id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            processing_time_ms=msg.processing_time_ms,
            sources_used=msg.sources_used,
        )
        for msg in messages
    ]


@router.get("/{session_id}/history", response_model=ConversationHistory)
async def get_conversation_history(
    session_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> ConversationHistory:
    """
    Get complete conversation history for a session.

    Requires: X-API-Key header

    Args:
        session_id: Session ID
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Complete conversation history

    Raises:
        HTTPException: If session not found
    """
    session = SessionService.get_session(db, session_id, tenant_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    messages = SessionService.get_messages(db, session_id, tenant_id)

    # Convert to Pydantic models
    from src.models.session import Message as MessageModel

    message_models = [
        MessageModel(
            message_id=msg.message_id,
            session_id=msg.session_id,
            tenant_id=msg.tenant_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            processing_time_ms=msg.processing_time_ms,
            token_count=msg.token_count,
            chunks_retrieved=msg.chunks_retrieved,
            sources_used=msg.sources_used,
            confidence_score=msg.confidence_score,
            agent_action=msg.agent_action,
            needs_retrieval=msg.needs_retrieval,
            metadata=msg.metadata,
        )
        for msg in messages
    ]

    return ConversationHistory(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        messages=message_models,
        total_messages=session.message_count,
    )


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def send_feedback(
    message_id: UUID,
    request: SendFeedbackRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> FeedbackResponse:
    """
    Send feedback on a message.

    Requires: X-API-Key header

    Args:
        message_id: Message ID
        request: Feedback request
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        Feedback confirmation

    Raises:
        HTTPException: If message not found
    """
    from src.db.models import Message

    # Verify message exists and belongs to tenant
    message = db.query(Message).filter(
        Message.message_id == message_id,
        Message.tenant_id == tenant_id
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )

    try:
        feedback = SessionService.add_feedback(
            db, message_id, message.session_id, tenant_id, request
        )

        return FeedbackResponse(
            feedback_id=feedback.feedback_id,
            message_id=feedback.message_id,
            feedback_type=feedback.feedback_type,
            created_at=feedback.created_at,
        )
    except Exception as e:
        logger.error(f"Error adding feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add feedback"
        )


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[SessionStatus] = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: DBSession = Depends(get_db)
) -> List[SessionResponse]:
    """
    List sessions for the authenticated tenant.

    Requires: X-API-Key header

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        status_filter: Filter by session status (optional)
        tenant_id: Tenant ID (from API key)
        db: Database session

    Returns:
        List of sessions
    """
    sessions = SessionService.list_sessions(db, tenant_id, skip, limit, status_filter)

    return [
        SessionResponse(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            status=session.status,
            started_at=session.started_at,
            message_count=session.message_count,
        )
        for session in sessions
    ]
