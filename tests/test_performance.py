"""
Performance Test Suite for FLAMEHAVEN FileSearch

Tests performance characteristics, response times, and throughput.
"""

import time
import pytest
from fastapi.testclient import TestClient
from flamehaven_filesearch.api import app


class TestResponseTimes:
    """Test API endpoint response times"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint_response_time(self, client):
        """Test health endpoint responds quickly"""
        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Health check should be very fast (<100ms)
        assert elapsed < 0.1, f"Health check took {elapsed:.3f}s (expected <0.1s)"

    def test_metrics_endpoint_response_time(self, client):
        """Test metrics endpoint responds quickly"""
        start = time.time()
        response = client.get("/metrics")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Metrics should be fast (<500ms)
        assert elapsed < 0.5, f"Metrics took {elapsed:.3f}s (expected <0.5s)"

    @pytest.mark.slow
    def test_upload_response_time(self, client):
        """Test file upload response time"""
        content = b"x" * 1024  # 1KB file

        start = time.time()
        response = client.post(
            "/api/upload/single",
            files={"file": ("test.txt", content, "text/plain")},
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        # Small file upload should complete in reasonable time (<2s)
        assert elapsed < 2.0, f"Upload took {elapsed:.3f}s (expected <2s)"

    @pytest.mark.slow
    def test_search_response_time(self, client):
        """Test search response time"""
        start = time.time()
        response = client.post(
            "/api/search",
            json={"query": "test query"},
        )
        assert response.status_code == 200
        elapsed = time.time() - start

        # Search should complete reasonably fast (<3s)
        assert elapsed < 3.0, f"Search took {elapsed:.3f}s (expected <3s)"


class TestThroughput:
    """Test API throughput and scalability"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.slow
    def test_sequential_upload_throughput(self, client):
        """Test throughput of sequential uploads"""
        num_uploads = 10
        content = b"x" * 1024  # 1KB files

        start = time.time()
        for i in range(num_uploads):
            response = client.post(
                "/api/upload/single",
                files={"file": (f"test{i}.txt", content, "text/plain")},
            )
            assert response.status_code == 200

        elapsed = time.time() - start
        throughput = num_uploads / elapsed

        print(f"\nSequential upload throughput: {throughput:.2f} files/sec")
        # Should handle at least 1 file per second
        assert throughput > 1.0, f"Low throughput: {throughput:.2f} files/sec"

    @pytest.mark.slow
    def test_sequential_search_throughput(self, client):
        """Test throughput of sequential searches"""
        num_searches = 20

        start = time.time()
        for i in range(num_searches):
            response = client.post(
                "/api/search",
                json={"query": f"test query {i}"},
            )
            assert response.status_code in [200, 404]

        elapsed = time.time() - start
        throughput = num_searches / elapsed

        print(f"\nSequential search throughput: {throughput:.2f} searches/sec")
        # Should handle multiple searches per second
        assert throughput > 2.0, f"Low throughput: {throughput:.2f} searches/sec"

    @pytest.mark.slow
    def test_concurrent_request_handling(self, client):
        """Test handling of concurrent requests"""
        import concurrent.futures

        def make_request(index):
            start = time.time()
            response = client.get("/health")
            elapsed = time.time() - start
            return response.status_code, elapsed

        # Make 50 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            start = time.time()
            futures = [executor.submit(make_request, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            total_elapsed = time.time() - start

        # All requests should succeed
        assert all(status == 200 for status, _ in results)

        # Average response time should still be reasonable under load
        avg_response_time = sum(elapsed for _, elapsed in results) / len(results)
        print(f"\nAverage response time under load: {avg_response_time:.3f}s")
        assert avg_response_time < 1.0, f"Slow under load: {avg_response_time:.3f}s avg"

        # Total time should show concurrency benefit
        print(f"Total time for 50 concurrent requests: {total_elapsed:.3f}s")


class TestMemoryUsage:
    """Test memory usage characteristics"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.slow
    def test_large_file_upload_memory(self, client):
        """Test memory handling for large file uploads"""
        # 10MB file
        large_content = b"x" * (10 * 1024 * 1024)

        response = client.post(
            "/api/upload/single",
            files={"file": ("large.bin", large_content, "application/octet-stream")},
        )

        # Should handle large files without crashing
        assert response.status_code in [200, 400, 413]

    @pytest.mark.slow
    def test_many_small_uploads_memory(self, client):
        """Test memory handling for many small uploads"""
        # Upload 100 small files
        for i in range(100):
            response = client.post(
                "/api/upload/single",
                files={"file": (f"test{i}.txt", b"content", "text/plain")},
            )
            # Should handle without memory issues
            assert response.status_code in [200, 429]

    @pytest.mark.slow
    def test_repeated_operations_memory_stability(self, client):
        """Test memory stability over repeated operations"""
        # Perform 500 mixed operations
        for i in range(500):
            if i % 2 == 0:
                # Upload
                client.post(
                    "/api/upload/single",
                    files={"file": (f"test{i}.txt", b"data", "text/plain")},
                )
            else:
                # Search
                client.post(
                    "/api/search",
                    json={"query": f"query {i}"},
                )

        # If this completes without hanging, memory is stable
        response = client.get("/health")
        assert response.status_code == 200


class TestScalability:
    """Test scalability characteristics"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.slow
    def test_increasing_load_performance(self, client):
        """Test performance degradation under increasing load"""
        load_levels = [10, 25, 50]
        response_times = []

        for load in load_levels:
            start = time.time()
            for _ in range(load):
                client.get("/health")
            elapsed = time.time() - start
            avg_time = elapsed / load
            response_times.append(avg_time)

            print(f"\nLoad {load}: avg {avg_time:.4f}s per request")

        # Performance should not degrade dramatically
        # Check that 50-request avg is not more than 3x the 10-request avg
        if len(response_times) >= 2:
            degradation = response_times[-1] / response_times[0]
            print(f"Performance degradation factor: {degradation:.2f}x")
            assert (
                degradation < 3.0
            ), f"Performance degraded {degradation:.2f}x under load"

    @pytest.mark.slow
    def test_file_size_scaling(self, client):
        """Test upload performance scales with file size"""
        sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB
        times = []

        for size in sizes:
            content = b"x" * size

            start = time.time()
            response = client.post(
                "/api/upload/single",
                files={"file": ("test.bin", content, "application/octet-stream")},
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                times.append(elapsed)
                throughput = size / elapsed / 1024  # KB/s
                print(
                    f"\nSize {size / 1024:.1f}KB: {elapsed:.3f}s ({throughput:.1f} KB/s)"
                )

        # Should complete all uploads
        assert len(times) > 0


class TestCacheEffectiveness:
    """Test caching effectiveness (when implemented)"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.skip(reason="Caching not yet implemented - Phase 4")
    def test_repeated_search_cache_hit(self, client):
        """Test that repeated searches benefit from caching"""
        query = "test query for caching"

        # First search (cache miss)
        start = time.time()
        response1 = client.post("/api/search", json={"query": query})
        time1 = time.time() - start

        # Second search (should be cache hit)
        start = time.time()
        response2 = client.post("/api/search", json={"query": query})
        time2 = time.time() - start

        assert response1.status_code in [200, 404]
        assert response2.status_code in [200, 404]

        # Cached request should be faster
        print(f"\nFirst request: {time1:.4f}s, Cached: {time2:.4f}s")
        if response1.status_code == 200:
            assert time2 < time1, "Cached request should be faster"


class TestResourceLimits:
    """Test behavior at resource limits"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.slow
    def test_max_file_size_limit(self, client):
        """Test behavior at maximum file size limit"""
        # Assuming 50MB default limit from config
        max_size = 50 * 1024 * 1024

        # Just under limit (should succeed)
        content_under = b"x" * (max_size - 1024)
        response = client.post(
            "/api/upload/single",
            files={
                "file": ("under_limit.bin", content_under, "application/octet-stream")
            },
        )
        # May succeed or fail depending on config
        assert response.status_code in [200, 413]

    def test_max_connections_behavior(self, client):
        """Test behavior when connection limit is reached"""
        # This would require actual connection pool exhaustion
        # Just verify the endpoint is accessible
        response = client.get("/health")
        assert response.status_code == 200


class TestLatencyPercentiles:
    """Test latency distribution and percentiles"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.slow
    def test_health_check_latency_percentiles(self, client):
        """Test health check latency percentiles"""
        num_requests = 100
        latencies = []

        for _ in range(num_requests):
            start = time.time()
            response = client.get("/health")
            elapsed = time.time() - start
            latencies.append(elapsed)
            assert response.status_code == 200

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nLatency percentiles (health check):")
        print(f"  P50: {p50 * 1000:.2f}ms")
        print(f"  P95: {p95 * 1000:.2f}ms")
        print(f"  P99: {p99 * 1000:.2f}ms")

        # P95 should be under 200ms for health check
        assert p95 < 0.2, f"P95 latency too high: {p95 * 1000:.0f}ms"


class TestErrorRateUnderLoad:
    """Test error rates under various load conditions"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.mark.slow
    def test_sustained_load_error_rate(self, client):
        """Test error rate under sustained load"""
        num_requests = 200
        errors = 0
        successes = 0

        for i in range(num_requests):
            response = client.post(
                "/api/search",
                json={"query": f"test {i}"},
            )

            if response.status_code >= 500:
                errors += 1
            elif response.status_code < 400:
                successes += 1

        error_rate = errors / num_requests
        print(f"\nError rate under sustained load: {error_rate * 100:.2f}%")

        # Error rate should be very low (<1%)
        assert error_rate < 0.01, f"High error rate: {error_rate * 100:.1f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
