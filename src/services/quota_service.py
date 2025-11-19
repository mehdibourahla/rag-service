"""Quota management and enforcement service."""

import logging
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Tenant
from src.models.tenant import TenantTier

logger = logging.getLogger(__name__)

# Default quota limits per tier
DEFAULT_QUOTAS = {
    TenantTier.FREE: {
        "max_documents": 10,
        "max_file_size_mb": 10,
        "max_queries_per_day": 100,
        "max_storage_mb": 100,  # Total storage
    },
    TenantTier.PRO: {
        "max_documents": 1000,
        "max_file_size_mb": 50,
        "max_queries_per_day": 10000,
        "max_storage_mb": 10000,  # 10GB
    },
}


class QuotaExceededError(Exception):
    """Raised when a tenant exceeds their quota."""

    def __init__(self, message: str, quota_type: str, current: int, limit: int, tier: str):
        super().__init__(message)
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        self.tier = tier


class QuotaService:
    """Service for managing and enforcing tenant quotas."""

    @staticmethod
    def get_tenant_quotas(tenant: Tenant) -> Dict[str, int]:
        """
        Get quota limits for a tenant.

        Uses tenant-specific settings if available, otherwise falls back to tier defaults.

        Args:
            tenant: Tenant model instance

        Returns:
            dict with quota limits
        """
        # Get tier defaults
        tier_quotas = DEFAULT_QUOTAS.get(tenant.tier, DEFAULT_QUOTAS[TenantTier.FREE])

        # Override with tenant-specific settings if present
        settings = tenant.settings or {}

        return {
            "max_documents": settings.get("max_documents", tier_quotas["max_documents"]),
            "max_file_size_mb": settings.get("max_file_size_mb", tier_quotas["max_file_size_mb"]),
            "max_queries_per_day": settings.get("max_queries_per_day", tier_quotas["max_queries_per_day"]),
            "max_storage_mb": tier_quotas["max_storage_mb"],
        }

    @staticmethod
    def get_document_count(db: Session, tenant_id: UUID) -> int:
        """
        Get the number of documents for a tenant.

        This counts unique documents in the vector store via their metadata.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Number of documents
        """
        # Query Qdrant metadata table or use vector store count
        # For now, we'll use the vector store directly
        from src.api.dependencies import get_vector_store

        try:
            vector_store = get_vector_store()
            count = vector_store.count(tenant_id)
            logger.debug(f"Tenant {tenant_id} has {count} documents")
            return count
        except Exception as e:
            logger.error(f"Error counting documents for tenant {tenant_id}: {e}")
            return 0

    @staticmethod
    def check_document_quota(
        db: Session,
        tenant: Tenant,
        file_size_mb: Optional[float] = None
    ) -> None:
        """
        Check if tenant can upload a new document.

        Args:
            db: Database session
            tenant: Tenant model instance
            file_size_mb: Size of file to upload in MB (optional)

        Raises:
            QuotaExceededError: If quota exceeded
        """
        quotas = QuotaService.get_tenant_quotas(tenant)

        # Check document count
        current_documents = QuotaService.get_document_count(db, tenant.tenant_id)
        max_documents = quotas["max_documents"]

        if current_documents >= max_documents:
            raise QuotaExceededError(
                f"Document quota exceeded. Your {tenant.tier} tier allows {max_documents} documents. "
                f"You currently have {current_documents} documents. Please upgrade your plan or delete some documents.",
                quota_type="documents",
                current=current_documents,
                limit=max_documents,
                tier=tenant.tier,
            )

        # Check file size if provided
        if file_size_mb is not None:
            max_file_size = quotas["max_file_size_mb"]

            if file_size_mb > max_file_size:
                raise QuotaExceededError(
                    f"File size exceeds limit. Your {tenant.tier} tier allows files up to {max_file_size}MB. "
                    f"This file is {file_size_mb:.2f}MB. Please upgrade your plan or use a smaller file.",
                    quota_type="file_size",
                    current=int(file_size_mb),
                    limit=max_file_size,
                    tier=tenant.tier,
                )

        logger.info(
            f"Quota check passed for tenant {tenant.tenant_id}: "
            f"documents={current_documents}/{max_documents}, "
            f"file_size={file_size_mb or 0:.2f}/{quotas['max_file_size_mb']}MB"
        )

    @staticmethod
    def get_quota_usage(db: Session, tenant: Tenant) -> Dict[str, any]:
        """
        Get current quota usage for a tenant.

        Args:
            db: Database session
            tenant: Tenant model instance

        Returns:
            dict with quota usage and limits
        """
        quotas = QuotaService.get_tenant_quotas(tenant)
        current_documents = QuotaService.get_document_count(db, tenant.tenant_id)

        return {
            "tier": tenant.tier,
            "quotas": quotas,
            "usage": {
                "documents": {
                    "current": current_documents,
                    "limit": quotas["max_documents"],
                    "percentage": round((current_documents / quotas["max_documents"]) * 100, 2) if quotas["max_documents"] > 0 else 0,
                },
                "file_size_limit_mb": quotas["max_file_size_mb"],
                "queries_per_day_limit": quotas["max_queries_per_day"],
            },
            "warnings": QuotaService._get_quota_warnings(current_documents, quotas),
        }

    @staticmethod
    def _get_quota_warnings(current_documents: int, quotas: Dict[str, int]) -> list[str]:
        """Generate warning messages if approaching quota limits."""
        warnings = []

        # Warn at 80% usage
        doc_usage_pct = (current_documents / quotas["max_documents"]) * 100 if quotas["max_documents"] > 0 else 0

        if doc_usage_pct >= 100:
            warnings.append("Document quota limit reached. Please upgrade or delete documents.")
        elif doc_usage_pct >= 80:
            warnings.append(f"You have used {doc_usage_pct:.0f}% of your document quota. Consider upgrading soon.")

        return warnings
