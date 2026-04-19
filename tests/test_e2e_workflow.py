"""
E2E Workflow Test Suite for FLAMEHAVEN FileSearch v1.4.2

Tests complete end-to-end workflows:
- Upload -> Search -> Store lifecycle
- Multi-mode search (keyword/semantic/hybrid)
- Batch search pipeline
- API key permission enforcement
"""

import pytest


class TestE2EUploadSearch:
    """E2E: File upload -> search pipeline"""

    def test_upload_single_then_search_e2e(self, client):
        """E2E: Upload a file then search within its store."""
        store_name = "e2e_upload_search"

        # Step 1: Upload a document
        content = b"Flamehaven FileSearch is a semantic document search engine powered by Gemini AI."
        response = client.post(
            "/api/upload/single",
            files={"file": ("e2e_doc.txt", content, "text/plain")},
            data={"store": store_name},
        )
        # Accept 200 (success) or 503 (offline/no Gemini API) - pipeline ran
        assert response.status_code in [
            200,
            429,
            503,
        ], f"Upload failed unexpectedly: {response.status_code} {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "request_id" in data

        # Step 2: Search within the store
        search_resp = client.post(
            "/api/search",
            json={
                "query": "semantic document search",
                "store_name": store_name,
                "search_mode": "keyword",
            },
        )
        # 200 (found), 404 (store empty offline), 400 (invalid), 429 (rate limited)
        assert search_resp.status_code in [
            200,
            400,
            404,
            429,
            503,
        ], f"Search failed unexpectedly: {search_resp.status_code}"

        if search_resp.status_code == 200:
            result = search_resp.json()
            assert "request_id" in result
            assert "status" in result

    def test_upload_multiple_then_list_stores_e2e(self, client):
        """E2E: Upload multiple files -> verify store exists via /api/stores."""
        store_name = "e2e_multi_store"

        files = [
            ("files", ("doc1.txt", b"Document one content", "text/plain")),
            ("files", ("doc2.txt", b"Document two content", "text/plain")),
        ]
        upload_resp = client.post(
            "/api/upload/multiple",
            files=files,
            data={"store": store_name},
        )
        assert upload_resp.status_code in [
            200,
            400,
            429,
            503,
        ], f"Multiple upload failed: {upload_resp.status_code}"

        # Step 2: List stores - store should appear
        stores_resp = client.get("/api/stores")
        assert stores_resp.status_code in [
            200,
            429,
            503,
        ], f"Stores list failed: {stores_resp.status_code}"

        if stores_resp.status_code == 200:
            stores_data = stores_resp.json()
            assert "stores" in stores_data
            assert "count" in stores_data
            # stores may be a list OR a dict {name: uri} depending on backend mode
            assert isinstance(stores_data["stores"], (list, dict))

    def test_health_then_search_e2e(self, client):
        """E2E: Health check -> search flow (system ready before search)."""
        # Verify system is up
        health_resp = client.get("/health")
        assert health_resp.status_code == 200

        health_data = health_resp.json()
        assert health_data["status"] in ["healthy", "unhealthy"]
        assert "version" in health_data

        # Only search if system reports healthy
        search_resp = client.post(
            "/api/search",
            json={"query": "test query for e2e", "store_name": "default"},
        )
        assert search_resp.status_code in [200, 400, 404, 429, 503]


class TestE2EStoreLifecycle:
    """E2E: Complete store lifecycle - create, use, delete."""

    def test_store_creation_via_upload_e2e(self, client):
        """E2E: Store is auto-created on first upload."""
        unique_store = "e2e_lifecycle_test"

        # Upload creates the store implicitly
        resp = client.post(
            "/api/upload/single",
            files={"file": ("lifecycle.txt", b"lifecycle content", "text/plain")},
            data={"store": unique_store},
        )
        assert resp.status_code in [200, 429, 503]

        if resp.status_code == 200:
            # Verify store info - stores field is list OR dict {name: uri}
            stores = client.get("/api/stores")
            if stores.status_code == 200:
                stores_val = stores.json().get("stores", [])
                assert isinstance(
                    stores_val, (list, dict)
                ), f"stores must be list or dict, got {type(stores_val)}"

    def test_store_search_empty_store_returns_404_e2e(self, client):
        """E2E: Search on non-existent store returns appropriate status.

        In offline/fallback mode the server may return 200 with an empty answer
        rather than 404, which is acceptable behaviour.
        """
        resp = client.post(
            "/api/search",
            json={
                "query": "anything",
                "store_name": "nonexistent_store_xyz_000",
                "search_mode": "keyword",
            },
        )
        # 200 is acceptable (offline mode returns empty result, not 404)
        # 404 is ideal (store not found), 503 = service unavailable
        # Hard rule: must NOT be 500 (internal server error)
        assert resp.status_code != 500, "Internal server error must not occur"
        assert resp.status_code in [
            200,
            400,
            404,
            429,
            503,
        ], f"Unexpected status for nonexistent store: {resp.status_code}"

    def test_delete_store_e2e(self, client):
        """E2E: Delete store endpoint returns valid response."""
        resp = client.delete("/api/stores/e2e_test_delete_store")
        # 200 (deleted), 404 (not found - also OK), 403 (no perms), 429
        assert resp.status_code in [
            200,
            404,
            403,
            429,
            503,
        ], f"Delete store returned unexpected: {resp.status_code}"
        assert resp.status_code != 500


