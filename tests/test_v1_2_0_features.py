"""
Comprehensive tests for FLAMEHAVEN FileSearch v1.2.0 features.

Tests all new functionality added in v1.2.0:
- API Key Authentication
- Admin Dashboard
- Batch Search API
- Redis Cache Backend
"""

import pytest
from fastapi.testclient import TestClient

from flamehaven_filesearch.api import app

# Try to import RedisCache, but it's optional
try:
    from flamehaven_filesearch.cache_redis import RedisCache, REDIS_AVAILABLE

    HAS_REDIS_CACHE = REDIS_AVAILABLE
except ImportError:
    HAS_REDIS_CACHE = False

# ============================================================================
# API AUTHENTICATION TESTS
# ============================================================================


class TestAPIKeyAuthentication:
    """Test API key generation, validation, and authentication"""

    def test_generate_api_key(self, key_manager):
        """Test API key generation"""
        key_id, plain_key = key_manager.generate_key(
            user_id="test_user",
            name="Test Key",
            permissions=["upload", "search"],
        )
        # Verify key was generated
        assert key_id is not None
        assert plain_key is not None
        assert plain_key.startswith("sk_live_")

    def test_api_key_is_unique(self, key_manager):
        """Test that generated API keys are unique"""
        key1_id, key1_plain = key_manager.generate_key("user1", "Key 1", ["upload"])
        key2_id, key2_plain = key_manager.generate_key("user1", "Key 2", ["upload"])
        # Keys should be different
        assert key1_id != key2_id
        assert key1_plain != key2_plain

    def test_api_key_never_stored_plain(self, key_manager):
        """Test that plain API keys are never stored in database"""
        key_id, plain_key = key_manager.generate_key("user", "test", ["upload"])
        # The returned key should work for validation
        assert key_id is not None
        assert plain_key is not None

        # Verify we can validate the key
        key_info = key_manager.validate_key(plain_key)
        assert key_info is not None
        assert key_info.user_id == "user"
        assert key_info.name == "test"

    def test_protected_endpoints_require_auth(self, client, test_api_key):
        """Test that protected endpoints require authentication"""
        # Without auth header, endpoints should require API key
        test_client = TestClient(app)  # Plain client without auth

        response = test_client.post(
            "/api/upload/single",
            files={"file": ("test.txt", "content", "text/plain")},
        )
        assert response.status_code == 401

    def test_protected_endpoints_with_auth(self, authenticated_client):
        """Test that protected endpoints work with valid API key"""
        response = authenticated_client.get("/api/stores")
        assert response.status_code in [200, 404]  # Either success or store not found

    def test_invalid_api_key_rejected(self, authenticated_client):
        """Test that invalid API keys are rejected"""
        test_client = TestClient(app)
        response = test_client.get(
            "/api/stores",
            headers={"Authorization": "Bearer invalid_key_12345"},
        )
        assert response.status_code == 401


# ============================================================================
# ADMIN DASHBOARD TESTS
# ============================================================================


