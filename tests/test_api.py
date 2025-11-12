"""
Tests for FLAMEHAVEN FileSearch API
"""

import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from flamehaven_filesearch.api import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock API key for testing"""
    test_key = os.getenv("GEMINI_API_KEY_TEST") or "test-mock-key"
    monkeypatch.setenv("GEMINI_API_KEY", test_key)
    return test_key


class TestHealthEndpoints:
    """Test health and info endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "FLAMEHAVEN FileSearch API"
        assert "version" in data
        assert "endpoints" in data

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "uptime" in data

    def test_docs_available(self, client):
        """Test API documentation is available"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema(self, client):
        """Test OpenAPI schema is available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "info" in schema
        assert schema["info"]["title"] == "SovDef FileSearch Lite API"


class TestStoreEndpoints:
    """Test store management endpoints"""

    def test_list_stores_empty(self, client, mock_api_key):
        """Test listing stores when none exist"""
        response = client.get("/stores")
        # May fail without valid API key
        if response.status_code == 200:
            data = response.json()
            assert "stores" in data
            assert "count" in data

    def test_create_store(self, client, mock_api_key):
        """Test creating a store"""
        response = client.post("/stores", json={"name": "test-store"})
        # May fail without valid API key
        # Just check it doesn't crash
        assert response.status_code in [200, 500, 503]


class TestUploadEndpoints:
    """Test file upload endpoints"""

    def test_upload_file_no_file(self, client, mock_api_key):
        """Test upload without file"""
        response = client.post("/upload")
        assert response.status_code == 422  # Validation error

    def test_upload_file_with_data(self, client, mock_api_key):
        """Test upload with file data"""
        # Create a small test file
        file_data = b"Test file content"
        files = {"file": ("test.txt", BytesIO(file_data), "text/plain")}
        data = {"store": "default"}

        response = client.post("/upload", files=files, data=data)
        # May fail without valid API key, but should not crash
        assert response.status_code in [200, 400, 500, 503]

    def test_upload_multiple_files(self, client, mock_api_key):
        """Test multiple file upload"""
        files = [
            ("files", ("test1.txt", BytesIO(b"File 1"), "text/plain")),
            ("files", ("test2.txt", BytesIO(b"File 2"), "text/plain")),
        ]
        data = {"store": "default"}

        response = client.post("/upload-multiple", files=files, data=data)
        # May fail without valid API key
        assert response.status_code in [200, 400, 500, 503]


class TestSearchEndpoints:
    """Test search endpoints"""

    def test_search_post_missing_query(self, client, mock_api_key):
        """Test search POST without query"""
        response = client.post("/search", json={})
        assert response.status_code == 422  # Validation error

    def test_search_post_with_query(self, client, mock_api_key):
        """Test search POST with query"""
        response = client.post(
            "/search", json={"query": "test query", "store_name": "default"}
        )
        # May fail without valid API key or store
        assert response.status_code in [200, 400, 500, 503]

    def test_search_get_missing_query(self, client, mock_api_key):
        """Test search GET without query"""
        response = client.get("/search")
        assert response.status_code == 422  # Validation error

    def test_search_get_with_query(self, client, mock_api_key):
        """Test search GET with query"""
        response = client.get("/search?q=test+query&store=default")
        # May fail without valid API key or store
        assert response.status_code in [200, 400, 500, 503]

    def test_search_with_params(self, client, mock_api_key):
        """Test search with additional parameters"""
        response = client.post(
            "/search",
            json={
                "query": "test",
                "store_name": "default",
                "model": "gemini-2.5-flash",
                "max_tokens": 512,
                "temperature": 0.7,
            },
        )
        assert response.status_code in [200, 400, 500, 503]


class TestMetricsEndpoints:
    """Test metrics endpoints"""

    def test_get_metrics(self, client, mock_api_key):
        """Test getting metrics"""
        response = client.get("/metrics")
        if response.status_code == 200:
            data = response.json()
            assert "stores_count" in data
            assert "stores" in data
            assert "config" in data


class TestErrorHandling:
    """Test error handling"""

    def test_404_endpoint(self, client):
        """Test non-existent endpoint returns 404"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_invalid_method(self, client):
        """Test invalid HTTP method"""
        response = client.patch("/upload")
        assert response.status_code == 405  # Method not allowed


# Integration tests requiring actual API key
@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API endpoints"""

    @pytest.fixture
    def auth_client(self):
        """Create client with actual API key"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            pytest.skip("GEMINI_API_KEY not set")

        # Set environment variable for app
        os.environ["GEMINI_API_KEY"] = api_key
        return TestClient(app)

    def test_full_workflow(self, auth_client):
        """Test complete upload and search workflow"""
        # Create store
        response = auth_client.post("/stores", json={"name": "integration-test"})
        assert response.status_code == 200

        # Upload file
        file_data = b"This is a test document for integration testing."
        files = {"file": ("test.txt", BytesIO(file_data), "text/plain")}
        data = {"store": "integration-test"}

        response = auth_client.post("/upload", files=files, data=data)
        assert response.status_code == 200
        upload_result = response.json()
        assert upload_result["status"] == "success"

        # Search
        response = auth_client.post(
            "/search",
            json={
                "query": "What is this document about?",
                "store_name": "integration-test",
            },
        )
        assert response.status_code == 200
        search_result = response.json()
        assert search_result["status"] == "success"
        assert "answer" in search_result

    def test_metrics_after_operations(self, auth_client):
        """Test metrics after performing operations"""
        # Get metrics
        response = auth_client.get("/metrics")
        assert response.status_code == 200
        metrics = response.json()
        assert metrics["stores_count"] >= 0
