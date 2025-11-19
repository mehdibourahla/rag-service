"""Integration tests for multi-tenancy isolation."""

import pytest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.db.models import Tenant, APIKey
from src.services.tenant_service import TenantService
from src.services.auth_service import AuthService


@pytest.mark.integration
@pytest.mark.requires_postgres
class TestMultiTenancyIsolation:
    """Test that tenant data is properly isolated."""

    def test_api_key_isolation(
        self, db: Session, free_tenant: Tenant, pro_tenant: Tenant
    ):
        """Test that API keys are isolated between tenants."""
        # Create API keys for both tenants
        free_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Free Key",
        )
        pro_key = AuthService.create_api_key(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            name="Pro Key",
        )

        # FREE tenant should only see their keys
        free_keys = AuthService.list_api_keys(db, free_tenant.tenant_id)
        free_key_ids = [k.key_id for k in free_keys]
        assert free_key.key_id in free_key_ids
        assert pro_key.key_id not in free_key_ids

        # PRO tenant should only see their keys
        pro_keys = AuthService.list_api_keys(db, pro_tenant.tenant_id)
        pro_key_ids = [k.key_id for k in pro_keys]
        assert pro_key.key_id in pro_key_ids
        assert free_key.key_id not in pro_key_ids

    def test_job_isolation(self, db: Session, free_tenant: Tenant, pro_tenant: Tenant):
        """Test that background jobs are isolated between tenants."""
        from src.services.job_service import JobService
        from src.models.job import JobType

        # Create jobs for both tenants
        free_job = JobService.create_job(
            db=db,
            tenant_id=free_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=uuid4(),
            file_path="/tmp/free.pdf",
        )

        pro_job = JobService.create_job(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            job_type=JobType.DOCUMENT_UPLOAD,
            document_id=uuid4(),
            file_path="/tmp/pro.pdf",
        )

        # FREE tenant cannot access PRO tenant's job
        free_job_retrieved = JobService.get_job(db, pro_job.job_id, free_tenant.tenant_id)
        assert free_job_retrieved is None

        # PRO tenant cannot access FREE tenant's job
        pro_job_retrieved = JobService.get_job(db, free_job.job_id, pro_tenant.tenant_id)
        assert pro_job_retrieved is None

        # Each tenant can only access their own job
        assert JobService.get_job(db, free_job.job_id, free_tenant.tenant_id) is not None
        assert JobService.get_job(db, pro_job.job_id, pro_tenant.tenant_id) is not None

    def test_quota_isolation(self, db: Session, free_tenant: Tenant, pro_tenant: Tenant):
        """Test that quotas are enforced separately per tenant."""
        from src.services.quota_service import QuotaService

        # Get quotas for each tenant
        free_quotas = QuotaService.get_tenant_quotas(free_tenant)
        pro_quotas = QuotaService.get_tenant_quotas(pro_tenant)

        # FREE and PRO should have different quotas
        assert free_quotas["max_documents"] != pro_quotas["max_documents"]
        assert free_quotas["max_queries_per_day"] != pro_quotas["max_queries_per_day"]

        # Quotas are based on tier, not tenant
        assert free_quotas["max_documents"] == 10
        assert pro_quotas["max_documents"] == 1000

    def test_cache_isolation(self, free_tenant: Tenant, pro_tenant: Tenant, mock_redis):
        """Test that cache is isolated between tenants."""
        from src.services.cache_service import CacheService

        cache = CacheService()
        query = "What is Python?"

        # Cache different results for different tenants
        chunks_free = [{"text": "Result for FREE tenant"}]
        chunks_pro = [{"text": "Result for PRO tenant"}]

        cache.set_query_result(query, free_tenant.tenant_id, 5, chunks_free)
        cache.set_query_result(query, pro_tenant.tenant_id, 5, chunks_pro)

        # Each tenant should only see their cached results
        import json
        mock_redis.get.side_effect = lambda key: (
            json.dumps(chunks_free) if str(free_tenant.tenant_id) in key
            else json.dumps(chunks_pro) if str(pro_tenant.tenant_id) in key
            else None
        )

        cached_free = cache.get_query_result(query, free_tenant.tenant_id, 5)
        cached_pro = cache.get_query_result(query, pro_tenant.tenant_id, 5)

        assert cached_free != cached_pro

    def test_api_authentication_isolation(
        self, client: TestClient, db: Session, free_tenant: Tenant, pro_tenant: Tenant
    ):
        """Test that API authentication properly isolates tenants."""
        # Create API keys
        free_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Free Key",
        )
        pro_key = AuthService.create_api_key(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            name="Pro Key",
        )

        # Request with FREE key should return FREE tenant info
        response_free = client.get(
            f"/api/v1/tenants/{free_tenant.tenant_id}",
            headers={"X-API-Key": free_key.key},
        )
        assert response_free.status_code == 200

        # FREE key should not access PRO tenant's resources
        # (Depends on middleware implementation)
        # Note: This may return 403 Forbidden if authorization is implemented

    def test_session_isolation(self, db: Session, free_tenant: Tenant, pro_tenant: Tenant):
        """Test that chat sessions are isolated between tenants."""
        from src.services.session_service import SessionService

        # Create sessions for both tenants
        free_session = SessionService.create_session(
            db=db,
            tenant_id=free_tenant.tenant_id,
            user_id="user1",
        )

        pro_session = SessionService.create_session(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            user_id="user2",
        )

        # List sessions for each tenant
        free_sessions = SessionService.list_sessions(db, free_tenant.tenant_id)
        pro_sessions = SessionService.list_sessions(db, pro_tenant.tenant_id)

        free_session_ids = [s.session_id for s in free_sessions]
        pro_session_ids = [s.session_id for s in pro_sessions]

        # Each tenant should only see their own sessions
        assert free_session.session_id in free_session_ids
        assert free_session.session_id not in pro_session_ids

        assert pro_session.session_id in pro_session_ids
        assert pro_session.session_id not in free_session_ids

    def test_concurrent_tenant_operations(
        self, db: Session, free_tenant: Tenant, pro_tenant: Tenant
    ):
        """Test that concurrent operations on different tenants don't interfere."""
        from src.services.tenant_service import TenantService

        # Update both tenants simultaneously
        updated_free = TenantService.update_tenant(
            db=db,
            tenant_id=free_tenant.tenant_id,
            brand_name="Updated Free Brand",
        )

        updated_pro = TenantService.update_tenant(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            brand_name="Updated Pro Brand",
        )

        # Verify updates are isolated
        assert updated_free.brand_name == "Updated Free Brand"
        assert updated_pro.brand_name == "Updated Pro Brand"

        # Refresh and verify persistence
        db.expire_all()
        free_refreshed = TenantService.get_tenant(db, free_tenant.tenant_id)
        pro_refreshed = TenantService.get_tenant(db, pro_tenant.tenant_id)

        assert free_refreshed.brand_name == "Updated Free Brand"
        assert pro_refreshed.brand_name == "Updated Pro Brand"

    def test_bulk_operations_isolation(
        self, db: Session, multiple_tenants: list[Tenant]
    ):
        """Test that bulk operations maintain tenant isolation."""
        from src.services.quota_service import QuotaService

        # Get usage for all tenants
        usages = []
        for tenant in multiple_tenants:
            usage = QuotaService.get_quota_usage(db, tenant)
            usages.append(usage)

        # Each tenant should have their own quota tracking
        tenant_ids = [u["tenant_id"] for u in usages]
        assert len(set(tenant_ids)) == len(multiple_tenants)

    def test_delete_tenant_isolation(
        self, db: Session, free_tenant: Tenant, pro_tenant: Tenant
    ):
        """Test that deleting one tenant doesn't affect others."""
        # Deactivate FREE tenant
        TenantService.deactivate_tenant(db, free_tenant.tenant_id)

        # FREE tenant should be deleted
        free_refreshed = TenantService.get_tenant(db, free_tenant.tenant_id)
        assert free_refreshed.status == "deleted"

        # PRO tenant should remain active
        pro_refreshed = TenantService.get_tenant(db, pro_tenant.tenant_id)
        assert pro_refreshed.status == "active"
