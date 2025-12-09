import asyncio

import pytest
from starlette.requests import Request
from fastapi import HTTPException

from flamehaven_filesearch import batch_routes
from flamehaven_filesearch.batch_routes import (
    BatchSearchQuery,
    BatchSearchRequest,
    _execute_batch_parallel,
    _execute_batch_sequential,
    _execute_single_search,
    batch_search,
    batch_search_status,
)
from flamehaven_filesearch.exceptions import FileSearchException


class FakeSearcher:
    def __init__(self, mode: str = "ok"):
        self.mode = mode

    def search(self, query: str, store_name: str = "default", max_sources: int = 5):
        if self.mode == "filesearch_error":
            raise FileSearchException("boom", status_code=400)
        if self.mode == "unexpected_error":
            raise RuntimeError("unexpected")
        return {
            "answer": f"{query}-answer",
            "sources": [{"query": query, "store": store_name}],
        }


@pytest.mark.asyncio
async def test_batch_search_returns_503_when_not_initialized():
    batch_routes.set_searcher(None)
    req = Request({"type": "http", "headers": []})
    payload = BatchSearchRequest(queries=[BatchSearchQuery(query="hello")])

    with pytest.raises(HTTPException) as exc:
        await batch_search(req, payload, api_key=None)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_batch_search_parallel_orders_by_priority(monkeypatch):
    batch_routes.set_searcher(FakeSearcher())
    monkeypatch.setattr(batch_routes, "get_request_id", lambda _: "req-123")

    req = Request({"type": "http", "headers": []})
    req.state.request_id = "req-123"
    payload = BatchSearchRequest(
        queries=[
            BatchSearchQuery(query="low", priority=0),
            BatchSearchQuery(query="high", priority=5),
        ],
        mode="parallel",
        max_results=2,
    )

    response = await batch_search(req, payload, api_key=None)

    assert response.status == "success"
    assert response.total_queries == 2
    assert response.successful == 2
    # Higher priority query should be processed first in parallel sort order
    assert response.results[0].query == "high"
    assert response.results[0].status == "success"


@pytest.mark.asyncio
async def test_execute_single_search_handles_filesearch_exception(monkeypatch):
    batch_routes.set_searcher(FakeSearcher(mode="filesearch_error"))
    query = BatchSearchQuery(query="bad")

    result = await _execute_single_search(query, max_results=2, request_id="req-err")

    assert result.status == "error"
    assert "boom" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_single_search_handles_unexpected_exception(monkeypatch):
    batch_routes.set_searcher(FakeSearcher(mode="unexpected_error"))
    query = BatchSearchQuery(query="oops")

    result = await _execute_single_search(query, max_results=2, request_id="req-err")

    assert result.status == "error"
    assert "Unexpected error" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_batch_sequential_success(monkeypatch):
    batch_routes.set_searcher(FakeSearcher())
    queries = [
        BatchSearchQuery(query="one"),
        BatchSearchQuery(query="two"),
    ]

    results = await _execute_batch_sequential(queries, max_results=3, request_id="req")

    assert len(results) == 2
    assert all(r.status == "success" for r in results)


@pytest.mark.asyncio
async def test_batch_search_status_returns_static_payload():
    payload = await batch_search_status(Request({"type": "http"}))
    assert payload["status"] == "available"
    assert payload["max_queries_per_batch"] == 100
