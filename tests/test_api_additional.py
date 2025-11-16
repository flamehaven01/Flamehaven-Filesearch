import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.requests import Request

from flamehaven_filesearch import api
from flamehaven_filesearch.api import (
    app,
    filesearch_exception_handler,
    format_uptime,
    general_exception_handler,
    get_system_info,
    http_exception_handler,
    initialize_services,
    rate_limit_key,
    request_validation_exception_handler,
)
from flamehaven_filesearch.exceptions import ServiceUnavailableError


class AuthenticatedTestClient(TestClient):
    """Custom TestClient that automatically adds API key authentication"""

    def __init__(self, app, api_key=None, **kwargs):
        super().__init__(app, **kwargs)
        self.api_key = api_key
        self.public_endpoints = ["/", "/health", "/prometheus", "/docs", "/openapi.json", "/admin/dashboard"]

    def request(self, method, url, **kwargs):
        """Override request to add authentication header"""
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Add API key for protected endpoints
        if self.api_key and url not in self.public_endpoints:
            if "Authorization" not in kwargs["headers"]:
                kwargs["headers"]["Authorization"] = f"Bearer {self.api_key}"

        return super().request(method, url, **kwargs)


@pytest.fixture
def api_client(test_api_key, temp_db, monkeypatch, key_manager):
    """FastAPI test client with authentication"""
    monkeypatch.setenv("FLAMEHAVEN_API_KEYS_DB", temp_db)
    monkeypatch.setenv("FLAMEHAVEN_ADMIN_KEY", "admin_test_key_12345")
    return AuthenticatedTestClient(app, api_key=test_api_key)


def _build_request():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/tests",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
    }
    request = Request(scope)
    request.state.request_id = "req-test"
    return request


def _parse_json(response):
    return json.loads(response.body.decode())


def test_rate_limit_key_includes_test_marker(monkeypatch):
    fake_request = SimpleNamespace(
        client=SimpleNamespace(host="1.2.3.4", port=1234),
        headers={},
    )
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "unit::test_case")
    assert rate_limit_key(fake_request).endswith(":unit::test_case")

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests::test_repeated_search_memory_leak")
    token = rate_limit_key(fake_request)
    assert "test_repeated_search_memory_leak" in token
    assert token.count(":") >= 2


def test_initialize_services_force_reload():
    initialize_services(force=True)
    assert api.searcher is not None
    assert api.search_cache is not None


@pytest.mark.parametrize(
    "seconds,expected_suffix",
    [
        (5, "s"),
        (120, "m"),
        (3600, "h"),
        (90000, "d"),
    ],
)
def test_format_uptime_formats_duration(seconds, expected_suffix):
    formatted = format_uptime(seconds)
    if expected_suffix == "s":
        assert formatted.endswith("s")
    else:
        assert expected_suffix in formatted


def test_get_system_info_fallback(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("psutil issue")

    monkeypatch.setattr(api.psutil, "cpu_percent", boom)
    monkeypatch.setattr(api.psutil, "virtual_memory", boom)
    monkeypatch.setattr(api.psutil, "disk_usage", boom)

    info = get_system_info()
    assert info == {"error": "unavailable"}


def test_upload_single_file_requires_initialized_searcher(api_client, monkeypatch):
    monkeypatch.setattr(api, "searcher", None, raising=False)
    response = api_client.post(
        "/api/upload/single",
        files={"file": ("data.txt", "hello", "text/plain")},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "SERVICE_UNAVAILABLE"


def test_upload_single_file_logs_cleanup_warning(api_client, monkeypatch, caplog):
    caplog.set_level("WARNING")
    monkeypatch.setattr(
        api.shutil,
        "rmtree",
        lambda path: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
    )
    response = api_client.post(
        "/api/upload/single",
        files={"file": ("valid.txt", "content", "text/plain")},
    )
    assert response.status_code == 200
    assert "Failed to cleanup temp dir" in caplog.text


def test_search_endpoint_surfacing_backend_errors(api_client, monkeypatch):
    initialize_services(force=True)
    api.search_cache.invalidate()

    def failing_search(**kwargs):
        return {"status": "error", "message": "Store missing"}

    monkeypatch.setattr(api.searcher, "search", failing_search)

    response = api_client.post("/api/search", json={"query": "hello"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Store missing"


def test_prometheus_metrics_updates_store_count(api_client, monkeypatch):
    initialize_services(force=True)
    monkeypatch.setattr(api.searcher, "list_stores", lambda: ["default", "reports"])
    response = api_client.get("/prometheus")
    assert response.status_code == 200
    assert "# HELP http_requests_total" in response.text


def test_metrics_endpoint_requires_searcher(api_client, monkeypatch):
    monkeypatch.setattr(api, "searcher", None, raising=False)
    resp = api_client.get("/metrics")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_file_search_exception_handler_formats_response():
    request = _build_request()
    exc = ServiceUnavailableError("Search", "offline")
    response = await filesearch_exception_handler(request, exc)
    assert response.status_code == 503
    payload = _parse_json(response)
    assert payload["request_id"] == "req-test"


@pytest.mark.asyncio
async def test_http_exception_handler_includes_detail():
    request = _build_request()
    exc = HTTPException(status_code=418, detail="teapot")
    response = await http_exception_handler(request, exc)
    assert response.status_code == 418
    assert _parse_json(response)["detail"] == "teapot"


@pytest.mark.asyncio
async def test_general_exception_handler_wraps_runtime_error():
    request = _build_request()
    exc = RuntimeError("unexpected")
    response = await general_exception_handler(request, exc)
    assert response.status_code == 500
    body = _parse_json(response)
    assert body["error"] == "INTERNAL_ERROR"
    assert body["request_id"] == "req-test"


@pytest.mark.asyncio
async def test_request_validation_exception_handler_delegates_when_not_file_error():
    request = _build_request()
    validation = RequestValidationError(
        [{"loc": ("body", "query"), "msg": "field required", "type": "value_error"}]
    )

    response = await request_validation_exception_handler(request, validation)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_request_validation_exception_handler_customizes_file_errors():
    request = _build_request()
    validation = RequestValidationError(
        [{"loc": ("body", "file"), "msg": "Expected UploadFile", "type": "type_error"}]
    )

    response = await request_validation_exception_handler(request, validation)
    assert response.status_code == 400
    assert (
        _parse_json(response)["detail"] == "Invalid filename: Filename cannot be empty"
    )
