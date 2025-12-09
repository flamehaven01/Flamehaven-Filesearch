"""
Encryption utilities for Flamehaven Filesearch.

Provides optional AES-256-GCM (Fernet) encryption for sensitive fields.
If no key is provided, encryption is disabled but interfaces still work.
"""

import logging
import os
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken

    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback when cryptography missing
    _CRYPTO_AVAILABLE = False
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

logger = logging.getLogger(__name__)


class EncryptionService:
    """Wrapper around Fernet to encrypt/decrypt strings when enabled."""

    def __init__(self, key: Optional[str] = None):
        if key and _CRYPTO_AVAILABLE:
            try:
                # Accept either raw Fernet key or 32-byte base64url
                self._fernet = Fernet(
                    key.encode() if not key.startswith("gAAAA") else key
                )
                self.enabled = True
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Invalid encryption key, disabling encryption: %s", exc)
                self._fernet = None
                self.enabled = False
        else:
            self._fernet = None
            self.enabled = False
            if key and not _CRYPTO_AVAILABLE:
                logger.warning("cryptography not installed; encryption disabled")

    @classmethod
    def from_env(cls, env_var: str = "FLAMEHAVEN_ENC_KEY") -> "EncryptionService":
        key = os.getenv(env_var)
        return cls(key)

    def encrypt(self, plaintext: str) -> str:
        if not self.enabled or self._fernet is None:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        if ciphertext is None:
            return None
        if not self.enabled or self._fernet is None:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            logger.warning("Failed to decrypt ciphertext; returning raw text")
            return ciphertext
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Decryption error: %s", exc)
            return ciphertext


# Global singleton for convenience
encryption_service = EncryptionService.from_env()
