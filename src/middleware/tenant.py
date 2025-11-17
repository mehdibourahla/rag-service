"""Tenant extraction middleware."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.db import get_db
from src.services.auth_service import AuthService


async def get_current_tenant_id(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> UUID:
    """
    Extract and validate tenant ID from request headers.

    Supports two authentication methods:
    1. X-API-Key header with API key (pk_live_...)
    2. Authorization header with Bearer token

    Args:
        authorization: Authorization header (optional)
        x_api_key: X-API-Key header (optional)
        db: Database session

    Returns:
        Tenant ID

    Raises:
        HTTPException: If authentication fails
    """
    # Try API key first (preferred for widget)
    if x_api_key:
        tenant_id = AuthService.get_tenant_from_api_key(db, x_api_key)
        if tenant_id:
            return tenant_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Try Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = AuthService.verify_access_token(token)
        if payload and "tenant_id" in payload:
            return UUID(payload["tenant_id"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # No valid authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication. Provide X-API-Key or Authorization header",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_api_key(
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> UUID:
    """
    Require a valid API key.

    Args:
        x_api_key: X-API-Key header
        db: Database session

    Returns:
        Tenant ID

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header"
        )

    tenant_id = AuthService.get_tenant_from_api_key(db, x_api_key)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return tenant_id


# Optional: Dependency for getting tenant ID but allowing anonymous access
async def get_optional_tenant_id(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[UUID]:
    """
    Get tenant ID if authentication is provided, but don't require it.

    Args:
        authorization: Authorization header (optional)
        x_api_key: X-API-Key header (optional)
        db: Database session

    Returns:
        Tenant ID if authenticated, None otherwise
    """
    try:
        return await get_current_tenant_id(authorization, x_api_key, db)
    except HTTPException:
        return None
