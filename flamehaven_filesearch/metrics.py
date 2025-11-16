"""
Prometheus metrics for FLAMEHAVEN FileSearch

Comprehensive application metrics for monitoring and alerting.
"""

import logging
import time

import psutil
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

logger = logging.getLogger(__name__)


# Create registry
registry = CollectorRegistry()

# Application info
app_info = Info(
    "flamehaven_filesearch_app", "Application information", registry=registry
)
app_info.info(
    {"version": "1.1.0", "service": "flamehaven-filesearch", "framework": "fastapi"}
)

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

# File upload metrics
file_uploads_total = Counter(
    "file_uploads_total", "Total file uploads", ["status", "store"], registry=registry
)

file_upload_size_bytes = Histogram(
    "file_upload_size_bytes",
    "File upload size in bytes",
    ["store"],
    buckets=(1024, 10240, 102400, 1048576, 10485760, 52428800),  # 1KB to 50MB
    registry=registry,
)

file_upload_duration_seconds = Histogram(
    "file_upload_duration_seconds",
    "File upload duration in seconds",
    ["store"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=registry,
)

# Search metrics
search_requests_total = Counter(
    "search_requests_total",
    "Total search requests",
    ["status", "store"],
    registry=registry,
)

search_duration_seconds = Histogram(
    "search_duration_seconds",
    "Search duration in seconds",
    ["store"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=registry,
)

search_results_count = Histogram(
    "search_results_count",
    "Number of search results returned",
    ["store"],
    buckets=(0, 1, 5, 10, 20, 50, 100),
    registry=registry,
)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total", "Total cache hits", ["cache_type"], registry=registry
)

cache_misses_total = Counter(
    "cache_misses_total", "Total cache misses", ["cache_type"], registry=registry
)

cache_size = Gauge(
    "cache_size", "Current cache size", ["cache_type"], registry=registry
)

# Rate limiting metrics
rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Total rate limit exceeded events",
    ["endpoint"],
    registry=registry,
)

# Error metrics
errors_total = Counter(
    "errors_total", "Total errors", ["error_type", "endpoint"], registry=registry
)

# System metrics
system_cpu_usage_percent = Gauge(
    "system_cpu_usage_percent", "System CPU usage percentage", registry=registry
)

system_memory_usage_percent = Gauge(
    "system_memory_usage_percent", "System memory usage percentage", registry=registry
)

system_disk_usage_percent = Gauge(
    "system_disk_usage_percent", "System disk usage percentage", registry=registry
)

# Store metrics
stores_total = Gauge("stores_total", "Total number of stores", registry=registry)

# Batch search metrics (v1.2.0)
batch_searches_total = Counter(
    "batch_searches_total", "Total batch search requests", registry=registry
)

batch_search_duration_seconds = Histogram(
    "batch_search_duration_seconds",
    "Batch search duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=registry,
)

batch_search_queries = Histogram(
    "batch_search_queries",
    "Number of queries in batch search",
    buckets=(1, 5, 10, 25, 50, 100),
    registry=registry,
)

# Gauge for active requests
active_requests = Gauge(
    "active_requests",
    "Number of requests currently being processed",
    ["method", "endpoint"],
    registry=registry,
)


