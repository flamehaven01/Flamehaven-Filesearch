import logging
from cryptography.fernet import Fernet

from flamehaven_filesearch.encryption import EncryptionService


def test_encryption_roundtrip_with_env_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FLAMEHAVEN_ENC_KEY", key)

    service = EncryptionService.from_env()
    ciphertext = service.encrypt("super-secret")

    assert ciphertext != "super-secret"
    assert service.decrypt(ciphertext) == "super-secret"


def test_encryption_disabled_without_key(monkeypatch):
    monkeypatch.delenv("FLAMEHAVEN_ENC_KEY", raising=False)
    service = EncryptionService()

    assert service.encrypt("plain") == "plain"
    assert service.decrypt("cipher") == "cipher"


def test_decrypt_invalid_token_returns_raw(monkeypatch, caplog):
    key = Fernet.generate_key().decode()
    service = EncryptionService(key)

    caplog.set_level(logging.WARNING)
    result = service.decrypt("not-a-valid-token")

    assert result == "not-a-valid-token"
    assert "Failed to decrypt" in caplog.text
