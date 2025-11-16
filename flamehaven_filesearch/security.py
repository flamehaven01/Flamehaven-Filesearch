"""
Security & Authentication for FLAMEHAVEN FileSearch v1.2.0

Provides:
- API key extraction and validation
- FastAPI dependency injection for protected routes
- Permission checking
- Request context with user/key information
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from .auth import APIKeyInfo, get_key_manager

logger = logging.getLogger(__name__)


class RequestContext:
    """Request context with authentication information"""

    def __init__(
        self,
        api_key_id: str,
        user_id: str,
        key_name: str,
        permissions: list,
        rate_limit: int,
    ):
        self.api_key_id = api_key_id
        self.user_id = user_id
        self.key_name = key_name
        self.permissions = permissions
        self.rate_limit = rate_limit

    def has_permission(self, permission: str) -> bool:
        """Check if context has specific permission"""
        return permission in self.permissions


# Store context in request state
REQUEST_CONTEXT_KEY = "auth_context"


async def extract_api_key(request: Request) -> str:
    """Extract API key from Authorization header

    Expected format: Authorization: Bearer <key>
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return parts[1]


async def get_current_api_key(
    request: Request, key: str = Depends(extract_api_key)
) -> APIKeyInfo:
    """
    Validate API key and return key information

    Used as FastAPI dependency on protected routes
    """
    key_manager = get_key_manager()
    api_key_info = key_manager.validate_key(key)

    if not api_key_info:
        logger.warning("Invalid API key attempted: %s", key[:10] + "...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Store in request state for later use
    request.state.api_key_info = api_key_info
    request.state.request_context = RequestContext(
        api_key_id=api_key_info.id,
        user_id=api_key_info.user_id,
        key_name=api_key_info.name,
        permissions=api_key_info.permissions,
        rate_limit=api_key_info.rate_limit_per_minute,
    )

    logger.debug(
        "API key validated: %s (user=%s)", api_key_info.id, api_key_info.user_id
    )

    return api_key_info


async def get_request_context(request: Request) -> RequestContext:
    """Get request context (requires prior API key validation)"""
    if not hasattr(request.state, "request_context"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication context",
        )
    return request.state.request_context


def require_permission(permission: str):
    """Dependency to require specific permission

    Example:
        @app.post("/upload")
        async def upload(
            context: RequestContext = Depends(require_permission("upload"))
        ):
            ...
    """

    async def permission_checker(
        context: RequestContext = Depends(get_request_context),
    ) -> RequestContext:
        if not context.has_permission(permission):
            logger.warning(
                "Permission denied: %s (user=%s, required=%s)",
                context.api_key_id,
                context.user_id,
                permission,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return context

    return permission_checker


async def optional_api_key(request: Request) -> Optional[APIKeyInfo]:
    """Extract API key if present, but don't require it

    Used for public endpoints that track usage if authenticated
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header:
        return None

    try:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            key = parts[1]
            key_manager = get_key_manager()
            api_key_info = key_manager.validate_key(key)

            if api_key_info:
                request.state.api_key_info = api_key_info
                request.state.request_context = RequestContext(
                    api_key_id=api_key_info.id,
                    user_id=api_key_info.user_id,
                    key_name=api_key_info.name,
                    permissions=api_key_info.permissions,
                    rate_limit=api_key_info.rate_limit_per_minute,
                )
                return api_key_info
    except Exception as e:
        logger.debug("Error validating optional API key: %s", e)

    return None
