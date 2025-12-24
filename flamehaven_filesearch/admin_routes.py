"""
Admin routes for API key management in FLAMEHAVEN FileSearch v1.2.0

Endpoints:
- POST /api/admin/keys - Create new API key
- GET /api/admin/keys - List user's API keys
- DELETE /api/admin/keys/{key_id} - Revoke API key
- GET /api/admin/usage - Get usage statistics
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from .auth import get_iam_provider, get_key_manager
from .config import Config
from .oauth import is_jwt_format, oauth_has_admin, validate_oauth_token
from .cache import get_all_cache_stats, reset_all_caches

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# Pydantic models
class CreateAPIKeyRequest(BaseModel):
    """Request to create new API key"""

    name: str = Field(..., description="Friendly name for the key")
    permissions: Optional[List[str]] = Field(
        default=None,
        description="Permissions list. Default: [upload, search, stores]",
    )
    rate_limit_per_minute: int = Field(
        default=100, description="Rate limit in requests per minute"
    )
    expires_in_days: Optional[int] = Field(
        default=None, description="Days until expiration"
    )


class CreateAPIKeyResponse(BaseModel):
    """Response with new API key (shown only once)"""

    id: str
    key: str
    name: str
    created_at: str
    permissions: List[str]
    rate_limit_per_minute: int
    warning: str = (
        "Save your API key in a secure location. " "You won't be able to see it again."
    )


class ListAPIKeysResponse(BaseModel):
    """Response with list of API keys"""

    keys: List[dict]


class UsageStatsResponse(BaseModel):
    """Usage statistics response"""

    period_days: int
    total_requests: int
    by_endpoint: dict
    by_key: dict


# Helper functions


def _get_admin_user(request: Request) -> str:
    """
    Extract admin user identifier

    For now, uses a simple approach:
    - Environment-provided admin key
    - Or derives from request context

    TODO: Implement proper admin authentication in v1.3.0
    """
    import os

    # Simple admin key check for now
    auth_header = request.headers.get("Authorization", "")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key = parts[1]

    config = Config.from_env()
    if config.oauth_enabled and is_jwt_format(key):
        oauth_info = validate_oauth_token(key, config=config)
        if oauth_info and oauth_has_admin(oauth_info, config=config):
            return oauth_info.subject
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required",
        )

    # Admin key validation (placeholder)
    # In production, should use separate admin key management
    admin_key = os.getenv("FLAMEHAVEN_ADMIN_KEY")

    if not admin_key or key != admin_key:
        # IAM provider hook (pluggable)
        iam = get_iam_provider()
        iam_user = iam.validate_admin_token(key)
        if iam_user:
            return iam_user

        # Alternatively, validate as regular API key
        key_manager = get_key_manager()
        api_key_info = key_manager.validate_key(key)

        if not api_key_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Require admin permission on API key
        perms = set(api_key_info.permissions or [])
        if "admin" not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permission required",
            )

        return api_key_info.user_id

    # Admin key authenticated
    return "admin"


# Admin endpoints


@router.post("/keys", response_model=CreateAPIKeyResponse)
async def create_api_key(
    key_data: CreateAPIKeyRequest,
    current_user: str = Depends(_get_admin_user),
):
    """
    Create a new API key

    Requires admin authentication (separate admin key management flow)
    """
    key_manager = get_key_manager()

    try:
        default_permissions = key_data.permissions or [
            "upload",
            "search",
            "stores",
            "admin",
        ]
        key_id, plain_key = key_manager.generate_key(
            user_id=current_user,
            name=key_data.name,
            permissions=default_permissions,
            rate_limit_per_minute=key_data.rate_limit_per_minute,
            expires_in_days=key_data.expires_in_days,
        )

        logger.info(
            "API key created: %s (name=%s, user=%s)",
            key_id,
            key_data.name,
            current_user,
        )

        return {
            "id": key_id,
            "key": plain_key,
            "name": key_data.name,
            "created_at": key_manager.validate_key(plain_key).created_at,
            "permissions": default_permissions,
            "rate_limit_per_minute": key_data.rate_limit_per_minute,
        }

    except Exception as e:
        logger.error("Failed to create API key: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key",
        )


@router.get("/keys", response_model=ListAPIKeysResponse)
async def list_api_keys(
    current_user: str = Depends(_get_admin_user),
):
    """
    List all API keys for current user

    Returns keys without secrets
    """
    key_manager = get_key_manager()

    try:
        keys = key_manager.list_keys(current_user)
        return {"keys": [key.to_dict() for key in keys]}

    except Exception as e:
        logger.error("Failed to list API keys: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys",
        )


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: str = Depends(_get_admin_user),
):
    """
    Revoke (disable) an API key

    The key cannot be used after revocation but is not deleted
    """
    key_manager = get_key_manager()

    try:
        # Verify user owns this key
        keys = key_manager.list_keys(current_user)
        if not any(k.id == key_id for k in keys):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to revoke this key",
            )

        # Revoke the key
        if key_manager.revoke_key(key_id):
            logger.info("API key revoked: %s (user=%s)", key_id, current_user)
            return {"status": "success", "message": "API key revoked"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke API key: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key",
        )


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    days: int = 30,
    current_user: str = Depends(_get_admin_user),
):
    """
    Get API usage statistics for current user

    Parameters:
        days: Number of days to look back (default: 30)
    """
    key_manager = get_key_manager()

    try:
        stats = key_manager.get_usage_stats(user_id=current_user, days=days)
        return stats

    except Exception as e:
        logger.error("Failed to get usage stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage statistics",
        )


@router.get("/cache/stats")
async def get_cache_stats(current_user: str = Depends(_get_admin_user)):
    """
    Return current cache statistics (search/file caches).
    """
    try:
        return get_all_cache_stats()
    except Exception as e:
        logger.error("Failed to get cache stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache stats",
        )


@router.post("/cache/flush")
async def flush_caches(current_user: str = Depends(_get_admin_user)):
    """
    Flush all caches (search + file metadata).
    """
    try:
        reset_all_caches()
        return {"status": "ok", "message": "Caches flushed"}
    except Exception as e:
        logger.error("Failed to flush caches: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to flush caches",
        )
