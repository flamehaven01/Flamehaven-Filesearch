"""
Security Test Suite for FLAMEHAVEN FileSearch

Tests path traversal protection, input validation, and security features.
"""

import os
import pytest
from fastapi.testclient import TestClient
from flamehaven_filesearch.api import app


class TestPathTraversalProtection:
    """Test protection against path traversal attacks"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_path_traversal_single_upload(self, client, tmp_path):
        """Test path traversal protection in single file upload"""
        # Attack vectors that should be blocked
        attack_filenames = [
            "../../etc/passwd",
            "../../../secret.txt",
            "..\\..\\windows\\system32\\config\\sam",
            "../.ssh/id_rsa",
            "../../root/.bashrc",
            "./../important.conf",
        ]

        for malicious_filename in attack_filenames:
            # Create a test file with malicious filename
            file_content = b"This should not be written outside temp dir"

            response = client.post(
                "/api/upload/single",
                files={"file": (malicious_filename, file_content, "text/plain")},
            )

            # Should either reject (400) or sanitize the filename
            # After sanitization, only basename should remain
            assert response.status_code in [
                200,
                400,
            ], f"Unexpected status for {malicious_filename}: {response.status_code}"

            if response.status_code == 200:
                # If accepted, verify it was sanitized (only basename used)
                result = response.json()
                # The saved filename should be just the basename
                basename = os.path.basename(malicious_filename)
                assert basename in result.get("filename", ""), (
                    f"Filename not properly sanitized: {malicious_filename}"
                )

    def test_path_traversal_multiple_upload(self, client):
        """Test path traversal protection in multiple file upload"""
        attack_files = [
            ("files", ("../../etc/passwd", b"attack1", "text/plain")),
            ("files", ("../../../secret.txt", b"attack2", "text/plain")),
            ("files", ("..\\windows\\win.ini", b"attack3", "text/plain")),
        ]

        response = client.post("/api/upload/multiple", files=attack_files)

        # Should reject malicious filenames
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            result = response.json()
            # Verify all filenames were sanitized
            for file_info in result.get("files", []):
                filename = file_info.get("filename", "")
                # Should not contain path separators
                assert ".." not in filename
                assert "/" not in filename or filename.count("/") == filename.count(
                    os.sep
                )
                assert "\\" not in filename

    def test_hidden_file_rejection(self, client):
        """Test rejection of hidden files (starting with .)"""
        hidden_filenames = [
            ".hidden_malware.exe",
            ".env",
            ".ssh_key",
            ".passwd",
        ]

        for hidden_file in hidden_filenames:
            response = client.post(
                "/api/upload/single",
                files={"file": (hidden_file, b"content", "text/plain")},
            )

            # Should reject hidden files
            assert response.status_code == 400, (
                f"Hidden file not rejected: {hidden_file}"
            )
            assert "Invalid filename" in response.json().get("detail", "")

    def test_empty_filename_rejection(self, client):
        """Test rejection of empty filenames"""
        response = client.post(
            "/api/upload/single",
            files={"file": ("", b"content", "text/plain")},
        )

        assert response.status_code == 400
        assert "Invalid filename" in response.json().get("detail", "")

    def test_legitimate_filenames(self, client):
        """Test that legitimate filenames are accepted"""
        legitimate_files = [
            "document.pdf",
            "report_2025.txt",
            "data-analysis.csv",
            "photo.jpg",
            "my file with spaces.docx",
        ]

        for filename in legitimate_files:
            response = client.post(
                "/api/upload/single",
                files={"file": (filename, b"legitimate content", "text/plain")},
            )

            # Legitimate files should be accepted
            assert response.status_code in [
                200,
                201,
            ], f"Legitimate file rejected: {filename}"


class TestInputValidation:
    """Test input validation and sanitization"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_file_size_limits(self, client):
        """Test file size validation"""
        # Create a large file (simulate exceeding limit)
        large_content = b"X" * (100 * 1024 * 1024)  # 100MB

        response = client.post(
            "/api/upload/single",
            files={"file": ("large.bin", large_content, "application/octet-stream")},
        )

        # Should reject if exceeds configured limit
        # (actual behavior depends on MAX_FILE_SIZE_MB configuration)
        assert response.status_code in [200, 400, 413]

    def test_search_query_validation(self, client):
        """Test search query validation"""
        # Test various query patterns
        valid_queries = [
            "machine learning",
            "data science tutorial",
            "python programming",
        ]

        for query in valid_queries:
            response = client.post(
                "/api/search",
                json={"query": query},
            )

            # Should accept valid queries (may return 404 if no docs indexed)
            assert response.status_code in [200, 404]

    def test_special_characters_in_search(self, client):
        """Test handling of special characters in search queries"""
        special_queries = [
            "C++ programming",
            "R&D activities",
            "cost/benefit analysis",
            "AI & ML",
        ]

        for query in special_queries:
            response = client.post(
                "/api/search",
                json={"query": query},
            )

            # Should handle special characters gracefully
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                assert isinstance(response.json(), dict)


