"""Chat session and message models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Enumerations
# ============================================================================


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SessionStatus(str, Enum):
    """Chat session status."""

    ACTIVE = "active"
    ENDED = "ended"
    ARCHIVED = "archived"


class FeedbackType(str, Enum):
    """Type of user feedback."""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"  # 1-5 stars
    CUSTOM = "custom"


class EndReason(str, Enum):
    """Reason for session ending."""

    USER_ENDED = "user_ended"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"  # Handed off to human
    ERROR = "error"


# ============================================================================
# Session Models
# ============================================================================


class ChatSession(BaseModel):
    """A chat conversation session."""

    session_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    # User identification (optional, for tracking returning users)
    user_id: Optional[str] = None  # Could be email, user ID, etc.
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

    # Session metadata
    status: SessionStatus = SessionStatus.ACTIVE
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    end_reason: Optional[EndReason] = None

    # Conversation stats
    message_count: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0

    # Context
    language: str = "en"
    metadata: Dict[str, str] = {}


class Message(BaseModel):
    """A single message in a chat session."""

    message_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    tenant_id: UUID

    # Message content
    role: MessageRole
    content: str

    # Processing info
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = None
    token_count: Optional[int] = None

    # RAG information (for assistant messages)
    chunks_retrieved: Optional[int] = None
    sources_used: List[str] = []  # Document IDs or filenames
    confidence_score: Optional[float] = None

    # Agent information
    agent_action: Optional[str] = None  # greeting, knowledge, action, fallback
    needs_retrieval: Optional[bool] = None

    # Metadata
    metadata: Dict[str, str] = {}


class MessageFeedback(BaseModel):
    """User feedback on a message."""

    feedback_id: UUID = Field(default_factory=uuid4)
    message_id: UUID
    session_id: UUID
    tenant_id: UUID

    # Feedback data
    feedback_type: FeedbackType
    value: str  # "1" for thumbs up/down, "1-5" for rating, custom text
    comment: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_agent: Optional[str] = None


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""

    user_id: Optional[str] = None
    language: Optional[str] = "en"
    metadata: Optional[Dict[str, str]] = None


class SessionResponse(BaseModel):
    """Response containing session information."""

    session_id: UUID
    tenant_id: UUID
    status: SessionStatus
    started_at: datetime
    message_count: int


class MessageRequest(BaseModel):
    """Request to send a message."""

    session_id: UUID
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    """Response containing message information."""

    message_id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    created_at: datetime
    processing_time_ms: Optional[float] = None
    sources_used: List[str] = []


class SendFeedbackRequest(BaseModel):
    """Request to send feedback on a message."""

    message_id: UUID
    feedback_type: FeedbackType
    value: str
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""

    feedback_id: UUID
    message_id: UUID
    feedback_type: FeedbackType
    created_at: datetime
    message: str = "Thank you for your feedback!"


class ConversationHistory(BaseModel):
    """Complete conversation history for a session."""

    session_id: UUID
    tenant_id: UUID
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime]
    messages: List[Message]
    total_messages: int


class EndSessionRequest(BaseModel):
    """Request to end a chat session."""

    session_id: UUID
    end_reason: Optional[EndReason] = EndReason.USER_ENDED
    feedback: Optional[str] = None
