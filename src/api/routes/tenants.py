"""Tenant management API routes."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db import get_db
from src.db.models import Tenant
from src.models.tenant import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateTenantRequest,
    ListAPIKeysResponse,
    TenantResponse,
    TenantSettings,
    UpdateTenantRequest,
)
from src.services import TenantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    db: Session = Depends(get_db)
) -> TenantResponse:
    """
    Create a new tenant.

    Args:
        request: Tenant creation request
        db: Database session

    Returns:
        Created tenant

    Raises:
        HTTPException: If email already exists
    """
    try:
        tenant = TenantService.create_tenant(db, request)

        # Parse settings from JSON
        settings = TenantSettings(**tenant.settings) if tenant.settings else TenantSettings(
            brand_name=tenant.name
        )

        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            industry=tenant.industry,
            status=tenant.status,
            tier=tenant.tier,
            contact_email=tenant.contact_email,
            created_at=tenant.created_at,
            settings=settings,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant"
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db)
) -> TenantResponse:
    """
    Get tenant by ID.

    Args:
        tenant_id: Tenant ID
        db: Database session

    Returns:
        Tenant information

    Raises:
        HTTPException: If tenant not found
    """
    tenant = TenantService.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    settings = TenantSettings(**tenant.settings) if tenant.settings else TenantSettings(
        brand_name=tenant.name
    )

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        industry=tenant.industry,
        status=tenant.status,
        tier=tenant.tier,
        contact_email=tenant.contact_email,
        created_at=tenant.created_at,
        settings=settings,
    )


@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[TenantResponse]:
    """
    List all tenants.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of tenants
    """
    tenants = TenantService.list_tenants(db, skip=skip, limit=limit)

    result = []
    for tenant in tenants:
        settings = TenantSettings(**tenant.settings) if tenant.settings else TenantSettings(
            brand_name=tenant.name
        )
        result.append(TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            industry=tenant.industry,
            status=tenant.status,
            tier=tenant.tier,
            contact_email=tenant.contact_email,
            created_at=tenant.created_at,
            settings=settings,
        ))

    return result


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    request: UpdateTenantRequest,
    db: Session = Depends(get_db)
) -> TenantResponse:
    """
    Update tenant.

    Args:
        tenant_id: Tenant ID
        request: Update request
        db: Database session

    Returns:
        Updated tenant

    Raises:
        HTTPException: If tenant not found
    """
    tenant = TenantService.update_tenant(db, tenant_id, request)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    settings = TenantSettings(**tenant.settings) if tenant.settings else TenantSettings(
        brand_name=tenant.name
    )

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        industry=tenant.industry,
        status=tenant.status,
        tier=tenant.tier,
        contact_email=tenant.contact_email,
        created_at=tenant.created_at,
        settings=settings,
    )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete tenant (soft delete).

    Args:
        tenant_id: Tenant ID
        db: Database session

    Raises:
        HTTPException: If tenant not found
    """
    success = TenantService.delete_tenant(db, tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )


# API Key Management

@router.post("/{tenant_id}/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    tenant_id: UUID,
    request: CreateAPIKeyRequest,
    db: Session = Depends(get_db)
) -> APIKeyResponse:
    """
    Create a new API key for a tenant.

    Args:
        tenant_id: Tenant ID
        request: API key creation request
        db: Database session

    Returns:
        API key information (with plain text key - shown only once!)

    Raises:
        HTTPException: If tenant not found
    """
    try:
        api_key_record, plain_key = TenantService.create_api_key(db, tenant_id, request)

        return APIKeyResponse(
            key_id=api_key_record.key_id,
            tenant_id=api_key_record.tenant_id,
            name=api_key_record.name,
            api_key=plain_key,  # Plain text key - only shown once!
            prefix=api_key_record.prefix,
            scopes=api_key_record.scopes,
            created_at=api_key_record.created_at,
            expires_at=api_key_record.expires_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.get("/{tenant_id}/api-keys", response_model=List[ListAPIKeysResponse])
async def list_api_keys(
    tenant_id: UUID,
    db: Session = Depends(get_db)
) -> List[ListAPIKeysResponse]:
    """
    List all API keys for a tenant.

    Args:
        tenant_id: Tenant ID
        db: Database session

    Returns:
        List of API keys (without secrets)
    """
    api_keys = TenantService.list_api_keys(db, tenant_id)

    return [
        ListAPIKeysResponse(
            key_id=key.key_id,
            name=key.name,
            prefix=key.prefix,
            scopes=key.scopes,
            is_active=key.is_active,
            last_used_at=key.last_used_at,
            created_at=key.created_at,
            expires_at=key.expires_at,
        )
        for key in api_keys
    ]


@router.delete("/{tenant_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    tenant_id: UUID,
    key_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Revoke (deactivate) an API key.

    Args:
        tenant_id: Tenant ID
        key_id: API key ID
        db: Database session

    Raises:
        HTTPException: If API key not found
    """
    success = TenantService.revoke_api_key(db, tenant_id, key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found for tenant {tenant_id}"
        )


@router.get("/{tenant_id}/stats")
async def get_tenant_stats(
    tenant_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get statistics for a tenant.

    Args:
        tenant_id: Tenant ID
        db: Database session

    Returns:
        Tenant statistics

    Raises:
        HTTPException: If tenant not found
    """
    tenant = TenantService.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    stats = TenantService.get_tenant_stats(db, tenant_id)
    return stats
