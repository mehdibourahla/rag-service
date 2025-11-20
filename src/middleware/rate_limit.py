"""Rate limiting middleware and utilities."""

import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, Callable, Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.models.tenant import TenantTier

if TYPE_CHECKING:
    from src.db.models import Tenant

logger = logging.getLogger(__name__)

# Context variable to store current request
_request_context: ContextVar[Optional[Request]] = ContextVar("request_context", default=None)


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
    Returns a rate limit function for the specified endpoint type.

    SlowAPI expects limit providers to have no parameters, so we use a closure
    to capture the endpoint type and access the request from the current context.

    Args:
        endpoint_type: Type of endpoint (chat, upload, query, default)

    Returns:
        Callable with no parameters that returns rate limit string
    """
    def rate_limit_provider() -> str:
        """
        No-argument callable that returns rate limit based on tenant tier.

        Returns:
            Rate limit string (e.g., "100/hour")
        """
        # Get request from context variable
        request = _request_context.get()

        # Get tenant from request state (set by tenant middleware)
        tenant: Optional[Tenant] = getattr(request.state, "tenant", None) if request else None

        if not tenant:
            # No tenant authenticated, use strictest limit
            limit = TIER_RATE_LIMITS[TenantTier.FREE][endpoint_type]
            if not limit:
                limit = TIER_RATE_LIMITS[TenantTier.FREE]["default"]
            return limit

        # Get tier-specific limits
        tier_limits = TIER_RATE_LIMITS.get(tenant.tier, TIER_RATE_LIMITS[TenantTier.FREE])

        # Get endpoint-specific limit or default
        limit = tier_limits.get(endpoint_type, tier_limits["default"])

        logger.debug(
            f"Rate limit for tenant {tenant.tenant_id} ({tenant.tier}): {limit} "
            f"(endpoint: {endpoint_type})"
        )

        return limit

    return rate_limit_provider


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


def set_request_context(request: Request) -> None:
    """
    Set the current request in the context variable.

    This should be called by middleware before rate limiting is checked.

    Args:
        request: The current FastAPI request
    """
    _request_context.set(request)
