"""SQLAlchemy ORM models for multi-tenancy."""

from datetime import datetime
from typing import List
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base
from src.models.session import EndReason, FeedbackType, MessageRole, SessionStatus
from src.models.tenant import Industry, TenantStatus, TenantTier


class Tenant(Base):
    """Tenant table for multi-tenancy."""

    __tablename__ = "tenants"
    __allow_unmapped__ = True

    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    industry = Column(Enum(Industry), nullable=False)
    status = Column(Enum(TenantStatus), nullable=False, default=TenantStatus.ACTIVE)
    tier = Column(Enum(TenantTier), nullable=False, default=TenantTier.FREE)

    contact_email = Column(String(255), nullable=False, unique=True)
    contact_name = Column(String(255), nullable=True)
    company_website = Column(String(512), nullable=True)

    settings = Column(JSON, nullable=False, default=dict)

    base_urls = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    trial_ends_at = Column(DateTime, nullable=True)

    tenant_metadata = Column("metadata", JSON, nullable=False, default=dict)
    api_keys: List["TenantAPIKey"] = relationship("TenantAPIKey", back_populates="tenant", cascade="all, delete-orphan")
    sessions: List["ChatSession"] = relationship("ChatSession", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Tenant(id={self.tenant_id}, name='{self.name}', status={self.status})>"


class TenantAPIKey(Base):
    """API keys for tenant authentication."""

    __tablename__ = "tenant_api_keys"
    __allow_unmapped__ = True

    key_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False)
    prefix = Column(String(16), nullable=False)

    scopes = Column(JSON, nullable=False, default=["chat", "upload", "query"])

    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    usage_count = Column(Integer, nullable=False, default=0)

    tenant: Tenant = relationship("Tenant", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<TenantAPIKey(id={self.key_id}, prefix='{self.prefix}', tenant={self.tenant_id})>"


class ChatSession(Base):
    """Chat conversation sessions."""

    __tablename__ = "chat_sessions"
    __allow_unmapped__ = True

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)

    user_id = Column(String(255), nullable=True)
    user_agent = Column(String(512), nullable=True)
    ip_address = Column(String(45), nullable=True)

    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    end_reason = Column(Enum(EndReason), nullable=True)

    message_count = Column(Integer, nullable=False, default=0)
    user_message_count = Column(Integer, nullable=False, default=0)
    assistant_message_count = Column(Integer, nullable=False, default=0)

    language = Column(String(10), nullable=False, default="en")
    session_metadata = Column("metadata", JSON, nullable=False, default=dict)

    tenant: Tenant = relationship("Tenant", back_populates="sessions")
    messages: List["Message"] = relationship("Message", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.session_id}, tenant={self.tenant_id}, messages={self.message_count})>"


class Message(Base):
    """Individual messages in chat sessions."""

    __tablename__ = "messages"
    __allow_unmapped__ = True

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)

    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processing_time_ms = Column(Float, nullable=True)
    token_count = Column(Integer, nullable=True)

    chunks_retrieved = Column(Integer, nullable=True)
    sources_used = Column(JSON, nullable=False, default=list)
    confidence_score = Column(Float, nullable=True)

    agent_action = Column(String(50), nullable=True)
    needs_retrieval = Column(Boolean, nullable=True)

    message_metadata = Column("metadata", JSON, nullable=False, default=dict)

    session: ChatSession = relationship("ChatSession", back_populates="messages")
    feedback: List["MessageFeedback"] = relationship("MessageFeedback", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.message_id}, role={self.role}, content='{preview}')>"


class MessageFeedback(Base):
    """User feedback on messages."""

    __tablename__ = "message_feedback"
    __allow_unmapped__ = True

    feedback_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.message_id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)

    feedback_type = Column(Enum(FeedbackType), nullable=False)
    value = Column(String(255), nullable=False)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_agent = Column(String(512), nullable=True)

    message: Message = relationship("Message", back_populates="feedback")

    def __repr__(self) -> str:
        return f"<MessageFeedback(id={self.feedback_id}, type={self.feedback_type}, value='{self.value}')>"
