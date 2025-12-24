"""
PostgreSQL metadata backend integration tests.
Skipped unless POSTGRES_DSN is configured and psycopg is available.
"""
from __future__ import annotations

import os
import uuid

import pytest

from flamehaven_filesearch.config import Config
from flamehaven_filesearch.storage import create_metadata_store

try:
    import psycopg  # type: ignore
except Exception:
    psycopg = None


@pytest.mark.integration
def test_postgres_metadata_store_roundtrip():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn or psycopg is None:
        pytest.skip("POSTGRES_DSN not set or psycopg missing")

    schema = f"fh_test_{uuid.uuid4().hex[:8]}"
    config = Config(
        api_key=None,
        postgres_enabled=True,
        postgres_dsn=dsn,
        postgres_schema=schema,
    )

    try:
        store = create_metadata_store(config)
        store.ensure_store("default")
        store.add_doc(
            "default",
            {
                "title": "example.txt",
                "uri": "local://default/example.txt",
                "content": "hello world",
                "metadata": {"kind": "test"},
            },
        )

        docs = store.get_docs("default")
        assert any(doc.get("title") == "example.txt" for doc in docs)
        assert "default" in store.list_store_names()
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
