from __future__ import annotations

import os
import uuid

import pytest

from flamehaven_filesearch.config import Config
from flamehaven_filesearch.vector_store import create_vector_store

try:
    import pgvector  # type: ignore
    import psycopg  # type: ignore
except Exception:
    psycopg = None
    pgvector = None


@pytest.mark.integration
def test_postgres_vector_store_roundtrip():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn or psycopg is None or pgvector is None:
        pytest.skip("POSTGRES_DSN not set or postgres deps missing")

    schema = f"fh_vec_{uuid.uuid4().hex[:8]}"
    table = f"fh_vectors_{uuid.uuid4().hex[:6]}"
    config = Config(
        api_key=None,
        vector_backend="postgres",
        postgres_dsn=dsn,
        postgres_schema=schema,
        vector_postgres_table=table,
    )

    try:
        store = create_vector_store(config, vector_dim=3)
    except Exception as exc:
        if "vector" in str(exc).lower():
            pytest.skip("pgvector extension not available")
        raise

    try:
        store.add_vector(
            store_name="default",
            glyph="local://default/example.txt",
            vector=[0.1, 0.2, 0.3],
            essence={"file_name": "example.txt", "file_path": "example.txt"},
        )
        results = store.query("default", [0.1, 0.2, 0.3], top_k=1)
        assert results
        assert results[0][0].get("file_name") == "example.txt"
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
