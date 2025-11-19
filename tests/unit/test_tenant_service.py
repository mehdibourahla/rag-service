"""Unit tests for TenantService."""

import pytest
from uuid import uuid4

from sqlalchemy.orm import Session

from src.db.models import Tenant
from src.models.tenant import TenantTier
from src.services.tenant_service import TenantService


@pytest.mark.unit
class TestTenantService:
    """Test TenantService CRUD operations."""

    def test_create_tenant(self, db: Session):
        """Test creating a new tenant."""
        tenant = TenantService.create_tenant(
            db=db,
            name="Test Company",
            tier=TenantTier.FREE,
            brand_name="TestBrand",
            brand_tone="professional",
            language="en",
            industry="technology",
            contact_email="test@test.com",
        )

        assert tenant.tenant_id is not None
        assert tenant.name == "Test Company"
        assert tenant.tier == TenantTier.FREE
        assert tenant.brand_name == "TestBrand"
        assert tenant.status == "active"
        assert tenant.contact_email == "test@test.com"

    def test_get_tenant(self, db: Session, free_tenant: Tenant):
        """Test retrieving a tenant by ID."""
        tenant = TenantService.get_tenant(db, free_tenant.tenant_id)

        assert tenant is not None
        assert tenant.tenant_id == free_tenant.tenant_id
        assert tenant.name == free_tenant.name

    def test_get_nonexistent_tenant(self, db: Session):
        """Test retrieving a non-existent tenant returns None."""
        fake_id = uuid4()
        tenant = TenantService.get_tenant(db, fake_id)

        assert tenant is None

    def test_get_tenant_by_name(self, db: Session, free_tenant: Tenant):
        """Test retrieving a tenant by name."""
        tenant = TenantService.get_tenant_by_name(db, free_tenant.name)

        assert tenant is not None
        assert tenant.tenant_id == free_tenant.tenant_id

    def test_update_tenant(self, db: Session, free_tenant: Tenant):
        """Test updating tenant information."""
        new_brand_name = "Updated Brand"
        new_tone = "friendly"

        updated_tenant = TenantService.update_tenant(
            db=db,
            tenant_id=free_tenant.tenant_id,
            brand_name=new_brand_name,
            brand_tone=new_tone,
        )

        assert updated_tenant.brand_name == new_brand_name
        assert updated_tenant.brand_tone == new_tone
        # Original values unchanged
        assert updated_tenant.name == free_tenant.name
        assert updated_tenant.tier == free_tenant.tier

    def test_upgrade_tenant_tier(self, db: Session, free_tenant: Tenant):
        """Test upgrading a tenant from FREE to PRO."""
        upgraded_tenant = TenantService.update_tenant(
            db=db,
            tenant_id=free_tenant.tenant_id,
            tier=TenantTier.PRO,
        )

        assert upgraded_tenant.tier == TenantTier.PRO
        assert upgraded_tenant.tenant_id == free_tenant.tenant_id

    def test_deactivate_tenant(self, db: Session, free_tenant: Tenant):
        """Test deactivating a tenant (soft delete)."""
        TenantService.deactivate_tenant(db, free_tenant.tenant_id)

        tenant = TenantService.get_tenant(db, free_tenant.tenant_id)
        assert tenant.status == "deleted"
        assert tenant.deleted_at is not None

    def test_list_tenants(self, db: Session, multiple_tenants: list[Tenant]):
        """Test listing all tenants."""
        tenants = TenantService.list_tenants(db)

        assert len(tenants) >= len(multiple_tenants)
        tenant_ids = [t.tenant_id for t in tenants]
        for tenant in multiple_tenants:
            assert tenant.tenant_id in tenant_ids

    def test_list_tenants_with_filters(self, db: Session, multiple_tenants: list[Tenant]):
        """Test listing tenants with filters."""
        # Filter by tier
        free_tenants = [t for t in multiple_tenants if t.tier == TenantTier.FREE]
        if free_tenants:
            filtered = TenantService.list_tenants(db, tier=TenantTier.FREE)
            assert all(t.tier == TenantTier.FREE for t in filtered)

    def test_update_settings(self, db: Session, free_tenant: Tenant):
        """Test updating tenant settings JSON."""
        settings = {
            "max_retries": 3,
            "timeout": 30,
            "custom_prompt": "You are a helpful assistant",
        }

        updated_tenant = TenantService.update_tenant(
            db=db,
            tenant_id=free_tenant.tenant_id,
            settings=settings,
        )

        assert updated_tenant.settings == settings
        assert updated_tenant.settings["max_retries"] == 3

    def test_tenant_isolation(self, db: Session, multiple_tenants: list[Tenant]):
        """Test that tenants are properly isolated."""
        tenant1 = multiple_tenants[0]
        tenant2 = multiple_tenants[1]

        # Each tenant should have unique ID
        assert tenant1.tenant_id != tenant2.tenant_id

        # Updating one tenant should not affect another
        TenantService.update_tenant(
            db=db,
            tenant_id=tenant1.tenant_id,
            brand_name="Updated Brand 1",
        )

        refreshed_tenant2 = TenantService.get_tenant(db, tenant2.tenant_id)
        assert refreshed_tenant2.brand_name != "Updated Brand 1"
