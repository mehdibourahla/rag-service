"""Unit tests for AuthService."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from src.db.models import TenantAPIKey as APIKey, Tenant
from src.services.auth_service import AuthService


@pytest.mark.unit
class TestAuthService:
    """Test AuthService for API key management and authentication."""

    def test_create_api_key(self, db: Session, free_tenant: Tenant):
        """Test creating a new API key."""
        api_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Test API Key",
            scopes=["chat", "upload"],
            environment="test",
        )

        assert api_key.key_id is not None
        assert api_key.tenant_id == free_tenant.tenant_id
        assert api_key.name == "Test API Key"
        assert api_key.scopes == ["chat", "upload"]
        assert api_key.environment == "test"
        assert api_key.key.startswith("pk_test_")
        assert api_key.is_active is True

    def test_api_key_prefix_live(self, db: Session, free_tenant: Tenant):
        """Test that live API keys have correct prefix."""
        api_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Live Key",
            environment="live",
        )

        assert api_key.key.startswith("pk_live_")

    def test_validate_api_key_success(self, db: Session, api_key_free: APIKey):
        """Test successful API key validation."""
        raw_key = api_key_free.raw_key
        validated_key = AuthService.validate_api_key(db, raw_key)

        assert validated_key is not None
        assert validated_key.key_id == api_key_free.key_id
        assert validated_key.tenant_id == api_key_free.tenant_id

    def test_validate_invalid_api_key(self, db: Session):
        """Test validation of invalid API key."""
        fake_key = "pk_test_invalid_key_123456"
        validated_key = AuthService.validate_api_key(db, fake_key)

        assert validated_key is None

    def test_validate_inactive_api_key(self, db: Session, api_key_free: APIKey):
        """Test that inactive API keys cannot be validated."""
        # Deactivate the key
        api_key_free.is_active = False
        db.commit()

        validated_key = AuthService.validate_api_key(db, api_key_free.raw_key)
        assert validated_key is None

    def test_validate_expired_api_key(self, db: Session, free_tenant: Tenant):
        """Test that expired API keys cannot be validated."""
        # Create key with past expiration
        api_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Expired Key",
            expires_in_days=1,
        )
        raw_key = api_key.key

        # Manually set expiration to past
        api_key_db = db.query(APIKey).filter(APIKey.key_id == api_key.key_id).first()
        api_key_db.expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit()

        validated_key = AuthService.validate_api_key(db, raw_key)
        assert validated_key is None

    def test_revoke_api_key(self, db: Session, api_key_free: APIKey):
        """Test revoking an API key."""
        AuthService.revoke_api_key(db, api_key_free.key_id)

        # Key should now be inactive
        key = db.query(APIKey).filter(APIKey.key_id == api_key_free.key_id).first()
        assert key.is_active is False

        # Validation should fail
        validated_key = AuthService.validate_api_key(db, api_key_free.raw_key)
        assert validated_key is None

    def test_list_api_keys(self, db: Session, free_tenant: Tenant):
        """Test listing API keys for a tenant."""
        # Create multiple keys
        for i in range(3):
            AuthService.create_api_key(
                db=db,
                tenant_id=free_tenant.tenant_id,
                name=f"Key {i}",
            )

        keys = AuthService.list_api_keys(db, free_tenant.tenant_id)
        assert len(keys) >= 3

    def test_api_key_usage_tracking(self, db: Session, api_key_free: APIKey):
        """Test that API key usage is tracked."""
        raw_key = api_key_free.raw_key

        # Validate key multiple times
        for _ in range(3):
            AuthService.validate_api_key(db, raw_key)

        # Check usage count
        key = db.query(APIKey).filter(APIKey.key_id == api_key_free.key_id).first()
        assert key.usage_count == 3
        assert key.last_used_at is not None

    def test_api_key_scopes(self, db: Session, free_tenant: Tenant):
        """Test creating API keys with different scopes."""
        # Chat-only key
        chat_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Chat Key",
            scopes=["chat"],
        )
        assert chat_key.scopes == ["chat"]

        # Upload-only key
        upload_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Upload Key",
            scopes=["upload"],
        )
        assert upload_key.scopes == ["upload"]

        # All scopes key
        all_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="All Scopes",
            scopes=["chat", "upload", "query"],
        )
        assert set(all_key.scopes) == {"chat", "upload", "query"}

    def test_api_key_hashing(self, db: Session, free_tenant: Tenant):
        """Test that API keys are properly hashed in database."""
        api_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Test Key",
        )
        raw_key = api_key.key

        # Retrieve from database
        db_key = db.query(APIKey).filter(APIKey.key_id == api_key.key_id).first()

        # Stored hash should be different from raw key
        assert db_key.key_hash != raw_key
        # But validation should still work
        assert AuthService.validate_api_key(db, raw_key) is not None

    def test_tenant_isolation_api_keys(
        self, db: Session, free_tenant: Tenant, pro_tenant: Tenant
    ):
        """Test that API keys are isolated by tenant."""
        # Create keys for both tenants
        free_key = AuthService.create_api_key(
            db=db,
            tenant_id=free_tenant.tenant_id,
            name="Free Tenant Key",
        )
        pro_key = AuthService.create_api_key(
            db=db,
            tenant_id=pro_tenant.tenant_id,
            name="Pro Tenant Key",
        )

        # Each tenant should only see their own keys
        free_keys = AuthService.list_api_keys(db, free_tenant.tenant_id)
        pro_keys = AuthService.list_api_keys(db, pro_tenant.tenant_id)

        free_key_ids = [k.key_id for k in free_keys]
        pro_key_ids = [k.key_id for k in pro_keys]

        assert free_key.key_id in free_key_ids
        assert free_key.key_id not in pro_key_ids

        assert pro_key.key_id in pro_key_ids
        assert pro_key.key_id not in free_key_ids
