"""Unit tests for CacheService."""

import pytest
from uuid import uuid4

from src.services.cache_service import CacheService


@pytest.mark.unit
@pytest.mark.requires_redis
class TestCacheService:
    """Test CacheService for Redis-based caching."""

    @pytest.fixture
    def cache_service(self, mock_redis):
        """Create a CacheService instance with mocked Redis."""
        return CacheService()

    def test_cache_service_initialization(self, cache_service):
        """Test that CacheService initializes correctly."""
        assert cache_service.enabled is True
        assert cache_service.redis_client is not None

    def test_set_and_get_embedding(self, cache_service, mock_redis):
        """Test caching and retrieving an embedding."""
        text = "Test text for embedding"
        model = "text-embedding-3-small"
        embedding = [0.1] * 1536

        # Mock Redis responses
        mock_redis.get.return_value = None  # Cache miss first
        mock_redis.setex.return_value = True

        # Set embedding
        success = cache_service.set_embedding(text, model, embedding)
        assert success is True

        # Mock cache hit
        import json
        mock_redis.get.return_value = json.dumps(embedding)

        # Get embedding
        cached = cache_service.get_embedding(text, model)
        assert cached == embedding

    def test_embedding_cache_miss(self, cache_service, mock_redis):
        """Test cache miss for embedding."""
        mock_redis.get.return_value = None

        embedding = cache_service.get_embedding("nonexistent text", "test-model")
        assert embedding is None

    def test_set_and_get_query_result(self, cache_service, mock_redis):
        """Test caching and retrieving query results."""
        query = "What is Python?"
        tenant_id = uuid4()
        top_k = 5
        chunks = [
            {"chunk_id": str(uuid4()), "text": "Python is a programming language"},
            {"chunk_id": str(uuid4()), "text": "Python is high-level"},
        ]

        # Mock cache miss then hit
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Set query result
        success = cache_service.set_query_result(query, tenant_id, top_k, chunks)
        assert success is True

        # Mock cache hit
        import json
        mock_redis.get.return_value = json.dumps(chunks)

        # Get query result
        cached = cache_service.get_query_result(query, tenant_id, top_k)
        assert cached == chunks

    def test_set_and_get_rerank_result(self, cache_service, mock_redis):
        """Test caching and retrieving reranking results."""
        query = "Python tutorial"
        chunk_ids = [str(uuid4()) for _ in range(5)]
        results = [
            {"chunk_id": chunk_ids[0], "score": 0.95},
            {"chunk_id": chunk_ids[1], "score": 0.87},
        ]

        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Set rerank result
        success = cache_service.set_rerank_result(query, chunk_ids, results)
        assert success is True

        # Mock cache hit
        import json
        mock_redis.get.return_value = json.dumps(results)

        # Get rerank result
        cached = cache_service.get_rerank_result(query, chunk_ids)
        assert cached == results

    def test_delete_cache_key(self, cache_service, mock_redis):
        """Test deleting a cache key."""
        mock_redis.delete.return_value = 1

        key = "test:key:123"
        success = cache_service.delete(key)
        assert success is True

    def test_delete_pattern(self, cache_service, mock_redis):
        """Test deleting keys matching a pattern."""
        # Mock keys matching pattern
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.delete.return_value = 3

        deleted_count = cache_service.delete_pattern("test:*")
        assert deleted_count == 3

    def test_invalidate_tenant_cache(self, cache_service, mock_redis):
        """Test invalidating all cache for a tenant."""
        tenant_id = uuid4()

        # Mock tenant cache keys
        mock_redis.keys.return_value = [
            f"query:{tenant_id}:abc123",
            f"query:{tenant_id}:def456",
        ]
        mock_redis.delete.return_value = 2

        deleted = cache_service.invalidate_tenant_cache(tenant_id)
        assert deleted == 2

    def test_invalidate_embedding_cache(self, cache_service, mock_redis):
        """Test invalidating all embedding cache entries."""
        # Mock embedding cache keys
        mock_redis.keys.return_value = [
            "embed:hash1",
            "embed:hash2",
            "embed:hash3",
        ]
        mock_redis.delete.return_value = 3

        deleted = cache_service.invalidate_embedding_cache()
        assert deleted == 3

    def test_cache_key_generation_consistency(self, cache_service):
        """Test that cache keys are generated consistently."""
        text = "Test text"
        model = "test-model"

        # Same inputs should generate same key
        key1 = cache_service._generate_key("embed", text, model)
        key2 = cache_service._generate_key("embed", text, model)
        assert key1 == key2

        # Different inputs should generate different keys
        key3 = cache_service._generate_key("embed", "Different text", model)
        assert key1 != key3

    def test_cache_ttl_settings(self, cache_service, mock_redis):
        """Test that different cache types have appropriate TTLs."""
        # Embedding cache - 7 days
        cache_service.set_embedding("test", "model", [0.1], ttl=604800)
        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 604800  # 7 days in seconds

        # Query cache - 1 hour (default)
        cache_service.set_query_result("query", uuid4(), 5, [], ttl=3600)
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # 1 hour in seconds

    def test_cache_graceful_degradation(self, mocker):
        """Test that cache service degrades gracefully when Redis unavailable."""
        # Mock Redis connection failure
        mocker.patch("redis.from_url", side_effect=Exception("Redis unavailable"))

        cache = CacheService()
        assert cache.enabled is False

        # Operations should not raise errors
        assert cache.get_embedding("test", "model") is None
        assert cache.set_embedding("test", "model", [0.1]) is False
        assert cache.delete("key") is False

    def test_cache_statistics(self, cache_service, mock_redis):
        """Test getting cache statistics."""
        # Mock Redis info response
        mock_redis.info.return_value = {
            "keyspace_hits": 100,
            "keyspace_misses": 20,
        }
        mock_redis.dbsize.return_value = 50

        stats = cache_service.get_stats()

        assert stats["enabled"] is True
        assert stats["keyspace_hits"] == 100
        assert stats["keyspace_misses"] == 20
        assert stats["total_keys"] == 50
        assert "hit_rate" in stats

    def test_cache_hit_rate_calculation(self, cache_service, mock_redis):
        """Test cache hit rate calculation."""
        mock_redis.info.return_value = {
            "keyspace_hits": 80,
            "keyspace_misses": 20,
        }
        mock_redis.dbsize.return_value = 100

        stats = cache_service.get_stats()
        # Hit rate = 80 / (80 + 20) = 80%
        assert stats["hit_rate"] == 80.0

    def test_cache_isolation_between_tenants(self, cache_service, mock_redis):
        """Test that cache is isolated between tenants."""
        tenant1 = uuid4()
        tenant2 = uuid4()
        query = "same query"

        # Mock different cached results for different tenants
        chunks1 = [{"text": "Result for tenant 1"}]
        chunks2 = [{"text": "Result for tenant 2"}]

        import json

        def mock_get(key):
            if str(tenant1) in key:
                return json.dumps(chunks1)
            elif str(tenant2) in key:
                return json.dumps(chunks2)
            return None

        mock_redis.get.side_effect = mock_get

        # Same query, different tenants, different results
        result1 = cache_service.get_query_result(query, tenant1, 5)
        result2 = cache_service.get_query_result(query, tenant2, 5)

        assert result1 != result2
        assert result1 == chunks1
        assert result2 == chunks2

    def test_embedding_cache_hash_collision_resistance(self, cache_service):
        """Test that similar texts generate different cache keys."""
        text1 = "Python programming"
        text2 = "Python programming."  # Only differs by punctuation
        model = "test-model"

        key1 = cache_service._generate_key("embed", text1, model)
        key2 = cache_service._generate_key("embed", text2, model)

        # Keys should be different even for very similar texts
        assert key1 != key2
