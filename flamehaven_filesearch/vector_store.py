"""
Vector store backends for semantic search.
"""
from __future__ import annotations

import json
import logging
import re
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import Config

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """Simple circuit breaker for database connections."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.recovery_timeout
            ):
                logger.info("[CircuitBreaker] Transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise RuntimeError("Circuit breaker is OPEN (database unhealthy)")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("[CircuitBreaker] Transitioning to CLOSED (recovered)")
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            logger.warning("[CircuitBreaker] Failure in HALF_OPEN, back to OPEN")
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            logger.error(
                f"[CircuitBreaker] Failure threshold reached ({self.failure_count}), "
                f"transitioning to OPEN"
            )
            self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("[CircuitBreaker] Manually reset to CLOSED")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0,
):
    """Decorator for exponential backoff retry logic."""

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"[Retry] Attempt {attempt + 1}/{max_retries} failed: {exc}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            f"[Retry] All {max_retries} attempts failed: {exc}"
                        )

            raise last_exception  # type: ignore

        return wrapper

    return decorator


class VectorStore:
    def ensure_store(self, name: str) -> None:
        raise NotImplementedError

    def add_vector(
        self,
        store_name: str,
        glyph: str,
        vector: Any,
        essence: Dict[str, Any],
    ) -> None:
        raise NotImplementedError

    def query(
        self, store_name: str, vector: Any, top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        raise NotImplementedError

    def delete_store(self, name: str) -> None:
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        raise NotImplementedError


class PostgresVectorStore(VectorStore):
    def __init__(
        self,
        dsn: str,
        schema: str,
        table: str,
        vector_dim: int,
        hnsw_m: int,
        hnsw_ef_construction: int,
        hnsw_ef_search: int,
    ):
        try:
            import psycopg
        except Exception as e:
            raise RuntimeError("psycopg is required for PostgreSQL vector store") from e

        try:
            from pgvector.psycopg import register_vector
        except Exception as e:
            raise RuntimeError("pgvector is required for PostgreSQL vector store") from e

        self._psycopg = psycopg
        self._register_vector = register_vector
        self._dsn = dsn
        self._schema = self._validate_identifier(schema) or "public"
        self._table = self._validate_identifier(table) or "flamehaven_vectors"
        self._vector_dim = int(vector_dim)
        self._hnsw_m = int(hnsw_m)
        self._hnsw_ef_construction = int(hnsw_ef_construction)
        self._hnsw_ef_search = int(hnsw_ef_search)

        # Circuit breaker for connection health
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=2,
        )

        self._ensure_schema()

    @staticmethod
    def _validate_identifier(identifier: str) -> str:
        if not identifier:
            return ""
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
            raise ValueError("Invalid PostgreSQL identifier")
        return identifier

    @retry_with_backoff(max_retries=3, initial_delay=0.1, max_delay=2.0)
    def _connect(self):
        """Connect to PostgreSQL with retry and circuit breaker protection."""
        def _do_connect():
            conn = self._psycopg.connect(self._dsn)
            self._register_vector(conn)
            return conn

        return self._circuit_breaker.call(_do_connect)

    def health_check(self) -> Dict[str, Any]:
        """
        Check database health and circuit breaker status.

        Returns:
            Dict with health status, circuit state, and connection test result.
        """
        health_info = {
            "healthy": False,
            "circuit_state": self._circuit_breaker.state.value,
            "failure_count": self._circuit_breaker.failure_count,
            "last_failure_time": self._circuit_breaker.last_failure_time,
        }

        if self._circuit_breaker.state == CircuitState.OPEN:
            health_info["error"] = "Circuit breaker is OPEN"
            return health_info

        try:
            with self._connect() as conn:
                # Simple query to test connection
                result = conn.execute("SELECT 1").fetchone()
                if result and result[0] == 1:
                    health_info["healthy"] = True
                    health_info["connection_test"] = "OK"
        except Exception as exc:
            health_info["error"] = str(exc)
            health_info["connection_test"] = "FAILED"
            logger.error(f"[HealthCheck] Database health check failed: {exc}")

        return health_info

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._schema}")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.{self._table} (
                    id SERIAL PRIMARY KEY,
                    store_name TEXT NOT NULL,
                    glyph TEXT NOT NULL,
                    essence JSONB,
                    embedding vector({self._vector_dim}),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (store_name, glyph)
                )
                """
            )
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self._table}_store_idx
                ON {self._schema}.{self._table}(store_name)
                """
            )
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self._table}_hnsw_idx
                ON {self._schema}.{self._table}
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = {self._hnsw_m}, ef_construction = {self._hnsw_ef_construction})
                """
            )

    def ensure_store(self, name: str) -> None:
        if not name:
            return
        # Store rows are created on demand by insert; no explicit store table.
        return None

    def _prepare_vector(self, vector: Any) -> List[float]:
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        vector_list = [float(v) for v in vector]
        if len(vector_list) != self._vector_dim:
            raise ValueError(
                f"Vector dimension mismatch: expected {self._vector_dim}, got {len(vector_list)}"
            )
        return vector_list

    def add_vector(
        self,
        store_name: str,
        glyph: str,
        vector: Any,
        essence: Dict[str, Any],
    ) -> None:
        if not store_name or not glyph:
            return
        vector_list = self._prepare_vector(vector)
        payload = json.dumps(essence) if essence is not None else None
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self._schema}.{self._table}
                (store_name, glyph, essence, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (store_name, glyph)
                DO UPDATE SET essence = EXCLUDED.essence, embedding = EXCLUDED.embedding
                """,
                (store_name, glyph, payload, vector_list),
            )

    def query(
        self, store_name: str, vector: Any, top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        if not store_name:
            return []
        vector_list = self._prepare_vector(vector)
        top_k = max(1, int(top_k))
        with self._connect() as conn:
            try:
                conn.execute(
                    "SET LOCAL hnsw.ef_search = %s",
                    (self._hnsw_ef_search,),
                )
            except Exception:
                pass
            rows = conn.execute(
                f"""
                SELECT essence, 1 - (embedding <=> %s) AS score
                FROM {self._schema}.{self._table}
                WHERE store_name = %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (vector_list, store_name, vector_list, top_k),
            ).fetchall()
        results: List[Tuple[Dict[str, Any], float]] = []
        for row in rows:
            essence = row[0] or {}
            score = float(row[1]) if row[1] is not None else 0.0
            if isinstance(essence, str):
                try:
                    essence = json.loads(essence)
                except Exception:
                    essence = {}
            results.append((essence, score))
        return results

    def delete_store(self, name: str) -> None:
        if not name:
            return
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {self._schema}.{self._table} WHERE store_name = %s",
                (name,),
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics including health status."""
        stats = {
            "backend": "postgres",
            "table": f"{self._schema}.{self._table}",
            "vector_dim": self._vector_dim,
            "circuit_state": self._circuit_breaker.state.value,
            "circuit_healthy": self._circuit_breaker.state == CircuitState.CLOSED,
        }

        try:
            with self._connect() as conn:
                total = conn.execute(
                    f"SELECT COUNT(*) FROM {self._schema}.{self._table}"
                ).fetchone()[0]
            stats["total_vectors"] = int(total)
        except Exception as exc:
            logger.warning(f"[Stats] Failed to get vector count: {exc}")
            stats["total_vectors"] = -1
            stats["error"] = str(exc)

        return stats


def create_vector_store(
    config: Optional[Config],
    vector_dim: int,
) -> Optional[VectorStore]:
    config = config or Config.from_env()
    if config.vector_backend != "postgres":
        return None
    if not config.postgres_dsn:
        raise RuntimeError("POSTGRES_DSN is required for postgres vector backend")
    return PostgresVectorStore(
        dsn=config.postgres_dsn,
        schema=config.postgres_schema,
        table=config.vector_postgres_table,
        vector_dim=vector_dim,
        hnsw_m=config.vector_hnsw_m,
        hnsw_ef_construction=config.vector_hnsw_ef_construction,
        hnsw_ef_search=config.vector_hnsw_ef_search,
    )