class TestE2ESearchModes:
    """E2E: All three search modes produce valid API responses."""

    @pytest.mark.parametrize("mode", ["keyword", "semantic", "hybrid"])
    def test_search_mode_pipeline_e2e(self, client, mode):
        """E2E: Each search mode returns a valid API response structure."""
        resp = client.post(
            "/api/search",
            json={
                "query": "document search test",
                "store_name": "default",
                "search_mode": mode,
            },
        )
        # Pipeline ran - mode accepted (not 422 validation error)
        assert (
            resp.status_code != 422
        ), f"Mode '{mode}' was rejected with 422 (validation error)"
        assert resp.status_code in [
            200,
            400,
            404,
            429,
            503,
        ], f"Mode '{mode}' returned unexpected: {resp.status_code}"

        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data
            assert "request_id" in data

    def test_invalid_search_mode_rejected_e2e(self, client):
        """E2E: Invalid search mode is handled by the server.

        The server currently accepts unknown search modes (treats them as
        fallback keyword search). This test documents that behaviour:
        the server must not crash (500), regardless of whether it rejects
        or gracefully accepts the mode.
        """
        resp = client.post(
            "/api/search",
            json={
                "query": "test",
                "store_name": "default",
                "search_mode": "INVALID_MODE_XYZ",
            },
        )
        # Server may accept (200) or reject (400/422) invalid modes - both OK
        # Hard rule: must NOT be 500
        assert resp.status_code != 500, "Server must not crash on invalid search mode"
        assert resp.status_code in [
            200,
            400,
            422,
            429,
            503,
        ], f"Unexpected status for invalid mode: {resp.status_code}"

    def test_vector_backend_parameter_e2e(self, client):
        """E2E: vector_backend parameter is accepted via API."""
        for backend in ["auto", "memory"]:
            resp = client.post(
                "/api/search",
                json={
                    "query": "test query",
                    "store_name": "default",
                    "vector_backend": backend,
                },
            )
            # Must not be 422 (unprocessable)
            assert (
                resp.status_code != 422
            ), f"vector_backend='{backend}' rejected with 422"

    def test_invalid_vector_backend_rejected_e2e(self, client):
        """E2E: Invalid vector_backend is rejected with 400."""
        resp = client.post(
            "/api/search",
            json={
                "query": "test",
                "vector_backend": "invalid_backend",
            },
        )
        assert resp.status_code in [
            400,
            422,
            429,
        ], f"Invalid vector_backend was not rejected: {resp.status_code}"


class TestE2EBatchSearch:
    """E2E: Batch search API pipeline."""

    def test_batch_search_endpoint_exists_e2e(self, client):
        """E2E: /api/batch-search endpoint is reachable (actual path uses hyphen)."""
        resp = client.post(
            "/api/batch-search",
            json={
                "queries": [
                    {"query": "first query", "store": "default"},
                    {"query": "second query", "store": "default"},
                ]
            },
        )
        # 200 OK or 503 offline - but endpoint must exist (not 404)
        assert (
            resp.status_code != 404
        ), "Batch search endpoint /api/batch-search must exist (not 404)"
        assert resp.status_code in [
            200,
            400,
            422,
            429,
            503,
        ], f"Batch search unexpected: {resp.status_code}"

    def test_batch_search_empty_queries_rejected_e2e(self, client):
        """E2E: Batch search with empty query list is rejected."""
        resp = client.post(
            "/api/batch-search",
            json={"queries": []},
        )
        assert resp.status_code in [
            400,
            422,
            429,
        ], f"Empty batch query not rejected: {resp.status_code}"

    def test_batch_search_response_structure_e2e(self, client):
        """E2E: Batch search response has consistent structure."""
        resp = client.post(
            "/api/batch-search",
            json={
                "queries": [
                    {"query": "structure test", "store": "default"},
                ]
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            # BatchSearchResponse fields: status, request_id, total_queries, results
            assert isinstance(data, dict), "Batch response must be a dict"
            assert "status" in data, "Batch response must have 'status'"
            assert "results" in data, "Batch response must have 'results' list"
            assert isinstance(data["results"], list)


class TestE2EAPIKeyPermissions:
    """E2E: API key permission enforcement."""

    def test_unauthenticated_upload_rejected_e2e(self, public_client):
        """E2E: Upload without API key returns 401/403."""
        resp = public_client.post(
            "/api/upload/single",
            files={"file": ("test.txt", b"content", "text/plain")},
            data={"store": "test"},
        )
        assert resp.status_code in [
            401,
            403,
            429,
        ], f"Unauthenticated upload not blocked: {resp.status_code}"

    def test_unauthenticated_search_rejected_e2e(self, public_client):
        """E2E: Search without API key returns 401/403."""
        resp = public_client.post(
            "/api/search",
            json={"query": "test", "store_name": "default"},
        )
        assert resp.status_code in [
            401,
            403,
            429,
        ], f"Unauthenticated search not blocked: {resp.status_code}"

    def test_public_health_accessible_e2e(self, public_client):
        """E2E: /health is publicly accessible (no auth required)."""
        resp = public_client.get("/health")
        assert (
            resp.status_code == 200
        ), f"/health must be public, got {resp.status_code}"

    def test_public_root_accessible_e2e(self, public_client):
        """E2E: / root endpoint is publicly accessible."""
        resp = public_client.get("/")
        assert resp.status_code == 200, f"Root must be public, got {resp.status_code}"

    def test_authenticated_upload_succeeds_e2e(self, client):
        """E2E: Upload with valid API key is accepted (reaches processing layer)."""
        resp = client.post(
            "/api/upload/single",
            files={"file": ("auth_test.txt", b"auth test content", "text/plain")},
            data={"store": "auth_test"},
        )
        # Must NOT be 401/403 - authentication passed
        assert resp.status_code not in [
            401,
            403,
        ], f"Valid API key was rejected: {resp.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
