"""Tenant models for multi-tenancy support."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# Enumerations
# ============================================================================


class TenantStatus(str, Enum):
    """Tenant status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    DELETED = "deleted"


class TenantTier(str, Enum):
    """Tenant subscription tier."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Industry(str, Enum):
    """Industry categories."""

    ECOMMERCE = "ecommerce"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    INSURANCE = "insurance"
    EDUCATION = "education"
    TECHNOLOGY = "technology"
    RETAIL = "retail"
    OTHER = "other"


class BrandTone(str, Enum):
    """Brand tone/personality."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CASUAL = "casual"
    FORMAL = "formal"
    TECHNICAL = "technical"
    EMPATHETIC = "empathetic"


# ============================================================================
# Tenant Models
# ============================================================================


class TenantSettings(BaseModel):
    """Tenant-specific settings and customization."""

    # Branding
    brand_name: str
    brand_tone: BrandTone = BrandTone.PROFESSIONAL
    primary_color: str = "#007bff"
    logo_url: Optional[HttpUrl] = None

    # Language and localization
    default_language: str = "en"
    supported_languages: List[str] = ["en"]

    # Widget configuration
    widget_position: str = "bottom-right"  # bottom-right, bottom-left, etc.
    widget_greeting: str = "Hi! How can I help you today?"
    widget_placeholder: str = "Type your message..."

    # Behavior settings
    enable_citations: bool = True
    enable_feedback: bool = True
    max_context_length: int = 4000
    response_temperature: float = 0.7

    # Rate limits (per day)
    max_queries_per_day: int = 1000
    max_documents: int = 100
    max_file_size_mb: int = 10

    # Content policies
    allowed_domains: List[str] = []  # For web scraping
    blocked_keywords: List[str] = []  # Content filtering
    custom_instructions: Optional[str] = None  # Additional system prompt


class TenantConfig(BaseModel):
    """Complete tenant configuration."""

    tenant_id: UUID = Field(default_factory=uuid4)
    name: str
    industry: Industry
    status: TenantStatus = TenantStatus.TRIAL
    tier: TenantTier = TenantTier.FREE

    # Contact information
    contact_email: str
    contact_name: Optional[str] = None
    company_website: Optional[HttpUrl] = None

    # Settings
    settings: TenantSettings

    # Base URLs for scraping
    base_urls: List[HttpUrl] = []

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    trial_ends_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, str] = {}


class TenantAPIKey(BaseModel):
    """API key for tenant authentication."""

    key_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str  # Human-readable name for the key
    key_hash: str  # Hashed API key (never store plain text)
    prefix: str  # First 8 chars for identification (e.g., "pk_live_")

    # Permissions
    scopes: List[str] = ["chat", "upload", "query"]

    # Status
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    # Usage tracking
    usage_count: int = 0


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateTenantRequest(BaseModel):
    """Request to create a new tenant."""

    name: str = Field(..., min_length=1, max_length=100)
    industry: Industry
    contact_email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    contact_name: Optional[str] = None
    company_website: Optional[HttpUrl] = None

    # Optional settings override
    brand_name: Optional[str] = None
    brand_tone: Optional[BrandTone] = None
    default_language: Optional[str] = None


class UpdateTenantRequest(BaseModel):
    """Request to update tenant configuration."""

    name: Optional[str] = None
    status: Optional[TenantStatus] = None
    tier: Optional[TenantTier] = None
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    company_website: Optional[HttpUrl] = None
    settings: Optional[TenantSettings] = None
    base_urls: Optional[List[HttpUrl]] = None


class TenantResponse(BaseModel):
    """Response containing tenant information."""

    tenant_id: UUID
    name: str
    industry: Industry
    status: TenantStatus
    tier: TenantTier
    contact_email: str
    created_at: datetime
    settings: TenantSettings


class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: Optional[List[str]] = None
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    """Response containing API key information."""

    key_id: UUID
    tenant_id: UUID
    name: str
    api_key: str  # Plain text key (only shown once!)
    prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    warning: str = "Store this key securely. It will not be shown again."


class ListAPIKeysResponse(BaseModel):
    """Response listing API keys (without secrets)."""

    key_id: UUID
    name: str
    prefix: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]
