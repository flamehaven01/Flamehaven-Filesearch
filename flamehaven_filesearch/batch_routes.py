"""
Batch Search API for FLAMEHAVEN FileSearch v1.2.0

Allows searching multiple queries in a single request.
Optimized for high-throughput use cases.
"""

import asyncio
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter

from .auth import APIKeyInfo, get_key_manager
from .core import FlamehavenFileSearch
from .exceptions import FileSearchException, exception_to_response
from .metrics import MetricsCollector
from .middlewares import get_request_id
from .security import get_current_api_key
from .validators import validate_search_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Batch"])

# Global searcher reference (from api.py)
searcher: Optional[FlamehavenFileSearch] = None


def set_searcher(s: FlamehavenFileSearch):
    """Set global searcher instance"""
    global searcher
    searcher = s


class BatchSearchQuery(BaseModel):
    """Single query in batch"""
    query: str = Field(..., description="Search query")
    store: str = Field(default="default", description="Store name")
    priority: int = Field(default=0, description="Query priority (0-10)")


class BatchSearchRequest(BaseModel):
    """Batch search request"""
    queries: List[BatchSearchQuery] = Field(
        ..., description="List of search queries"
    )
    mode: str = Field(
        default="sequential", description="sequential or parallel"
    )
    max_results: int = Field(
        default=5, ge=1, le=10, description="Max results per query"
    )


class BatchSearchResult(BaseModel):
    """Result for single query in batch"""
    query: str
    store: str
    status: str
    answer: Optional[str] = None
    sources: Optional[List[dict]] = None
    duration_ms: float
    error: Optional[str] = None


class BatchSearchResponse(BaseModel):
    """Batch search response"""
    status: str
    request_id: str
    total_queries: int
    successful: int
    failed: int
    results: List[BatchSearchResult]
    total_duration_ms: float


@router.post("/batch-search", response_model=BatchSearchResponse)
async def batch_search(
    request: Request,
    batch_request: BatchSearchRequest,
    api_key: APIKeyInfo = Depends(get_current_api_key),
):
    """
    Search multiple queries in a single request (Rate limited: 100/min)

    Supports sequential and parallel execution modes.
    Optimized for batch processing workflows.

    Args:
        batch_request: Batch of queries to search
        mode: sequential (default) or parallel execution

    Returns:
        Results for all queries with status and duration
    """
    if not searcher:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FileSearch service not initialized",
        )

    request_id = get_request_id(request)
    start_time = time.time()

    if len(batch_request.queries) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one query required",
        )

    if len(batch_request.queries) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 queries per batch",
        )

    # Sort by priority if parallel mode
    queries = batch_request.queries
    if batch_request.mode == "parallel":
        queries = sorted(queries, key=lambda q: q.priority, reverse=True)

    results = []
    successful = 0
    failed = 0

    try:
        if batch_request.mode == "parallel":
            # Parallel execution
            results = await _execute_batch_parallel(
                queries, batch_request.max_results, request_id
            )
        else:
            # Sequential execution (default)
            results = await _execute_batch_sequential(
                queries, batch_request.max_results, request_id
            )

        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "error")

        # Record metrics
        total_duration = time.time() - start_time
        MetricsCollector.record_batch_search(
            query_count=len(queries),
            successful=successful,
            duration=total_duration,
        )

        logger.info(
            "[%s] Batch search completed: %d/%d successful in %.2fs",
            request_id,
            successful,
            len(queries),
            total_duration,
        )

        return BatchSearchResponse(
            status="success" if failed == 0 else "partial",
            request_id=request_id,
            total_queries=len(queries),
            successful=successful,
            failed=failed,
            results=results,
            total_duration_ms=round(total_duration * 1000, 2),
        )

    except Exception as e:
        logger.error("[%s] Batch search failed: %s", request_id, e)
        MetricsCollector.record_error(
            error_type="BatchSearchError", endpoint="/api/batch-search"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


async def _execute_batch_sequential(
    queries: List[BatchSearchQuery], max_results: int, request_id: str
) -> List[BatchSearchResult]:
    """Execute queries sequentially"""
    results = []

    for q in queries:
        result = await _execute_single_search(q, max_results, request_id)
        results.append(result)

    return results


async def _execute_batch_parallel(
    queries: List[BatchSearchQuery], max_results: int, request_id: str
) -> List[BatchSearchResult]:
    """Execute queries in parallel"""
    tasks = [
        _execute_single_search(q, max_results, request_id)
        for q in queries
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


async def _execute_single_search(
    query_obj: BatchSearchQuery, max_results: int, request_id: str
) -> BatchSearchResult:
    """Execute single search query"""
    query_start = time.time()

    try:
        # Validate search request
        validate_search_request(query_obj.query)

        # Perform search
        result = await asyncio.to_thread(
            searcher.search,
            query_obj.query,
            store_name=query_obj.store,
            max_sources=max_results,
        )

        duration = time.time() - query_start

        return BatchSearchResult(
            query=query_obj.query,
            store=query_obj.store,
            status="success",
            answer=result.get("answer"),
            sources=result.get("sources"),
            duration_ms=round(duration * 1000, 2),
            error=None,
        )

    except FileSearchException as e:
        duration = time.time() - query_start
        return BatchSearchResult(
            query=query_obj.query,
            store=query_obj.store,
            status="error",
            duration_ms=round(duration * 1000, 2),
            error=str(e),
        )

    except Exception as e:
        duration = time.time() - query_start
        logger.error(
            "[%s] Batch search query failed: %s - %s",
            request_id,
            query_obj.query,
            e,
        )
        return BatchSearchResult(
            query=query_obj.query,
            store=query_obj.store,
            status="error",
            duration_ms=round(duration * 1000, 2),
            error=f"Unexpected error: {str(e)}",
        )


@router.get("/batch-search/status", tags=["Batch"])
async def batch_search_status(request: Request):
    """Get batch search capability status"""
    return {
        "status": "available",
        "max_queries_per_batch": 100,
        "modes": ["sequential", "parallel"],
        "min_queries": 1,
        "supported_since": "v1.2.0",
    }
