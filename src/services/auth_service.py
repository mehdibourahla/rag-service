"""Authentication and authorization service."""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models import TenantAPIKey

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"


class AuthService:
    """Service for authentication and API key management."""

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key for secure storage.

        Args:
            api_key: Plain text API key

        Returns:
            Hashed API key
        """
        return pwd_context.hash(api_key)

    @staticmethod
    def verify_api_key(plain_key: str, hashed_key: str) -> bool:
        """
        Verify an API key against its hash.

        Args:
            plain_key: Plain text API key
            hashed_key: Hashed API key from database

        Returns:
            True if key matches, False otherwise
        """
        return pwd_context.verify(plain_key, hashed_key)

    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """
        Generate a new API key and its prefix.

        Returns:
            Tuple of (full_api_key, prefix)
        """
        # Generate random API key
        api_key = f"pk_live_{secrets.token_urlsafe(32)}"
        prefix = api_key[:12]  # First 12 chars for identification
        return api_key, prefix

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_access_token(token: str) -> Optional[dict]:
        """
        Verify and decode a JWT access token.

        Args:
            token: JWT token to verify

        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    @staticmethod
    def authenticate_api_key(db: Session, api_key: str) -> Optional[TenantAPIKey]:
        """
        Authenticate an API key and return the associated tenant API key record.

        Args:
            db: Database session
            api_key: Plain text API key

        Returns:
            TenantAPIKey record if authenticated, None otherwise
        """
        # Extract prefix from key
        prefix = api_key[:12]

        # Find all API keys with this prefix
        api_keys = db.query(TenantAPIKey).filter(
            TenantAPIKey.prefix == prefix,
            TenantAPIKey.is_active == True  # noqa: E712
        ).all()

        # Verify the key hash
        for key_record in api_keys:
            if AuthService.verify_api_key(api_key, key_record.key_hash):
                # Check if expired
                if key_record.expires_at and key_record.expires_at < datetime.utcnow():
                    return None

                # Update last used timestamp and usage count
                key_record.last_used_at = datetime.utcnow()
                key_record.usage_count += 1
                db.commit()

                return key_record

        return None

    @staticmethod
    def get_tenant_from_api_key(db: Session, api_key: str) -> Optional[UUID]:
        """
        Get tenant ID from an API key.

        Args:
            db: Database session
            api_key: Plain text API key

        Returns:
            Tenant ID if valid, None otherwise
        """
        key_record = AuthService.authenticate_api_key(db, api_key)
        return key_record.tenant_id if key_record else None
