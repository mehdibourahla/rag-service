"""Caching service for embeddings, queries, and results using Redis."""

import hashlib
import json
import logging
from typing import Any, List, Optional
from uuid import UUID

import redis
from redis import RedisError

from src.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-based caching service for RAG operations."""

    def __init__(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,  # Auto-decode to strings
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"Cache service initialized: {settings.redis_url}")
        except (RedisError, Exception) as e:
            logger.warning(f"Cache service disabled (Redis unavailable): {e}")
            self.enabled = False
            self.redis_client = None

    def _generate_key(self, prefix: str, *args: Any) -> str:
        """
        Generate a cache key from prefix and arguments.

        Args:
            prefix: Key prefix (e.g., "embed", "query", "rerank")
            *args: Values to hash

        Returns:
            Cache key string
        """
        # Create a deterministic hash of the arguments
        content = json.dumps(args, sort_keys=True, default=str)
        hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_value}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not self.enabled:
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except (RedisError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Cache get error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            serialized = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized)
            logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
            return True
        except (RedisError, TypeError, Exception) as e:
            logger.warning(f"Cache set error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except (RedisError, Exception) as e:
            logger.warning(f"Cache delete error for {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Pattern to match (e.g., "tenant:abc123:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cache DELETE pattern '{pattern}': {deleted} keys")
                return deleted
            return 0
        except (RedisError, Exception) as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    # ========================================================================
    # Embedding Cache
    # ========================================================================

    def get_embedding(self, text: str, model: str) -> Optional[List[float]]:
        """
        Get cached embedding for text.

        Args:
            text: Text to get embedding for
            model: Model name (e.g., "text-embedding-3-small")

        Returns:
            Embedding vector or None
        """
        key = self._generate_key("embed", text, model)
        return self.get(key)

    def set_embedding(
        self, text: str, model: str, embedding: List[float], ttl: int = 604800
    ) -> bool:
        """
        Cache embedding for text.

        Args:
            text: Text that was embedded
            model: Model name
            embedding: Embedding vector
            ttl: Time to live (default: 7 days)

        Returns:
            True if successful
        """
        key = self._generate_key("embed", text, model)
        return self.set(key, embedding, ttl=ttl)

    # ========================================================================
    # Query Result Cache
    # ========================================================================

    def get_query_result(
        self, query: str, tenant_id: UUID, top_k: int
    ) -> Optional[List[dict]]:
        """
        Get cached query results.

        Args:
            query: Search query
            tenant_id: Tenant ID
            top_k: Number of results

        Returns:
            Cached chunks or None
        """
        key = self._generate_key("query", str(tenant_id), query, top_k)
        return self.get(key)

    def set_query_result(
        self, query: str, tenant_id: UUID, top_k: int, chunks: List[dict], ttl: int = 3600
    ) -> bool:
        """
        Cache query results.

        Args:
            query: Search query
            tenant_id: Tenant ID
            top_k: Number of results
            chunks: Retrieved chunks (serialized)
            ttl: Time to live (default: 1 hour)

        Returns:
            True if successful
        """
        key = self._generate_key("query", str(tenant_id), query, top_k)
        return self.set(key, chunks, ttl=ttl)

    # ========================================================================
    # Reranking Cache
    # ========================================================================

    def get_rerank_result(
        self, query: str, chunk_ids: List[str]
    ) -> Optional[List[dict]]:
        """
        Get cached reranking results.

        Args:
            query: Search query
            chunk_ids: List of chunk IDs

        Returns:
            Reranked results or None
        """
        key = self._generate_key("rerank", query, sorted(chunk_ids))
        return self.get(key)

    def set_rerank_result(
        self, query: str, chunk_ids: List[str], results: List[dict], ttl: int = 3600
    ) -> bool:
        """
        Cache reranking results.

        Args:
            query: Search query
            chunk_ids: List of chunk IDs
            results: Reranked results
            ttl: Time to live (default: 1 hour)

        Returns:
            True if successful
        """
        key = self._generate_key("rerank", query, sorted(chunk_ids))
        return self.set(key, results, ttl=ttl)

    # ========================================================================
    # Cache Invalidation
    # ========================================================================

    def invalidate_tenant_cache(self, tenant_id: UUID) -> int:
        """
        Invalidate all cache entries for a tenant.

        Call this when tenant uploads or deletes documents.

        Args:
            tenant_id: Tenant ID

        Returns:
            Number of keys deleted
        """
        pattern = f"*{str(tenant_id)}*"
        return self.delete_pattern(pattern)

    def invalidate_embedding_cache(self) -> int:
        """
        Invalidate all embedding cache entries.

        Call this when embedding model changes.

        Returns:
            Number of keys deleted
        """
        return self.delete_pattern("embed:*")

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict with cache stats
        """
        if not self.enabled:
            return {"enabled": False, "message": "Cache disabled"}

        try:
            info = self.redis_client.info("stats")
            return {
                "enabled": True,
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0)
                    / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                    * 100
                ),
                "total_keys": self.redis_client.dbsize(),
            }
        except (RedisError, Exception) as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"enabled": True, "error": str(e)}


# Global cache service instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get or create the global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
