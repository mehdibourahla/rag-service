"""Rate limiting middleware and utilities."""

import logging
from typing import Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.models.tenant import TenantTier

logger = logging.getLogger(__name__)


# Rate limits per tier (requests per time period)
TIER_RATE_LIMITS = {
    TenantTier.FREE: {
        "chat": "100/hour",  # 100 chat requests per hour
        "upload": "10/hour",  # 10 document uploads per hour
        "query": "200/hour",  # 200 queries per hour
        "default": "100/hour",
    },
    TenantTier.PRO: {
        "chat": "10000/hour",  # 10k chat requests per hour
        "upload": "1000/hour",  # 1k document uploads per hour
        "query": "20000/hour",  # 20k queries per hour
        "default": "10000/hour",
    },
}


def get_tenant_rate_limit(endpoint_type: str = "default") -> Callable:
    """
    Returns a function that determines rate limit based on tenant tier.

    Args:
        endpoint_type: Type of endpoint (chat, upload, query, default)

    Returns:
        Function that extracts rate limit string from request
    """

    def _get_limit(request: Request) -> str:
        # Get tenant from request state (set by tenant middleware)
        tenant = getattr(request.state, "tenant", None)

        if not tenant:
            # No tenant authenticated, use strictest limit
            return TIER_RATE_LIMITS[TenantTier.FREE]["default"]

        # Get tier-specific limits
        tier_limits = TIER_RATE_LIMITS.get(tenant.tier, TIER_RATE_LIMITS[TenantTier.FREE])

        # Get endpoint-specific limit or default
        limit = tier_limits.get(endpoint_type, tier_limits["default"])

        logger.debug(
            f"Rate limit for tenant {tenant.tenant_id} ({tenant.tier}): {limit} "
            f"(endpoint: {endpoint_type})"
        )

        return limit

    return _get_limit


def get_tenant_key(request: Request) -> str:
    """
    Generate rate limit key based on tenant ID.

    Falls back to IP address if no tenant is authenticated.
    """
    tenant = getattr(request.state, "tenant", None)

    if tenant:
        # Use tenant ID for authenticated requests
        return f"tenant:{tenant.tenant_id}"

    # Fall back to IP address for unauthenticated requests
    return f"ip:{get_remote_address(request)}"


# Initialize limiter with tenant-based key function
limiter = Limiter(key_func=get_tenant_key)
