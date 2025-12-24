"""
API Key Authentication & Management for FLAMEHAVEN FileSearch v1.2.0

Provides:
- API key generation and validation
- SQLite-based key storage with hashing
- Per-key metadata (permissions, rate limits)
- Audit logging of key usage
"""

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import jwt

from .encryption import encryption_service

logger = logging.getLogger(__name__)


class APIKeyInfo:
    """API Key information (without secret)"""

    def __init__(
        self,
        key_id: str,
        name: str,
        user_id: str,
        created_at: str,
        last_used: Optional[str],
        is_active: bool,
        rate_limit_per_minute: int,
        permissions: List[str],
    ):
        self.id = key_id
        self.name = name
        self.user_id = user_id
        self.created_at = created_at
        self.last_used = last_used
        self.is_active = is_active
        self.rate_limit_per_minute = rate_limit_per_minute
        self.permissions = permissions

    def to_dict(self) -> dict:
        """Convert to dict (safe for API responses)"""
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "is_active": self.is_active,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "permissions": self.permissions,
        }


class APIKeyManager:
    """Manage API keys: generation, validation, storage"""

    def __init__(self, db_path: str = "./data/flamehaven.db"):
        """Initialize API key manager with database"""
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Ensure database and tables exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create api_keys table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    expires_at TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    rate_limit_per_minute INTEGER DEFAULT 100,
                    permissions TEXT NOT NULL,
                    metadata TEXT,
                    created_at_unix REAL
                )
            """
            )

            # Create api_key_usage table for audit logging
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS api_key_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    endpoint TEXT,
                    method TEXT,
                    status_code INTEGER,
                    duration_ms INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(api_key_id) REFERENCES api_keys(id)
                )
            """
            )

            # Create index for faster lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
                ON api_keys(user_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_id
                ON api_key_usage(api_key_id)
            """
            )

            conn.commit()
            logger.info("API key database initialized at %s", self.db_path)

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash API key using SHA256"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _generate_key_secret() -> str:
        """Generate random API key secret"""
        return f"sk_live_{uuid.uuid4().hex[:32]}"

    def generate_key(
        self,
        user_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        rate_limit_per_minute: int = 100,
        expires_in_days: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[str, str]:
        """
        Generate new API key

        Returns:
            (key_id, plain_key) - Plain key shown only once!
        """
        if permissions is None:
            permissions = ["upload", "search", "stores"]

        key_id = f"key_{uuid.uuid4().hex[:12]}"
        plain_key = self._generate_key_secret()
        key_hash = self._hash_key(plain_key)

        now = datetime.now(timezone.utc)
        created_at = now.isoformat() + "Z"
        expires_at = None

        if expires_in_days:
            expires_at = (now + timedelta(days=expires_in_days)).isoformat() + "Z"

        safe_name = encryption_service.encrypt(name)
        safe_user_id = encryption_service.encrypt(user_id)
        safe_permissions = encryption_service.encrypt(json.dumps(permissions))

        try:
            enc_metadata = None
            if metadata:
                enc_metadata = encryption_service.encrypt(json.dumps(metadata))

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO api_keys
                    (id, name, key_hash, user_id, created_at, expires_at,
                     rate_limit_per_minute, permissions, metadata, created_at_unix)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key_id,
                        safe_name,
                        key_hash,
                        safe_user_id,
                        created_at,
                        expires_at,
                        rate_limit_per_minute,
                        safe_permissions,
                        enc_metadata,
                        now.timestamp(),
                    ),
                )
                conn.commit()

            logger.info("API key generated: %s (user=%s)", key_id, user_id)
            return key_id, plain_key

        except sqlite3.IntegrityError as e:
            logger.error("Failed to generate API key: %s", e)
            raise

    def validate_key(self, plain_key: str) -> Optional[APIKeyInfo]:
        """
        Validate API key and return metadata

        Returns:
            APIKeyInfo if valid and active, None otherwise
        """
        key_hash = self._hash_key(plain_key)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, user_id, created_at, last_used, is_active,
                           rate_limit_per_minute, permissions
                    FROM api_keys
                    WHERE key_hash = ?
                    """,
                    (key_hash,),
                )

                row = cursor.fetchone()

                if not row:
                    return None

                (
                    key_id,
                    name,
                    user_id,
                    created_at,
                    last_used,
                    is_active,
                    rate_limit,
                    perms_json,
                ) = row

                # Normalize SQLite boolean (0/1) to Python bool
                is_active = bool(is_active)

                # Check if key is active
                if not is_active:
                    logger.warning("Attempted use of inactive key: %s", key_id)
                    return None

                # Check if key has expired
                # (expiration check can be added here)

                # Update last_used timestamp
                now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                cursor.execute(
                    "UPDATE api_keys SET last_used = ? WHERE id = ?",
                    (now, key_id),
                )
                conn.commit()

                decrypted_name = encryption_service.decrypt(name) or name
                decrypted_user_id = encryption_service.decrypt(user_id) or user_id
                try:
                    permissions = json.loads(
                        encryption_service.decrypt(perms_json) or perms_json
                    )
                except Exception:
                    permissions = json.loads(perms_json) if perms_json else []

                return APIKeyInfo(
                    key_id=key_id,
                    name=decrypted_name,
                    user_id=decrypted_user_id,
                    created_at=created_at,
                    last_used=last_used,
                    is_active=is_active,
                    rate_limit_per_minute=rate_limit,
                    permissions=permissions,
                )

        except sqlite3.Error as e:
            logger.error("Database error validating key: %s", e)
            return None

    def revoke_key(self, key_id: str) -> bool:
        """Revoke API key"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE api_keys SET is_active = 0 WHERE id = ?",
                    (key_id,),
                )
                conn.commit()
                affected = cursor.rowcount

                if affected > 0:
                    logger.info("API key revoked: %s", key_id)
                    return True
                else:
                    logger.warning("API key not found for revocation: %s", key_id)
                    return False

        except sqlite3.Error as e:
            logger.error("Database error revoking key: %s", e)
            return False

    def list_keys(self, user_id: str) -> List[APIKeyInfo]:
        """List all keys for user (without secret)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, user_id, created_at, last_used, is_active,
                           rate_limit_per_minute, permissions
                    FROM api_keys
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )

                keys = []
                for row in cursor.fetchall():
                    (
                        key_id,
                        name,
                        user,
                        created_at,
                        last_used,
                        is_active,
                        rate_limit,
                        perms_json,
                    ) = row
                    is_active = bool(is_active)
                    try:
                        permissions = json.loads(
                            encryption_service.decrypt(perms_json) or perms_json
                        )
                    except Exception:
                        permissions = json.loads(perms_json) if perms_json else []

                    keys.append(
                        APIKeyInfo(
                            key_id=key_id,
                            name=encryption_service.decrypt(name) or name,
                            user_id=encryption_service.decrypt(user) or user,
                            created_at=created_at,
                            last_used=last_used,
                            is_active=is_active,
                            rate_limit_per_minute=rate_limit,
                            permissions=permissions,
                        )
                    )

                return keys

        except sqlite3.Error as e:
            logger.error("Database error listing keys: %s", e)
            return []

    def log_usage(
        self,
        api_key_id: str,
        request_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: int,
    ):
        """Log API key usage for audit trail"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
                safe_request_id = encryption_service.encrypt(request_id)

                cursor.execute(
                    """
                    INSERT INTO api_key_usage
                    (api_key_id, request_id, endpoint, method, status_code,
                     duration_ms, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        api_key_id,
                        safe_request_id,
                        endpoint,
                        method,
                        status_code,
                        duration_ms,
                        timestamp,
                    ),
                )
                conn.commit()

        except sqlite3.Error as e:
            logger.error("Error logging usage: %s", e)

    def get_usage_stats(self, user_id: Optional[str] = None, days: int = 30) -> dict:
        """Get usage statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total requests
                if user_id:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM api_key_usage u
                        JOIN api_keys k ON u.api_key_id = k.id
                        WHERE k.user_id = ?
                        AND datetime(u.timestamp) > datetime('now', '-' || ? || ' days')
                        """,
                        (user_id, days),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM api_key_usage
                        WHERE datetime(timestamp) > datetime('now', '-' || ? || ' days')
                        """,
                        (days,),
                    )

                total_requests = cursor.fetchone()[0]

                # Requests by endpoint
                if user_id:
                    cursor.execute(
                        """
                        SELECT endpoint, COUNT(*) as count FROM api_key_usage u
                        JOIN api_keys k ON u.api_key_id = k.id
                        WHERE k.user_id = ?
                        AND datetime(u.timestamp) > datetime('now', '-' || ? || ' days')
                        GROUP BY endpoint
                        ORDER BY count DESC
                        """,
                        (user_id, days),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT endpoint, COUNT(*) as count FROM api_key_usage
                        WHERE datetime(timestamp) > datetime('now', '-' || ? || ' days')
                        GROUP BY endpoint
                        ORDER BY count DESC
                        """,
                        (days,),
                    )

                by_endpoint = {row[0]: row[1] for row in cursor.fetchall()}

                # Requests by key
                if user_id:
                    cursor.execute(
                        """
                        SELECT api_key_id, COUNT(*) as count FROM api_key_usage u
                        JOIN api_keys k ON u.api_key_id = k.id
                        WHERE k.user_id = ?
                        AND datetime(u.timestamp) > datetime('now', '-' || ? || ' days')
                        GROUP BY api_key_id
                        ORDER BY count DESC
                        """,
                        (user_id, days),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT api_key_id, COUNT(*) as count FROM api_key_usage
                        WHERE datetime(timestamp) > datetime('now', '-' || ? || ' days')
                        GROUP BY api_key_id
                        ORDER BY count DESC
                        """,
                        (days,),
                    )

                by_key = {row[0]: row[1] for row in cursor.fetchall()}

                return {
                    "period_days": days,
                    "total_requests": total_requests,
                    "by_endpoint": by_endpoint,
                    "by_key": by_key,
                }

        except sqlite3.Error as e:
            logger.error("Error getting usage stats: %s", e)
            return {
                "period_days": days,
                "total_requests": 0,
                "by_endpoint": {},
                "by_key": {},
            }


# Global instance
_key_manager: Optional[APIKeyManager] = None


def get_key_manager(db_path: str = "./data/flamehaven.db") -> APIKeyManager:
    """Get or create API key manager instance"""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager(db_path)
    return _key_manager


class IAMProvider:
    """Pluggable IAM provider (placeholder for future backends)."""

    def validate_admin_token(self, token: str) -> Optional[str]:
        """
        Validate admin token and return user_id if valid, else None.
        Override in real provider (AWS IAM / OIDC, etc.).
        """
        return None


_iam_provider: Optional[IAMProvider] = None


class OIDCIAMProvider(IAMProvider):
    """OIDC-based admin token validator (HS256 shared secret)."""

    def __init__(self, secret: str, issuer: Optional[str], audience: Optional[str]):
        self.secret = secret
        self.issuer = issuer
        self.audience = audience

    def validate_admin_token(self, token: str) -> Optional[str]:
        try:
            options = {"verify_aud": bool(self.audience)}
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                audience=self.audience,
                issuer=self.issuer,
                options=options,
            )
            return (
                payload.get("sub") or payload.get("preferred_username") or "oidc-admin"
            )
        except Exception:
            return None


def get_iam_provider() -> IAMProvider:
    """Return IAM provider singleton."""
    global _iam_provider
    if _iam_provider is None:
        provider = os.getenv("FLAMEHAVEN_IAM_PROVIDER", "default").lower()
        if provider == "oidc":
            secret = os.getenv("FLAMEHAVEN_OIDC_SECRET")
            issuer = os.getenv("FLAMEHAVEN_OIDC_ISSUER")
            audience = os.getenv("FLAMEHAVEN_OIDC_AUDIENCE")
            if secret:
                _iam_provider = OIDCIAMProvider(secret, issuer, audience)
            else:
                logger.warning(
                    "OIDC provider selected but FLAMEHAVEN_OIDC_SECRET missing; "
                    "falling back to default IAM provider"
                )
                _iam_provider = IAMProvider()
        else:
            _iam_provider = IAMProvider()
    return _iam_provider
