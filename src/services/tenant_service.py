"""Tenant management service."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Tenant, TenantAPIKey
from src.models.tenant import (
    CreateAPIKeyRequest,
    CreateTenantRequest,
    TenantSettings,
    UpdateTenantRequest,
)
from src.services.auth_service import AuthService


class TenantService:
    """Service for tenant management operations."""

    @staticmethod
    def create_tenant(db: Session, request: CreateTenantRequest) -> Tenant:
        """
        Create a new tenant.

        Args:
            db: Database session
            request: Tenant creation request

        Returns:
            Created tenant

        Raises:
            ValueError: If email already exists (excluding soft-deleted tenants)
        """
        # Check if email already exists (excluding soft-deleted tenants)
        from src.models.tenant import TenantStatus
        existing = db.query(Tenant).filter(
            Tenant.contact_email == request.contact_email,
            Tenant.status != TenantStatus.DELETED
        ).first()
        if existing:
            raise ValueError(f"Tenant with email {request.contact_email} already exists")

        # Create default settings
        settings = TenantSettings(
            brand_name=request.brand_name or request.name,
            brand_tone=request.brand_tone or "professional",
            default_language=request.default_language or "en",
            supported_languages=[request.default_language or "en"],
        )

        # Create tenant
        tenant = Tenant(
            name=request.name,
            industry=request.industry,
            contact_email=request.contact_email,
            contact_name=request.contact_name,
            company_website=str(request.company_website) if request.company_website else None,
            settings=settings.model_dump(),
        )

        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        return tenant

    @staticmethod
    def get_tenant(db: Session, tenant_id: UUID) -> Optional[Tenant]:
        """
        Get a tenant by ID.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Tenant if found, None otherwise
        """
        return db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

    @staticmethod
    def get_tenant_by_email(db: Session, email: str) -> Optional[Tenant]:
        """
        Get a tenant by contact email.

        Args:
            db: Database session
            email: Contact email

        Returns:
            Tenant if found, None otherwise
        """
        return db.query(Tenant).filter(Tenant.contact_email == email).first()

    @staticmethod
    def list_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[Tenant]:
        """
        List all tenants.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of tenants
        """
        return db.query(Tenant).offset(skip).limit(limit).all()

    @staticmethod
    def update_tenant(db: Session, tenant_id: UUID, request: UpdateTenantRequest) -> Optional[Tenant]:
        """
        Update a tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID
            request: Update request

        Returns:
            Updated tenant if found, None otherwise
        """
        tenant = TenantService.get_tenant(db, tenant_id)
        if not tenant:
            return None

        # Update fields if provided
        if request.name is not None:
            tenant.name = request.name
        if request.status is not None:
            tenant.status = request.status
        if request.tier is not None:
            tenant.tier = request.tier
        if request.contact_email is not None:
            tenant.contact_email = request.contact_email
        if request.contact_name is not None:
            tenant.contact_name = request.contact_name
        if request.company_website is not None:
            tenant.company_website = str(request.company_website)
        if request.settings is not None:
            tenant.settings = request.settings.model_dump()
        if request.base_urls is not None:
            tenant.base_urls = [str(url) for url in request.base_urls]

        tenant.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(tenant)

        return tenant

    @staticmethod
    def delete_tenant(db: Session, tenant_id: UUID) -> bool:
        """
        Delete a tenant (soft delete by setting status to DELETED).

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        tenant = TenantService.get_tenant(db, tenant_id)
        if not tenant:
            return False

        # Soft delete
        from src.models.tenant import TenantStatus
        tenant.status = TenantStatus.DELETED
        tenant.updated_at = datetime.utcnow()

        db.commit()

        return True

    # API Key Management

    @staticmethod
    def create_api_key(
        db: Session,
        tenant_id: UUID,
        request: CreateAPIKeyRequest
    ) -> tuple[TenantAPIKey, str]:
        """
        Create a new API key for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID
            request: API key creation request

        Returns:
            Tuple of (API key record, plain text API key)

        Raises:
            ValueError: If tenant not found
        """
        # Verify tenant exists
        tenant = TenantService.get_tenant(db, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Generate API key
        api_key, prefix = AuthService.generate_api_key()
        key_hash = AuthService.hash_api_key(api_key)

        # Calculate expiration if specified
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

        # Create API key record
        api_key_record = TenantAPIKey(
            tenant_id=tenant_id,
            name=request.name,
            key_hash=key_hash,
            prefix=prefix,
            scopes=request.scopes or ["chat", "upload", "query"],
            expires_at=expires_at,
        )

        db.add(api_key_record)
        db.commit()
        db.refresh(api_key_record)

        return api_key_record, api_key

    @staticmethod
    def list_api_keys(db: Session, tenant_id: UUID) -> List[TenantAPIKey]:
        """
        List all API keys for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            List of API keys
        """
        return db.query(TenantAPIKey).filter(
            TenantAPIKey.tenant_id == tenant_id
        ).all()

    @staticmethod
    def revoke_api_key(db: Session, tenant_id: UUID, key_id: UUID) -> bool:
        """
        Revoke (deactivate) an API key.

        Args:
            db: Database session
            tenant_id: Tenant ID
            key_id: API key ID

        Returns:
            True if revoked, False if not found
        """
        api_key = db.query(TenantAPIKey).filter(
            TenantAPIKey.key_id == key_id,
            TenantAPIKey.tenant_id == tenant_id
        ).first()

        if not api_key:
            return False

        api_key.is_active = False
        db.commit()

        return True

    @staticmethod
    def get_tenant_stats(db: Session, tenant_id: UUID) -> dict:
        """
        Get statistics for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Dictionary of statistics
        """
        from src.db.models import ChatSession, Message

        # Count active API keys
        active_keys = db.query(TenantAPIKey).filter(
            TenantAPIKey.tenant_id == tenant_id,
            TenantAPIKey.is_active == True  # noqa: E712
        ).count()

        # Count sessions
        total_sessions = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant_id
        ).count()

        # Count messages
        total_messages = db.query(Message).filter(
            Message.tenant_id == tenant_id
        ).count()

        return {
            "tenant_id": str(tenant_id),
            "active_api_keys": active_keys,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
        }