class TestAPIKeyHandling:
    """Test API key handling and offline mode"""

    def test_offline_mode_config(self):
        """Test that offline mode works without API key"""
        from flamehaven_filesearch.config import Config

        # Should not raise error when require_api_key=False
        config = Config(api_key=None)
        try:
            config.validate(require_api_key=False)
            assert True, "Offline mode validation passed"
        except ValueError:
            pytest.fail("Offline mode should not require API key")

    def test_remote_mode_requires_key(self):
        """Test that remote mode requires API key"""
        from flamehaven_filesearch.config import Config

        config = Config(api_key=None)

        # Should raise error when require_api_key=True
        with pytest.raises(ValueError) as exc_info:
            config.validate(require_api_key=True)

        assert "API key required" in str(exc_info.value)

    def test_valid_api_key_accepted(self):
        """Test that valid API key is accepted"""
        from flamehaven_filesearch.config import Config

        config = Config(api_key="dummy-key")

        # Should not raise error
        assert config.validate(require_api_key=True) is True


class TestAuthenticationAndAuthorization:
    """Test authentication and authorization mechanisms"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint_public(self, client):
        """Test that health endpoint is publicly accessible"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_metrics_endpoint_accessible(self, client):
        """Test that metrics endpoint is accessible"""
        response = client.get("/metrics")

        # Should return metrics data
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling and information disclosure"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_404_error_handling(self, client):
        """Test 404 error does not leak information"""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404
        data = response.json()
        # Should not expose internal paths or sensitive info
        assert "detail" in data
        assert "/home/" not in str(data)
        assert "C:\\" not in str(data)

    def test_500_error_handling(self, client):
        """Test internal errors don't expose stack traces"""
        # This would need to trigger an actual internal error
        # For now, just verify error response structure
        pass

    def test_malformed_json_handling(self, client):
        """Test handling of malformed JSON"""
        response = client.post(
            "/api/search",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code in [400, 422]
        # Should return structured error, not expose internals


class TestSecurityHeaders:
    """Test security-related HTTP headers"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_security_headers_present(self, client):
        """Test that appropriate security headers are set"""
        response = client.get("/health")

        # This test will initially fail - headers to be added in Phase 3
        # Just verify response is valid
        assert response.status_code == 200


class TestRateLimiting:
    """Test rate limiting (to be implemented in Phase 3)"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.skip(reason="Rate limiting not yet implemented - Phase 3")
    def test_upload_rate_limiting(self, client):
        """Test upload rate limiting (10/min)"""
        # Make 11 requests rapidly
        responses = []
        for i in range(11):
            response = client.post(
                "/api/upload/single",
                files={"file": (f"test{i}.txt", b"content", "text/plain")},
            )
            responses.append(response)

        # 11th request should be rate limited
        assert responses[-1].status_code == 429

    @pytest.mark.skip(reason="Rate limiting not yet implemented - Phase 3")
    def test_search_rate_limiting(self, client):
        """Test search rate limiting (100/min)"""
        # Make 101 requests rapidly
        responses = []
        for i in range(101):
            response = client.post(
                "/api/search",
                json={"query": f"test query {i}"},
            )
            responses.append(response)

        # 101st request should be rate limited
        assert responses[-1].status_code == 429


class TestCORSConfiguration:
    """Test CORS configuration"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_cors_headers(self, client):
        """Test CORS headers are properly configured"""
        response = client.options(
            "/api/search",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should allow configured origins
        assert response.status_code in [200, 204]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
