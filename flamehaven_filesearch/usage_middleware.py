"""
Usage tracking middleware for Flamehaven FileSearch v1.4.1

Automatically tracks all API requests and enforces quotas.
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from .exceptions import RateLimitExceededError
from .security import REQUEST_CONTEXT_KEY
from .usage_tracker import UsageRecord, get_usage_tracker

logger = logging.getLogger(__name__)


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track API usage and enforce quotas"""

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        if self.enabled:
            self.tracker = get_usage_tracker()
            logger.info("[UsageMiddleware] Usage tracking enabled")

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # Skip tracking for non-API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        # Get API key ID from request context (if authenticated)
        api_key_id = None
        if hasattr(request.state, REQUEST_CONTEXT_KEY):
            context = getattr(request.state, REQUEST_CONTEXT_KEY)
            api_key_id = context.api_key_id

        # If no API key, skip tracking (public endpoints)
        if not api_key_id:
            return await call_next(request)

        # Check quota BEFORE processing request
        quota_status = self.tracker.check_quota_exceeded(api_key_id)
        if quota_status["exceeded"]:
            # Find which quota was exceeded
            exceeded_quotas = []
            for period in ["daily", "monthly"]:
                for metric in ["requests", "tokens"]:
                    if quota_status[period][metric]["exceeded"]:
                        exceeded_quotas.append(
                            f"{period}_{metric}: {quota_status[period][metric]['current']}/{quota_status[period][metric]['limit']}"
                        )

            logger.warning(
                f"[UsageMiddleware] Quota exceeded for {api_key_id}: {exceeded_quotas}"
            )

            raise RateLimitExceededError(
                f"Quota exceeded: {', '.join(exceeded_quotas)}"
            )

        # Track request
        start_time = time.time()
        request_size = int(request.headers.get("content-length", 0))

        # Process request
        response = await call_next(request)

        # Calculate metrics
        duration_ms = (time.time() - start_time) * 1000
        response_size = 0

        # Try to get response size from headers
        if hasattr(response, "headers"):
            response_size = int(response.headers.get("content-length", 0))

        # Estimate token usage (rough approximation: 1 token ≈ 4 characters)
        # For actual token counting, you would integrate with the LLM provider
        request_tokens = request_size // 4
        response_tokens = response_size // 4

        # Record usage
        record = UsageRecord(
            api_key_id=api_key_id,
            endpoint=request.url.path,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            request_bytes=request_size,
            response_bytes=response_size,
            duration_ms=duration_ms,
            status_code=response.status_code,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            self.tracker.record_usage(record)
        except Exception as exc:
            # Don't fail request if usage tracking fails
            logger.error(f"[UsageMiddleware] Failed to record usage: {exc}")

        return response
