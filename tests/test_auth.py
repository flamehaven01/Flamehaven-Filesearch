"""
Tests for API Key Authentication in FLAMEHAVEN FileSearch v1.2.0

Tests:
- API key generation and validation
- Protected endpoint access with/without keys
- Admin routes for key management
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flamehaven_filesearch.api import app
from flamehaven_filesearch.auth import get_key_manager


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        Path(db_path).unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def key_manager(temp_db):
    """Create API key manager with temp database"""
    manager = get_key_manager(temp_db)
    return manager


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def admin_key(monkeypatch):
    """Set admin API key for testing"""
    admin_key = "admin_test_key_12345"
    monkeypatch.setenv("FLAMEHAVEN_ADMIN_KEY", admin_key)
    return admin_key


class TestAPIKeyGeneration:
    """Test API key generation and storage"""

    def test_generate_key_creates_unique_keys(self, key_manager):
        """Test that generated keys are unique"""
        key_id_1, plain_key_1 = key_manager.generate_key(
            user_id="user1", name="Key 1"
        )
        key_id_2, plain_key_2 = key_manager.generate_key(
            user_id="user1", name="Key 2"
        )

        assert key_id_1 != key_id_2
        assert plain_key_1 != plain_key_2
        assert key_id_1.startswith("key_")
        assert key_id_2.startswith("key_")

    def test_generate_key_with_permissions(self, key_manager):
        """Test generating key with specific permissions"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1",
            name="Limited Key",
            permissions=["upload", "search"],
        )

        key_info = key_manager.validate_key(plain_key)
        assert key_info is not None
        assert set(key_info.permissions) == {"upload", "search"}

    def test_generate_key_with_rate_limit(self, key_manager):
        """Test generating key with custom rate limit"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1",
            name="Limited Rate Key",
            rate_limit_per_minute=50,
        )

        key_info = key_manager.validate_key(plain_key)
        assert key_info.rate_limit_per_minute == 50

    def test_generate_key_with_expiration(self, key_manager):
        """Test generating key with expiration"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1",
            name="Expiring Key",
            expires_in_days=7,
        )

        key_info = key_manager.validate_key(plain_key)
        assert key_info is not None


class TestAPIKeyValidation:
    """Test API key validation"""

    def test_validate_valid_key(self, key_manager):
        """Test validating a valid API key"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1", name="Test Key"
        )

        key_info = key_manager.validate_key(plain_key)
        assert key_info is not None
        assert key_info.id == key_id
        assert key_info.user_id == "user1"
        assert key_info.name == "Test Key"
        assert key_info.is_active is True

    def test_validate_invalid_key(self, key_manager):
        """Test validating invalid API key"""
        key_info = key_manager.validate_key("invalid_key_xyz")
        assert key_info is None

    def test_validate_revoked_key(self, key_manager):
        """Test that revoked keys fail validation"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1", name="Test Key"
        )

        # Revoke the key
        key_manager.revoke_key(key_id)

        # Validation should fail
        key_info = key_manager.validate_key(plain_key)
        assert key_info is None


class TestAPIKeyManagement:
    """Test key revocation and listing"""

    def test_revoke_key(self, key_manager):
        """Test revoking an API key"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1", name="Test Key"
        )

        # Revoke the key
        result = key_manager.revoke_key(key_id)
        assert result is True

        # Key should no longer be valid
        key_info = key_manager.validate_key(plain_key)
        assert key_info is None

    def test_list_keys_for_user(self, key_manager):
        """Test listing keys for a specific user"""
        key_manager.generate_key(user_id="user1", name="User1 Key 1")
        key_manager.generate_key(user_id="user1", name="User1 Key 2")
        key_manager.generate_key(user_id="user2", name="User2 Key 1")

        user1_keys = key_manager.list_keys("user1")
        user2_keys = key_manager.list_keys("user2")

        assert len(user1_keys) == 2
        assert len(user2_keys) == 1
        assert all(k.user_id == "user1" for k in user1_keys)
        assert user2_keys[0].user_id == "user2"

    def test_list_keys_excludes_secrets(self, key_manager):
        """Test that list_keys doesn't return plain keys"""
        key_id, plain_key = key_manager.generate_key(
            user_id="user1", name="Test Key"
        )

        keys = key_manager.list_keys("user1")
        assert len(keys) == 1

        key_info = keys[0]
        # Verify that plain_key is NOT in the response dict
        key_dict = key_info.to_dict()
        assert "key" not in key_dict or key_dict.get("key") != plain_key


