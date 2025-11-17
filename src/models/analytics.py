"""Analytics and metrics models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Enumerations
# ============================================================================


class EventType(str, Enum):
    """Analytics event types."""

    # Session events
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"

    # Message events
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"

    # Query events
    QUERY_EXECUTED = "query_executed"
    RETRIEVAL_PERFORMED = "retrieval_performed"
    GENERATION_COMPLETED = "generation_completed"

    # Document events
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_DELETED = "document_deleted"

    # Feedback events
    FEEDBACK_SUBMITTED = "feedback_submitted"

    # Error events
    ERROR_OCCURRED = "error_occurred"

    # Widget events
    WIDGET_LOADED = "widget_loaded"
    WIDGET_OPENED = "widget_opened"
    WIDGET_CLOSED = "widget_closed"


class DeflectionOutcome(str, Enum):
    """Outcome of a support deflection attempt."""

    RESOLVED = "resolved"  # User got answer, didn't escalate
    ESCALATED = "escalated"  # User requested human support
    ABANDONED = "abandoned"  # User left without resolution
    UNKNOWN = "unknown"


# ============================================================================
# Analytics Models
# ============================================================================


class AnalyticsEvent(BaseModel):
    """A single analytics event."""

    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Context
    session_id: Optional[UUID] = None
    user_id: Optional[str] = None
    message_id: Optional[UUID] = None
    document_id: Optional[UUID] = None

    # Event data
    properties: Dict[str, str] = {}

    # Performance metrics
    duration_ms: Optional[float] = None
    token_count: Optional[int] = None
    cost_usd: Optional[float] = None


class UsageMetrics(BaseModel):
    """Aggregated usage metrics for a time period."""

    tenant_id: UUID
    period_start: datetime
    period_end: datetime

    # Conversation metrics
    total_sessions: int = 0
    total_messages: int = 0
    total_user_messages: int = 0
    total_assistant_messages: int = 0
    avg_messages_per_session: float = 0.0
    avg_session_duration_seconds: float = 0.0

    # Query metrics
    total_queries: int = 0
    total_retrievals: int = 0
    avg_query_latency_ms: float = 0.0
    avg_chunks_retrieved: float = 0.0

    # Document metrics
    total_documents: int = 0
    total_chunks: int = 0
    documents_uploaded: int = 0
    documents_deleted: int = 0

    # Feedback metrics
    total_feedback: int = 0
    thumbs_up_count: int = 0
    thumbs_down_count: int = 0
    avg_rating: Optional[float] = None

    # Deflection metrics
    deflection_rate: Optional[float] = None  # % of sessions resolved without escalation
    resolved_count: int = 0
    escalated_count: int = 0
    abandoned_count: int = 0

    # Cost metrics
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Error metrics
    total_errors: int = 0
    error_rate: float = 0.0


class QueryAnalytics(BaseModel):
    """Analytics for a specific query."""

    query_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    session_id: UUID
    message_id: UUID

    # Query info
    query_text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Retrieval metrics
    chunks_retrieved: int = 0
    chunks_used: int = 0
    retrieval_time_ms: float = 0.0
    avg_chunk_score: Optional[float] = None

    # Generation metrics
    generation_time_ms: float = 0.0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    total_tokens: int = 0

    # Quality metrics
    confidence_score: Optional[float] = None
    user_feedback: Optional[str] = None  # thumbs_up, thumbs_down, or rating

    # Agent metrics
    agent_action: Optional[str] = None
    needs_retrieval: bool = False
    iterations: int = 1


class TopQuery(BaseModel):
    """A frequently asked query."""

    query_text: str
    count: int
    avg_confidence: Optional[float] = None
    thumbs_up_ratio: Optional[float] = None
    last_seen: datetime


# ============================================================================
# Request/Response Models
# ============================================================================


class GetUsageMetricsRequest(BaseModel):
    """Request to get usage metrics."""

    tenant_id: Optional[UUID] = None
    start_date: datetime
    end_date: datetime
    granularity: str = "day"  # hour, day, week, month


class UsageMetricsResponse(BaseModel):
    """Response containing usage metrics."""

    tenant_id: Optional[UUID]
    start_date: datetime
    end_date: datetime
    metrics: UsageMetrics


class GetTopQueriesRequest(BaseModel):
    """Request to get top queries."""

    tenant_id: Optional[UUID] = None
    start_date: datetime
    end_date: datetime
    limit: int = Field(default=10, ge=1, le=100)


class TopQueriesResponse(BaseModel):
    """Response containing top queries."""

    tenant_id: Optional[UUID]
    start_date: datetime
    end_date: datetime
    queries: List[TopQuery]


class GetFeedbackSummaryRequest(BaseModel):
    """Request to get feedback summary."""

    tenant_id: Optional[UUID] = None
    start_date: datetime
    end_date: datetime


class FeedbackSummary(BaseModel):
    """Summary of user feedback."""

    total_feedback: int
    thumbs_up_count: int
    thumbs_down_count: int
    thumbs_up_ratio: float
    avg_rating: Optional[float] = None
    top_positive_queries: List[str] = []
    top_negative_queries: List[str] = []
    common_complaints: List[str] = []


class FeedbackSummaryResponse(BaseModel):
    """Response containing feedback summary."""

    tenant_id: Optional[UUID]
    start_date: datetime
    end_date: datetime
    summary: FeedbackSummary


class PerformanceMetrics(BaseModel):
    """Real-time performance metrics."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Latency (ms)
    p50_query_latency: float
    p95_query_latency: float
    p99_query_latency: float
    avg_query_latency: float

    # Throughput (queries per second)
    queries_per_second: float

    # Error rates
    error_rate_5min: float
    error_rate_1hour: float

    # System health
    vector_store_size: int
    bm25_index_size: int
    active_sessions: int


class ExportDataRequest(BaseModel):
    """Request to export analytics data."""

    tenant_id: Optional[UUID] = None
    start_date: datetime
    end_date: datetime
    data_types: List[str] = ["sessions", "messages", "queries", "feedback"]
    format: str = "csv"  # csv or json


class ExportDataResponse(BaseModel):
    """Response containing export job information."""

    export_id: UUID = Field(default_factory=uuid4)
    status: str = "processing"
    download_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
