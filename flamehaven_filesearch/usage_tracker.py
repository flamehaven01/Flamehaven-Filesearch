"""
Usage tracking and quota management for Flamehaven FileSearch v1.4.1

Provides:
- Per-key usage tracking (requests, tokens, bytes)
- Quota enforcement (daily/monthly limits)
- Usage reporting and analytics
- Alert thresholds
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class UsageRecord:
    """Single usage record"""

    def __init__(
        self,
        api_key_id: str,
        endpoint: str,
        request_tokens: int = 0,
        response_tokens: int = 0,
        request_bytes: int = 0,
        response_bytes: int = 0,
        duration_ms: float = 0.0,
        status_code: int = 200,
        timestamp: Optional[datetime] = None,
    ):
        self.api_key_id = api_key_id
        self.endpoint = endpoint
        self.request_tokens = request_tokens
        self.response_tokens = response_tokens
        self.total_tokens = request_tokens + response_tokens
        self.request_bytes = request_bytes
        self.response_bytes = response_bytes
        self.total_bytes = request_bytes + response_bytes
        self.duration_ms = duration_ms
        self.status_code = status_code
        self.timestamp = timestamp or datetime.now(timezone.utc)


class QuotaConfig:
    """Quota configuration for an API key"""

    def __init__(
        self,
        daily_requests: int = 10000,
        daily_tokens: int = 1000000,
        monthly_requests: int = 300000,
        monthly_tokens: int = 30000000,
        alert_threshold_pct: float = 80.0,
    ):
        self.daily_requests = daily_requests
        self.daily_tokens = daily_tokens
        self.monthly_requests = monthly_requests
        self.monthly_tokens = monthly_tokens
        self.alert_threshold_pct = alert_threshold_pct


class UsageStats:
    """Usage statistics for a time period"""

    def __init__(
        self,
        total_requests: int = 0,
        total_tokens: int = 0,
        total_bytes: int = 0,
        avg_duration_ms: float = 0.0,
        success_rate: float = 100.0,
        top_endpoints: Optional[List[Tuple[str, int]]] = None,
    ):
        self.total_requests = total_requests
        self.total_tokens = total_tokens
        self.total_bytes = total_bytes
        self.avg_duration_ms = avg_duration_ms
        self.success_rate = success_rate
        self.top_endpoints = top_endpoints or []


class UsageTracker:
    """Track and enforce API usage quotas"""

    def __init__(self, db_path: str = "./data/usage.db"):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create usage database and tables"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Usage records table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    request_tokens INTEGER DEFAULT 0,
                    response_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    request_bytes INTEGER DEFAULT 0,
                    response_bytes INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    duration_ms REAL DEFAULT 0.0,
                    status_code INTEGER DEFAULT 200,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Create indexes for usage_records
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_usage_api_key
                ON usage_records(api_key_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                ON usage_records(timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_usage_api_key_timestamp
                ON usage_records(api_key_id, timestamp)
                """
            )

            # Quota configurations table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quota_configs (
                    api_key_id TEXT PRIMARY KEY,
                    daily_requests INTEGER DEFAULT 10000,
                    daily_tokens INTEGER DEFAULT 1000000,
                    monthly_requests INTEGER DEFAULT 300000,
                    monthly_tokens INTEGER DEFAULT 30000000,
                    alert_threshold_pct REAL DEFAULT 80.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Alert history table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    threshold_pct REAL NOT NULL,
                    current_usage INTEGER NOT NULL,
                    quota_limit INTEGER NOT NULL,
                    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Create indexes for usage_alerts
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alerts_api_key
                ON usage_alerts(api_key_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
                ON usage_alerts(triggered_at)
                """
            )

            conn.commit()
            logger.info(f"[UsageTracker] Database initialized at {self.db_path}")

    def record_usage(self, record: UsageRecord) -> None:
        """Record a single usage event"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_records (
                    api_key_id, endpoint, request_tokens, response_tokens,
                    total_tokens, request_bytes, response_bytes, total_bytes,
                    duration_ms, status_code, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.api_key_id,
                    record.endpoint,
                    record.request_tokens,
                    record.response_tokens,
                    record.total_tokens,
                    record.request_bytes,
                    record.response_bytes,
                    record.total_bytes,
                    record.duration_ms,
                    record.status_code,
                    record.timestamp.isoformat(),
                ),
            )
            conn.commit()

        # Check quotas and trigger alerts if needed
        self._check_quotas(record.api_key_id)

    def set_quota(self, api_key_id: str, quota: QuotaConfig) -> None:
        """Set quota configuration for an API key"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO quota_configs (
                    api_key_id, daily_requests, daily_tokens,
                    monthly_requests, monthly_tokens, alert_threshold_pct,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    api_key_id,
                    quota.daily_requests,
                    quota.daily_tokens,
                    quota.monthly_requests,
                    quota.monthly_tokens,
                    quota.alert_threshold_pct,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            logger.info(f"[UsageTracker] Quota updated for {api_key_id}")

    def get_quota(self, api_key_id: str) -> QuotaConfig:
        """Get quota configuration for an API key"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT daily_requests, daily_tokens, monthly_requests,
                       monthly_tokens, alert_threshold_pct
                FROM quota_configs WHERE api_key_id = ?
                """,
                (api_key_id,),
            ).fetchone()

        if row:
            return QuotaConfig(*row)
        return QuotaConfig()  # Default quota

    def check_quota_exceeded(self, api_key_id: str) -> Dict[str, Any]:
        """Check if any quota is exceeded"""
        quota = self.get_quota(api_key_id)
        now = datetime.now(timezone.utc)

        # Daily usage
        daily_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_stats = self.get_usage_stats(
            api_key_id, start_time=daily_start, end_time=now
        )

        # Monthly usage
        monthly_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_stats = self.get_usage_stats(
            api_key_id, start_time=monthly_start, end_time=now
        )

        result = {
            "exceeded": False,
            "daily": {
                "requests": {
                    "current": daily_stats.total_requests,
                    "limit": quota.daily_requests,
                    "exceeded": daily_stats.total_requests >= quota.daily_requests,
                    "pct": (
                        (daily_stats.total_requests / quota.daily_requests * 100)
                        if quota.daily_requests > 0
                        else 0
                    ),
                },
                "tokens": {
                    "current": daily_stats.total_tokens,
                    "limit": quota.daily_tokens,
                    "exceeded": daily_stats.total_tokens >= quota.daily_tokens,
                    "pct": (
                        (daily_stats.total_tokens / quota.daily_tokens * 100)
                        if quota.daily_tokens > 0
                        else 0
                    ),
                },
            },
            "monthly": {
                "requests": {
                    "current": monthly_stats.total_requests,
                    "limit": quota.monthly_requests,
                    "exceeded": monthly_stats.total_requests >= quota.monthly_requests,
                    "pct": (
                        (monthly_stats.total_requests / quota.monthly_requests * 100)
                        if quota.monthly_requests > 0
                        else 0
                    ),
                },
                "tokens": {
                    "current": monthly_stats.total_tokens,
                    "limit": quota.monthly_tokens,
                    "exceeded": monthly_stats.total_tokens >= quota.monthly_tokens,
                    "pct": (
                        (monthly_stats.total_tokens / quota.monthly_tokens * 100)
                        if quota.monthly_tokens > 0
                        else 0
                    ),
                },
            },
        }

        # Set overall exceeded flag
        result["exceeded"] = any(
            [
                result["daily"]["requests"]["exceeded"],
                result["daily"]["tokens"]["exceeded"],
                result["monthly"]["requests"]["exceeded"],
                result["monthly"]["tokens"]["exceeded"],
            ]
        )

        return result

    def get_usage_stats(
        self,
        api_key_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> UsageStats:
        """Get usage statistics for a time period"""
        with sqlite3.connect(self.db_path) as conn:
            # Build query
            where_clauses = []
            params = []

            if api_key_id:
                where_clauses.append("api_key_id = ?")
                params.append(api_key_id)

            if start_time:
                where_clauses.append("timestamp >= ?")
                params.append(start_time.isoformat())

            if end_time:
                where_clauses.append("timestamp <= ?")
                params.append(end_time.isoformat())

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Get aggregate stats
            row = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total_requests,
                    SUM(total_tokens) as total_tokens,
                    SUM(total_bytes) as total_bytes,
                    AVG(duration_ms) as avg_duration,
                    SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
                FROM usage_records
                {where_sql}
                """,
                params,
            ).fetchone()

            total_requests = row[0] or 0
            total_tokens = row[1] or 0
            total_bytes = row[2] or 0
            avg_duration = row[3] or 0.0
            success_rate = row[4] or 100.0

            # Get top endpoints
            top_endpoints = conn.execute(
                f"""
                SELECT endpoint, COUNT(*) as count
                FROM usage_records
                {where_sql}
                GROUP BY endpoint
                ORDER BY count DESC
                LIMIT 5
                """,
                params,
            ).fetchall()

        return UsageStats(
            total_requests=total_requests,
            total_tokens=total_tokens,
            total_bytes=total_bytes,
            avg_duration_ms=avg_duration,
            success_rate=success_rate,
            top_endpoints=[(ep, cnt) for ep, cnt in top_endpoints],
        )

    def _check_quotas(self, api_key_id: str) -> None:
        """Check quotas and trigger alerts if threshold exceeded"""
        quota = self.get_quota(api_key_id)
        status = self.check_quota_exceeded(api_key_id)

        # Check alert thresholds
        for period in ["daily", "monthly"]:
            for metric in ["requests", "tokens"]:
                usage_pct = status[period][metric]["pct"]
                if usage_pct >= quota.alert_threshold_pct:
                    self._trigger_alert(
                        api_key_id,
                        f"{period}_{metric}",
                        usage_pct,
                        status[period][metric]["current"],
                        status[period][metric]["limit"],
                    )

    def _trigger_alert(
        self,
        api_key_id: str,
        alert_type: str,
        threshold_pct: float,
        current_usage: int,
        quota_limit: int,
    ) -> None:
        """Trigger usage alert"""
        # Check if alert already triggered recently (within last hour)
        with sqlite3.connect(self.db_path) as conn:
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

            existing = conn.execute(
                """
                SELECT id FROM usage_alerts
                WHERE api_key_id = ? AND alert_type = ?
                AND triggered_at > ?
                """,
                (api_key_id, alert_type, one_hour_ago),
            ).fetchone()

            if existing:
                return  # Alert already triggered recently

            # Record new alert
            conn.execute(
                """
                INSERT INTO usage_alerts (
                    api_key_id, alert_type, threshold_pct,
                    current_usage, quota_limit
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (api_key_id, alert_type, threshold_pct, current_usage, quota_limit),
            )
            conn.commit()

        logger.warning(
            f"[UsageAlert] {api_key_id}: {alert_type} at {threshold_pct:.1f}% "
            f"({current_usage}/{quota_limit})"
        )

    def get_recent_alerts(
        self, api_key_id: Optional[str] = None, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent usage alerts"""
        with sqlite3.connect(self.db_path) as conn:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

            if api_key_id:
                rows = conn.execute(
                    """
                    SELECT api_key_id, alert_type, threshold_pct,
                           current_usage, quota_limit, triggered_at
                    FROM usage_alerts
                    WHERE api_key_id = ? AND triggered_at > ?
                    ORDER BY triggered_at DESC
                    """,
                    (api_key_id, cutoff),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT api_key_id, alert_type, threshold_pct,
                           current_usage, quota_limit, triggered_at
                    FROM usage_alerts
                    WHERE triggered_at > ?
                    ORDER BY triggered_at DESC
                    """,
                    (cutoff,),
                ).fetchall()

        return [
            {
                "api_key_id": row[0],
                "alert_type": row[1],
                "threshold_pct": row[2],
                "current_usage": row[3],
                "quota_limit": row[4],
                "triggered_at": row[5],
            }
            for row in rows
        ]

    def cleanup_old_records(self, days: int = 90) -> int:
        """Clean up usage records older than specified days"""
        with sqlite3.connect(self.db_path) as conn:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            cursor = conn.execute(
                "DELETE FROM usage_records WHERE timestamp < ?", (cutoff,)
            )
            deleted = cursor.rowcount

            conn.execute("DELETE FROM usage_alerts WHERE triggered_at < ?", (cutoff,))

            conn.commit()

        logger.info(f"[UsageTracker] Cleaned up {deleted} old records (>{days} days)")
        return deleted


# Singleton instance
_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Get singleton usage tracker instance"""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


def reset_usage_tracker() -> None:
    """Reset singleton (for testing)"""
    global _usage_tracker
    _usage_tracker = None