class MetricsCollector:
    """
    Helper class for collecting and updating metrics
    """

    @staticmethod
    def record_request(method: str, endpoint: str, status: int, duration: float):
        """
        Record HTTP request metrics

        Args:
            method: HTTP method
            endpoint: Endpoint path
            status: HTTP status code
            duration: Request duration in seconds
        """
        http_requests_total.labels(
            method=method, endpoint=endpoint, status=str(status)
        ).inc()

        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
            duration
        )

    @staticmethod
    def record_file_upload(store: str, size_bytes: int, duration: float, success: bool):
        """
        Record file upload metrics

        Args:
            store: Store name
            size_bytes: File size in bytes
            duration: Upload duration in seconds
            success: Whether upload succeeded
        """
        status = "success" if success else "failure"

        file_uploads_total.labels(status=status, store=store).inc()

        if success:
            file_upload_size_bytes.labels(store=store).observe(size_bytes)
            file_upload_duration_seconds.labels(store=store).observe(duration)

    @staticmethod
    def record_search(store: str, duration: float, results_count: int, success: bool):
        """
        Record search metrics

        Args:
            store: Store name
            duration: Search duration in seconds
            results_count: Number of results returned
            success: Whether search succeeded
        """
        status = "success" if success else "failure"

        search_requests_total.labels(status=status, store=store).inc()

        if success:
            search_duration_seconds.labels(store=store).observe(duration)
            search_results_count.labels(store=store).observe(results_count)

    @staticmethod
    def record_cache_hit(cache_type: str):
        """Record cache hit"""
        cache_hits_total.labels(cache_type=cache_type).inc()

    @staticmethod
    def record_cache_miss(cache_type: str):
        """Record cache miss"""
        cache_misses_total.labels(cache_type=cache_type).inc()

    @staticmethod
    def update_cache_size(cache_type: str, size: int):
        """Update cache size gauge"""
        cache_size.labels(cache_type=cache_type).set(size)

    @staticmethod
    def record_rate_limit_exceeded(endpoint: str):
        """Record rate limit exceeded"""
        rate_limit_exceeded_total.labels(endpoint=endpoint).inc()

    @staticmethod
    def record_error(error_type: str, endpoint: str):
        """Record error"""
        errors_total.labels(error_type=error_type, endpoint=endpoint).inc()

    @staticmethod
    def update_system_metrics():
        """
        Update system resource metrics

        Should be called periodically (e.g., every 15 seconds)
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            system_cpu_usage_percent.set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            system_memory_usage_percent.set(memory.percent)

            # Disk usage
            disk = psutil.disk_usage("/")
            system_disk_usage_percent.set(disk.percent)

        except Exception as e:
            logger.warning(f"Failed to update system metrics: {e}")

    @staticmethod
    def update_stores_count(count: int):
        """Update total stores count"""
        stores_total.set(count)

    @staticmethod
    def record_batch_search(query_count: int, successful: int, duration: float):
        """
        Record batch search metrics

        Args:
            query_count: Number of queries in batch
            successful: Number of successful queries
            duration: Total duration in seconds
        """
        batch_searches_total.inc()
        batch_search_queries.observe(query_count)
        batch_search_duration_seconds.observe(duration)


class RequestMetricsContext:
    """
    Context manager for tracking request metrics

    Usage:
        with RequestMetricsContext(method, endpoint):
            # Process request
            pass
    """

    def __init__(self, method: str, endpoint: str):
        self.method = method
        self.endpoint = endpoint
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        active_requests.labels(method=self.method, endpoint=self.endpoint).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        active_requests.labels(method=self.method, endpoint=self.endpoint).dec()

        # Determine status code
        if exc_type is None:
            status = 200
        elif hasattr(exc_val, "status_code"):
            status = exc_val.status_code
        else:
            status = 500

        # Record metrics
        MetricsCollector.record_request(self.method, self.endpoint, status, duration)


def get_metrics_text() -> bytes:
    """
    Get Prometheus metrics in text format

    Returns:
        Metrics in Prometheus text format
    """
    # Update system metrics before generating output
    MetricsCollector.update_system_metrics()

    return generate_latest(registry)


def get_metrics_content_type() -> str:
    """
    Get Prometheus metrics content type

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST


# Metric name constants for easy reference
class MetricNames:
    """Constants for metric names"""

    HTTP_REQUESTS_TOTAL = "http_requests_total"
    HTTP_REQUEST_DURATION = "http_request_duration_seconds"
    FILE_UPLOADS_TOTAL = "file_uploads_total"
    FILE_UPLOAD_SIZE = "file_upload_size_bytes"
    FILE_UPLOAD_DURATION = "file_upload_duration_seconds"
    SEARCH_REQUESTS_TOTAL = "search_requests_total"
    SEARCH_DURATION = "search_duration_seconds"
    SEARCH_RESULTS_COUNT = "search_results_count"
    CACHE_HITS_TOTAL = "cache_hits_total"
    CACHE_MISSES_TOTAL = "cache_misses_total"
    CACHE_SIZE = "cache_size"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded_total"
    ERRORS_TOTAL = "errors_total"
    SYSTEM_CPU_USAGE = "system_cpu_usage_percent"
    SYSTEM_MEMORY_USAGE = "system_memory_usage_percent"
    SYSTEM_DISK_USAGE = "system_disk_usage_percent"
    STORES_TOTAL = "stores_total"
    ACTIVE_REQUESTS = "active_requests"


# Example metrics output
EXAMPLE_METRICS_OUTPUT = """
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",endpoint="/api/search",status="200"} 150.0

# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="POST",endpoint="/api/search",le="0.1"} 50.0
http_request_duration_seconds_bucket{method="POST",endpoint="/api/search",
le="0.5"} 120.0
http_request_duration_seconds_sum{method="POST",endpoint="/api/search"} 45.2
http_request_duration_seconds_count{method="POST",endpoint="/api/search"} 150.0

# HELP cache_hits_total Total cache hits
# TYPE cache_hits_total counter
cache_hits_total{cache_type="search"} 89.0

# HELP system_cpu_usage_percent System CPU usage percentage
# TYPE system_cpu_usage_percent gauge
system_cpu_usage_percent 25.3
"""
