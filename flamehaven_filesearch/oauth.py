"""
OAuth2/OIDC token validation helpers for FLAMEHAVEN FileSearch.
"""
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional

import jwt

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class OAuthTokenInfo:
    subject: str
    roles: List[str]
    scopes: List[str]
    issuer: Optional[str]
    audience: Optional[str]
    claims: Dict[str, Any]


_jwks_client = None
_jwks_client_url = None


def is_jwt_format(token: str) -> bool:
    return token.count(".") == 2


def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    global _jwks_client, _jwks_client_url
    if _jwks_client is None or _jwks_client_url != jwks_url:
        _jwks_client = jwt.PyJWKClient(jwks_url)
        _jwks_client_url = jwks_url
    return _jwks_client


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in value.replace(",", " ").split() if item]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def validate_oauth_token(token: str, config: Optional[Config] = None) -> Optional[OAuthTokenInfo]:
    config = config or Config.from_env()
    if not config.oauth_enabled:
        return None
    if not token or not is_jwt_format(token):
        return None

    options = {"verify_aud": bool(config.oauth_audience)}
    payload = None

    try:
        if config.oauth_jwt_secret:
            payload = jwt.decode(
                token,
                config.oauth_jwt_secret,
                algorithms=["HS256"],
                audience=config.oauth_audience,
                issuer=config.oauth_issuer,
                options=options,
            )
        elif config.oauth_jwks_url:
            client = _get_jwks_client(config.oauth_jwks_url)
            signing_key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=config.oauth_audience,
                issuer=config.oauth_issuer,
                options=options,
            )
        else:
            return None
    except Exception as e:
        logger.debug("OAuth token validation failed: %s", e)
        return None

    subject = (
        payload.get("sub")
        or payload.get("preferred_username")
        or payload.get("email")
        or "oauth-user"
    )
    roles = []
    for key in ("roles", "role", "groups", "permissions"):
        roles.extend(_normalize_list(payload.get(key)))
    scopes = _normalize_list(payload.get("scope")) + _normalize_list(payload.get("scp"))

    return OAuthTokenInfo(
        subject=subject,
        roles=sorted(set(roles)),
        scopes=sorted(set(scopes)),
        issuer=payload.get("iss"),
        audience=config.oauth_audience,
        claims=payload,
    )


def oauth_permissions(oauth_info: OAuthTokenInfo, config: Optional[Config] = None) -> List[str]:
    config = config or Config.from_env()
    permissions: List[str] = []

    scope_map = {
        "filesearch:search": "search",
        "filesearch:upload": "upload",
        "filesearch:stores": "stores",
        "filesearch:admin": "admin",
    }

    for scope in oauth_info.scopes:
        normalized = scope.strip().lower()
        if normalized in scope_map:
            permissions.append(scope_map[normalized])
        elif normalized in {"search", "upload", "stores", "admin"}:
            permissions.append(normalized)

    for role in oauth_info.roles:
        role_norm = role.strip().lower()
        if role_norm in {"admin", "filesearch-admin", "fs-admin"}:
            permissions.append("admin")
        if role_norm in config.oauth_required_roles:
            permissions.append("admin")

    return sorted(set(permissions))


def oauth_has_admin(oauth_info: OAuthTokenInfo, config: Optional[Config] = None) -> bool:
    config = config or Config.from_env()
    perms = oauth_permissions(oauth_info, config)
    return "admin" in perms