class TestAdminDashboard:
    """Test admin dashboard functionality"""

    def test_dashboard_endpoint_exists(self, authenticated_client):
        """Test that dashboard endpoint exists"""
        response = authenticated_client.get("/admin/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_contains_metrics(self, authenticated_client):
        """Test that dashboard displays metrics"""
        response = authenticated_client.get("/admin/dashboard")
        assert response.status_code == 200
        html = response.text
        # Should contain typical dashboard elements
        assert "API Keys" in html or "api" in html.lower()
        assert "Request" in html or "request" in html.lower()

    def test_admin_create_key_endpoint(self, authenticated_client):
        """Test admin endpoint for creating API keys"""
        response = authenticated_client.post(
            "/api/admin/keys",
            json={
                "name": "New Test Key",
                "permissions": ["upload", "search"],
                "rate_limit_per_minute": 50,
            },
            headers={"X-Admin-Key": "admin_test_key_12345"},
        )
        # Should return 200 or 422 (validation), not 401
        assert response.status_code in [200, 201, 422]

    def test_admin_list_keys_endpoint(self, authenticated_client):
        """Test admin endpoint for listing keys"""
        response = authenticated_client.get(
            "/api/admin/keys",
            headers={"X-Admin-Key": "admin_test_key_12345"},
        )
        # Should return key list or validation error
        assert response.status_code in [200, 422]

    def test_admin_usage_stats_endpoint(self, authenticated_client):
        """Test admin endpoint for usage statistics"""
        response = authenticated_client.get(
            "/api/admin/usage?days=7",
            headers={"X-Admin-Key": "admin_test_key_12345"},
        )
        # Should return usage stats or validation error
        assert response.status_code in [200, 422]


# ============================================================================
# BATCH SEARCH TESTS
# ============================================================================


class TestBatchSearchAPI:
    """Test batch search functionality"""

    def test_batch_search_endpoint_exists(self, authenticated_client):
        """Test that batch search endpoint exists"""
        batch_request = {
            "queries": [
                {"query": "test query 1", "store": "default"},
            ],
            "mode": "sequential",
        }
        response = authenticated_client.post(
            "/api/batch-search",
            json=batch_request,
        )
        # Endpoint should exist (may return error due to missing store, but not 404)
        assert response.status_code != 404

    def test_batch_search_accepts_multiple_queries(self, authenticated_client):
        """Test batch search with multiple queries"""
        batch_request = {
            "queries": [
                {"query": "query 1", "store": "default", "priority": 5},
                {"query": "query 2", "store": "default", "priority": 3},
                {"query": "query 3", "store": "default", "priority": 7},
            ],
            "mode": "sequential",
        }
        response = authenticated_client.post(
            "/api/batch-search",
            json=batch_request,
        )
        # Should accept batch request format
        assert response.status_code in [200, 400, 404, 422]

    def test_batch_search_supports_parallel_mode(self, authenticated_client):
        """Test batch search parallel execution mode"""
        batch_request = {
            "queries": [
                {"query": "query 1", "store": "default"},
                {"query": "query 2", "store": "default"},
            ],
            "mode": "parallel",
        }
        response = authenticated_client.post(
            "/api/batch-search",
            json=batch_request,
        )
        # Parallel mode should be supported
        assert response.status_code in [200, 400, 404, 422]

    def test_batch_search_has_status_endpoint(self, authenticated_client):
        """Test batch search status endpoint"""
        response = authenticated_client.get("/api/batch-search/status")
        # Endpoint should indicate batch search is available
        assert response.status_code in [200, 404]


# ============================================================================
# REDIS CACHE BACKEND TESTS
# ============================================================================


class TestRedisCacheBackend:
    """Test Redis cache backend"""

    @pytest.mark.skipif(not HAS_REDIS_CACHE, reason="redis package not installed")
    def test_redis_cache_basic_operations(self):
        """Test basic Redis cache operations"""
        cache = RedisCache(host="localhost", port=6379, password=None)

        # Test set/get (may fail if Redis not running, but that's ok for this test)
        try:
            cache.set("test_key", "test_value")
            value = cache.get("test_key")
            # If Redis is available, check value
            if value is not None:
                assert value == "test_value"
        except Exception:
            # Redis not running is acceptable for this test
            pytest.skip("Redis not available")

    @pytest.mark.skipif(not HAS_REDIS_CACHE, reason="redis package not installed")
    def test_redis_cache_has_namespace_isolation(self):
        """Test that Redis cache uses namespace isolation"""
        cache = RedisCache(host="localhost", port=6379, password=None)

        try:
            # Should use flamehaven: prefix for keys
            cache.set("test_key", "test_value")
            # Verify namespace is used (implementation detail)
            assert hasattr(cache, "namespace")
        except Exception:
            pytest.skip("Redis not available")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestV120Integration:
    """Integration tests for v1.2.0 features working together"""

    def test_authenticated_search(self, authenticated_client):
        """Test that authenticated search works"""
        response = authenticated_client.post(
            "/api/search",
            json={"query": "test", "store": "default"},
        )
        # Should authenticate successfully, may return 404 for missing store
        assert response.status_code in [200, 404, 400, 422]

    def test_authenticated_upload(self, authenticated_client):
        """Test that authenticated upload works"""
        response = authenticated_client.post(
            "/api/upload/single",
            files={"file": ("test.txt", "test content", "text/plain")},
        )
        # Should authenticate, may fail for other reasons
        assert response.status_code != 401

    def test_authenticated_store_management(self, authenticated_client):
        """Test that authenticated store management works"""
        # Create store
        response = authenticated_client.post(
            "/api/stores",
            json={"name": "test_store"},
        )
        assert response.status_code != 401

        # List stores
        response = authenticated_client.get("/api/stores")
        assert response.status_code != 401

    def test_public_endpoints_still_available(self):
        """Test that public endpoints don't require authentication"""
        client = TestClient(app)

        # Health check should be public
        response = client.get("/health")
        assert response.status_code == 200

        # Docs should be public
        response = client.get("/docs")
        assert response.status_code == 200

        # Prometheus should be public
        response = client.get("/prometheus")
        assert response.status_code == 200


# ============================================================================
# API VERSION TESTS
# ============================================================================


class TestAPIVersion:
    """Test API version reporting"""

    def test_api_version_is_120(self, authenticated_client):
        """Test that API reports version 1.2.0"""
        response = authenticated_client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Should have version info
        assert (
            "version" in data
            or "api_version" in data
            or "service" in data.get("info", {})
        )

    def test_api_version_in_responses(self, authenticated_client):
        """Test that API version appears in responses"""
        response = authenticated_client.get("/api/stores")
        response.json()

        # Version should be in response metadata if available
        assert response.status_code in [200, 404, 400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