class TestProtectedEndpoints:
    """Test that endpoints require authentication"""

    def test_upload_single_requires_auth(self, client):
        """Test that upload endpoint requires API key"""
        response = client.post(
            "/api/upload/single",
            files={"file": ("test.txt", b"test content")},
            data={"store": "default"},
        )

        assert response.status_code == 401
        assert "Authorization" in response.text.lower() or "missing" in response.text.lower()

    def test_search_requires_auth(self, client):
        """Test that search endpoint requires API key"""
        response = client.post(
            "/api/search",
            json={"query": "test"},
        )

        assert response.status_code == 401

    def test_stores_create_requires_auth(self, client):
        """Test that store creation requires API key"""
        response = client.post("/api/stores", json={"name": "test_store"})

        assert response.status_code == 401

    def test_stores_list_requires_auth(self, client):
        """Test that store listing requires API key"""
        response = client.get("/api/stores")

        assert response.status_code == 401

    def test_health_check_no_auth_required(self, client):
        """Test that health check doesn't require authentication"""
        response = client.get("/health")

        assert response.status_code == 200
        assert "status" in response.json()


class TestAdminRoutes:
    """Test admin API for key management"""

    def test_create_api_key_via_admin(self, client, admin_key):
        """Test creating API key through admin endpoint"""
        response = client.post(
            "/api/admin/keys",
            json={
                "name": "Test Admin Key",
                "permissions": ["upload", "search"],
                "rate_limit_per_minute": 100,
            },
            headers={"Authorization": f"Bearer {admin_key}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "key" in data
        assert data["name"] == "Test Admin Key"
        assert data["permissions"] == ["upload", "search"]
        assert "warning" in data

    def test_list_api_keys_via_admin(self, client, admin_key):
        """Test listing API keys through admin endpoint"""
        # First create a key
        create_response = client.post(
            "/api/admin/keys",
            json={"name": "Test Key"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert create_response.status_code == 200

        # Now list keys
        list_response = client.get(
            "/api/admin/keys",
            headers={"Authorization": f"Bearer {admin_key}"},
        )

        assert list_response.status_code == 200
        data = list_response.json()
        assert "keys" in data
        assert len(data["keys"]) > 0

    def test_revoke_api_key_via_admin(self, client, admin_key):
        """Test revoking API key through admin endpoint"""
        # First create a key
        create_response = client.post(
            "/api/admin/keys",
            json={"name": "Test Key to Revoke"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        key_data = create_response.json()
        key_id = key_data["id"]

        # Revoke the key
        revoke_response = client.delete(
            f"/api/admin/keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_key}"},
        )

        assert revoke_response.status_code == 200
        data = revoke_response.json()
        assert data["status"] == "success"

    def test_admin_requires_authentication(self, client):
        """Test that admin endpoints require authentication"""
        response = client.post(
            "/api/admin/keys",
            json={"name": "Test"},
        )

        assert response.status_code == 401

    def test_admin_with_invalid_key(self, client):
        """Test admin endpoint with invalid key"""
        response = client.post(
            "/api/admin/keys",
            json={"name": "Test"},
            headers={"Authorization": "Bearer invalid_admin_key"},
        )

        assert response.status_code == 401


class TestUsageTracking:
    """Test usage statistics tracking"""

    def test_get_usage_stats(self, client, admin_key, key_manager):
        """Test retrieving usage statistics"""
        # Create a test key
        key_id, plain_key = key_manager.generate_key(
            user_id="admin", name="Test Key"
        )

        # Log some usage
        key_manager.log_usage(
            api_key_id=key_id,
            request_id="test-request-1",
            endpoint="/api/search",
            method="POST",
            status_code=200,
            duration_ms=100,
        )

        # Get usage stats
        response = client.get(
            "/api/admin/usage",
            headers={"Authorization": f"Bearer {admin_key}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "by_endpoint" in data
        assert "by_key" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
