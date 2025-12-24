"""
Metadata storage backends for local fallback mode.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .config import Config

logger = logging.getLogger(__name__)


class MetadataStore:
    def ensure_store(self, name: str) -> None:
        raise NotImplementedError

    def add_doc(self, store_name: str, doc: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_docs(self, store_name: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def list_store_names(self) -> List[str]:
        raise NotImplementedError

    def delete_store(self, name: str) -> None:
        raise NotImplementedError


class MemoryMetadataStore(MetadataStore):
    def __init__(self, backing: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self._stores = backing if backing is not None else {}

    def ensure_store(self, name: str) -> None:
        self._stores.setdefault(name, [])

    def add_doc(self, store_name: str, doc: Dict[str, Any]) -> None:
        self._stores.setdefault(store_name, []).append(doc)

    def get_docs(self, store_name: str) -> List[Dict[str, Any]]:
        return list(self._stores.get(store_name, []))

    def list_store_names(self) -> List[str]:
        return list(self._stores.keys())

    def delete_store(self, name: str) -> None:
        self._stores.pop(name, None)


class PostgresMetadataStore(MetadataStore):
    def __init__(self, dsn: str, schema: str = "public"):
        try:
            import psycopg
        except Exception as e:
            raise RuntimeError("psycopg is required for PostgreSQL backend") from e

        self._psycopg = psycopg
        self._dsn = dsn
        self._schema = self._validate_schema(schema)
        self._ensure_schema()

    @staticmethod
    def _validate_schema(schema: str) -> str:
        if not schema:
            return "public"
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
            raise ValueError("Invalid PostgreSQL schema name")
        return schema

    def _ensure_schema(self) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._schema}")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.flamehaven_stores (
                    name TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.flamehaven_docs (
                    id SERIAL PRIMARY KEY,
                    store_name TEXT NOT NULL REFERENCES {self._schema}.flamehaven_stores(name) ON DELETE CASCADE,
                    title TEXT,
                    uri TEXT,
                    content TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS flamehaven_docs_store_idx
                ON {self._schema}.flamehaven_docs(store_name)
                """
            )

    def ensure_store(self, name: str) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            conn.execute(
                f"""
                INSERT INTO {self._schema}.flamehaven_stores(name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                """,
                (name,),
            )

    def add_doc(self, store_name: str, doc: Dict[str, Any]) -> None:
        metadata = doc.get("metadata")
        with self._psycopg.connect(self._dsn) as conn:
            conn.execute(
                f"""
                INSERT INTO {self._schema}.flamehaven_docs
                (store_name, title, uri, content, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    store_name,
                    doc.get("title"),
                    doc.get("uri"),
                    doc.get("content"),
                    json.dumps(metadata) if metadata is not None else None,
                ),
            )

    def get_docs(self, store_name: str) -> List[Dict[str, Any]]:
        with self._psycopg.connect(self._dsn) as conn:
            rows = conn.execute(
                f"""
                SELECT title, uri, content, metadata
                FROM {self._schema}.flamehaven_docs
                WHERE store_name = %s
                ORDER BY id ASC
                """,
                (store_name,),
            ).fetchall()
        return [
            {
                "title": row[0],
                "uri": row[1],
                "content": row[2] or "",
                "metadata": row[3] or {},
            }
            for row in rows
        ]

    def list_store_names(self) -> List[str]:
        with self._psycopg.connect(self._dsn) as conn:
            rows = conn.execute(
                f"SELECT name FROM {self._schema}.flamehaven_stores ORDER BY name"
            ).fetchall()
        return [row[0] for row in rows]

    def delete_store(self, name: str) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            conn.execute(
                f"DELETE FROM {self._schema}.flamehaven_stores WHERE name = %s",
                (name,),
            )


def create_metadata_store(config: Optional[Config] = None) -> MetadataStore:
    config = config or Config.from_env()
    if config.postgres_enabled:
        if not config.postgres_dsn:
            raise RuntimeError("POSTGRES_DSN is required when postgres backend is enabled")
        return PostgresMetadataStore(config.postgres_dsn, schema=config.postgres_schema)
    return MemoryMetadataStore()
