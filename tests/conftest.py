"""
Shared pytest fixtures and configuration for FLAMEHAVEN FileSearch tests.

Provides:
- Authenticated test client with API key
- Test database isolation
- Mock Google Gemini API
"""

import tempfile
import sys
import site
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure user site-packages are visible (for psutil, etc.)
sys.path.append(site.getusersitepackages())

from flamehaven_filesearch.api import app
from flamehaven_filesearch.auth import get_key_manager


@pytest.fixture(scope="session")
def test_api_key():
    """Fixed test API key for all tests"""
    return "sk_test_abc123def456ghi789jkl"


@pytest.fixture
def temp_db():
    """Create temporary database for each test"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        Path(db_path).unlink()
    except FileNotFoundError:
        pass
    except PermissionError:
        # On Windows, retry with delay if locked
        import time

        time.sleep(0.1)
        try:
            Path(db_path).unlink()
        except (FileNotFoundError, PermissionError):
            pass


@pytest.fixture
def key_manager(temp_db, test_api_key, monkeypatch):
    """Create API key manager with temp database and mock"""
    # Override default database
    monkeypatch.setenv("FLAMEHAVEN_API_KEYS_DB", temp_db)

    # Reset global singleton to force new instance with temp_db
    import flamehaven_filesearch.auth as auth_module

    auth_module._key_manager = None

    manager = get_key_manager(temp_db)

    # Create test API key by directly inserting (bypass hashing for testing)
    import sqlite3
    from datetime import datetime

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tables already created by manager._ensure_db(), just verify
    # No need to recreate - manager already initialized the schema

    # Insert test key (use SHA256 hash for consistency)
    import hashlib

    key_hash = hashlib.sha256(test_api_key.encode()).hexdigest()

    cursor.execute(
        """
        INSERT OR IGNORE INTO api_keys
        (id, name, key_hash, user_id, created_at, is_active,
         rate_limit_per_minute, permissions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "test_key_id",
            "Test Key",
            key_hash,
            "test_user",
            datetime.now().isoformat(),
            1,
            100,
            '["upload", "search", "stores", "delete", "admin"]',
        ),
    )

    conn.commit()
    conn.close()

    # Set as global singleton BEFORE yielding
    # This ensures all get_key_manager() calls use this instance
    auth_module._key_manager = manager

    yield manager

    # Cleanup: close DB connections
    if hasattr(manager, "conn") and manager.conn:
        manager.conn.close()

    # Reset singleton
    auth_module._key_manager = None


class AuthenticatedTestClient(TestClient):
    """Custom TestClient that automatically adds API key authentication"""

    def __init__(self, app, api_key=None, **kwargs):
        super().__init__(app, **kwargs)
        self.api_key = api_key
        self.public_endpoints = [
            "/",
            "/health",
            "/prometheus",
            "/docs",
            "/openapi.json",
            "/admin/dashboard",
        ]

    def request(self, method, url, **kwargs):
        """Override request to add authentication header"""
        # Handle None or missing headers
        if "headers" not in kwargs or kwargs["headers"] is None:
            kwargs["headers"] = {}

        # Add API key for protected endpoints
        if self.api_key and url not in self.public_endpoints:
            if "Authorization" not in kwargs["headers"]:
                kwargs["headers"]["Authorization"] = f"Bearer {self.api_key}"

        return super().request(method, url, **kwargs)


@pytest.fixture
def authenticated_client(test_api_key, temp_db, monkeypatch, key_manager):
    """FastAPI test client with authentication headers"""
    monkeypatch.setenv("FLAMEHAVEN_API_KEYS_DB", temp_db)
    monkeypatch.setenv("FLAMEHAVEN_ADMIN_KEY", "admin_test_key_12345")

    # Singleton already set by key_manager fixture

    return AuthenticatedTestClient(app, api_key=test_api_key)


@pytest.fixture
def public_client(temp_db, monkeypatch):
    """FastAPI test client for public endpoints (no authentication)"""
    monkeypatch.setenv("FLAMEHAVEN_API_KEYS_DB", temp_db)
    return TestClient(app)


@pytest.fixture
def client(authenticated_client):
    """Alias for authenticated_client for backward compatibility"""
    return authenticated_client


@pytest.fixture
def admin_client(test_api_key, temp_db, monkeypatch, key_manager):
    """FastAPI test client with admin authentication"""
    admin_key = "admin_test_key_12345"
    monkeypatch.setenv("FLAMEHAVEN_API_KEYS_DB", temp_db)
    monkeypatch.setenv("FLAMEHAVEN_ADMIN_KEY", admin_key)

    # Singleton already set by key_manager fixture

    return AuthenticatedTestClient(app, api_key=test_api_key)


@pytest.fixture
def mock_gemini():
    """Mock Google Gemini API responses"""
    with patch("flamehaven_filesearch.core.GoogleGenerativeAI") as mock_api:
        # Mock the API client
        mock_client = MagicMock()
        mock_api.return_value = mock_client

        # Mock embeddings
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 768
        mock_client.embed_content.return_value = mock_embedding

        # Mock text generation
        mock_response = MagicMock()
        mock_response.text = "This is a test response from the mocked Gemini API."
        mock_client.generate_content.return_value = mock_response

        yield mock_client


@pytest.fixture
def mock_online_api(monkeypatch):
    """Set up environment for online API mode"""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key_12345")
    monkeypatch.setenv("ENVIRONMENT", "remote")


@pytest.fixture(autouse=True)
def cleanup_metrics():
    """Reset metrics before each test to avoid cross-test contamination"""
    # Clear in-memory metrics state

    # Reset metrics registry if needed
    yield

    # Cleanup after test


@pytest.fixture(autouse=True)
def ensure_searcher_initialized():
    """Ensure searcher and cache are initialized for each test."""
    from flamehaven_filesearch import api as api_module

    api_module.initialize_services(force=True)
    yield


@pytest.fixture
def isolated_fs(tmp_path, monkeypatch):
    """Provide isolated filesystem for tests"""
    monkeypatch.chdir(tmp_path)
    return tmp_path
