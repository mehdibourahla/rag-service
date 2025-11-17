"""Chat session management service."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import ChatSession, Message, MessageFeedback
from src.models.session import (
    CreateSessionRequest,
    EndReason,
    EndSessionRequest,
    FeedbackType,
    MessageRole,
    SendFeedbackRequest,
    SessionStatus,
)


class SessionService:
    """Service for chat session management."""

    @staticmethod
    def create_session(
        db: Session,
        tenant_id: UUID,
        request: CreateSessionRequest
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            db: Database session
            tenant_id: Tenant ID
            request: Session creation request

        Returns:
            Created chat session
        """
        session = ChatSession(
            tenant_id=tenant_id,
            user_id=request.user_id,
            language=request.language or "en",
            metadata=request.metadata or {},
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        return session

    @staticmethod
    def get_session(db: Session, session_id: UUID, tenant_id: Optional[UUID] = None) -> Optional[ChatSession]:
        """
        Get a chat session by ID.

        Args:
            db: Database session
            session_id: Session ID
            tenant_id: Tenant ID for validation (optional)

        Returns:
            Chat session if found, None otherwise
        """
        query = db.query(ChatSession).filter(ChatSession.session_id == session_id)

        if tenant_id:
            query = query.filter(ChatSession.tenant_id == tenant_id)

        return query.first()

    @staticmethod
    def end_session(
        db: Session,
        session_id: UUID,
        tenant_id: UUID,
        request: EndSessionRequest
    ) -> Optional[ChatSession]:
        """
        End a chat session.

        Args:
            db: Database session
            session_id: Session ID
            tenant_id: Tenant ID
            request: End session request

        Returns:
            Updated session if found, None otherwise
        """
        session = SessionService.get_session(db, session_id, tenant_id)
        if not session:
            return None

        session.status = SessionStatus.ENDED
        session.ended_at = datetime.utcnow()
        session.end_reason = request.end_reason or EndReason.USER_ENDED

        db.commit()
        db.refresh(session)

        return session

    @staticmethod
    def add_message(
        db: Session,
        session_id: UUID,
        tenant_id: UUID,
        role: MessageRole,
        content: str,
        **kwargs
    ) -> Message:
        """
        Add a message to a session.

        Args:
            db: Database session
            session_id: Session ID
            tenant_id: Tenant ID
            role: Message role (user/assistant/system)
            content: Message content
            **kwargs: Additional message metadata

        Returns:
            Created message
        """
        message = Message(
            session_id=session_id,
            tenant_id=tenant_id,
            role=role,
            content=content,
            processing_time_ms=kwargs.get("processing_time_ms"),
            token_count=kwargs.get("token_count"),
            chunks_retrieved=kwargs.get("chunks_retrieved"),
            sources_used=kwargs.get("sources_used", []),
            confidence_score=kwargs.get("confidence_score"),
            agent_action=kwargs.get("agent_action"),
            needs_retrieval=kwargs.get("needs_retrieval"),
            metadata=kwargs.get("metadata", {}),
        )

        db.add(message)

        # Update session message counts
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session:
            session.message_count += 1
            if role == MessageRole.USER:
                session.user_message_count += 1
            elif role == MessageRole.ASSISTANT:
                session.assistant_message_count += 1

        db.commit()
        db.refresh(message)

        return message

    @staticmethod
    def get_messages(
        db: Session,
        session_id: UUID,
        tenant_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[Message]:
        """
        Get messages for a session.

        Args:
            db: Database session
            session_id: Session ID
            tenant_id: Tenant ID for validation (optional)
            limit: Maximum number of messages to return

        Returns:
            List of messages
        """
        query = db.query(Message).filter(Message.session_id == session_id)

        if tenant_id:
            query = query.filter(Message.tenant_id == tenant_id)

        return query.order_by(Message.created_at).limit(limit).all()

    @staticmethod
    def add_feedback(
        db: Session,
        message_id: UUID,
        session_id: UUID,
        tenant_id: UUID,
        request: SendFeedbackRequest
    ) -> MessageFeedback:
        """
        Add feedback to a message.

        Args:
            db: Database session
            message_id: Message ID
            session_id: Session ID
            tenant_id: Tenant ID
            request: Feedback request

        Returns:
            Created feedback
        """
        feedback = MessageFeedback(
            message_id=message_id,
            session_id=session_id,
            tenant_id=tenant_id,
            feedback_type=request.feedback_type,
            value=request.value,
            comment=request.comment,
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        return feedback

    @staticmethod
    def list_sessions(
        db: Session,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[SessionStatus] = None
    ) -> List[ChatSession]:
        """
        List sessions for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by status (optional)

        Returns:
            List of chat sessions
        """
        query = db.query(ChatSession).filter(ChatSession.tenant_id == tenant_id)

        if status:
            query = query.filter(ChatSession.status == status)

        return query.order_by(ChatSession.started_at.desc()).offset(skip).limit(limit).all()
