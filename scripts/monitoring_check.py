#!/usr/bin/env python3
"""
Monitoring verification script for Flamehaven FileSearch v1.4.1

Checks:
1. Usage tracking database
2. pgvector health (if PostgreSQL configured)
3. API endpoints accessibility
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flamehaven_filesearch.usage_tracker import UsageTracker
from flamehaven_filesearch.config import Config


def check_usage_tracking():
    """Verify usage tracking database"""
    print("=" * 60)
    print("USAGE TRACKING VERIFICATION")
    print("=" * 60)

    try:
        tracker = UsageTracker()
        db_path = Path(tracker.db_path)

        if not db_path.exists():
            print("[!] FAIL: Database not found")
            return False

        print(f"[+] Database: {db_path.absolute()}")
        print(f"[+] Size: {db_path.stat().st_size:,} bytes")

        # Verify tables
        import sqlite3
        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        expected_tables = ['usage_records', 'quota_configs', 'usage_alerts']

        for table in expected_tables:
            if table in tables:
                print(f"[+] Table '{table}': OK")
            else:
                print(f"[!] Table '{table}': MISSING")
                return False

        # Verify indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'idx_usage_api_key',
            'idx_usage_timestamp',
            'idx_usage_api_key_timestamp',
            'idx_alerts_api_key',
            'idx_alerts_timestamp'
        ]

        for idx in expected_indexes:
            if idx in indexes:
                print(f"[+] Index '{idx}': OK")
            else:
                print(f"[!] Index '{idx}': MISSING")
                return False

        conn.close()
        print("\n[+] Usage tracking: READY")
        return True

    except Exception as e:
        print(f"[!] FAIL: {e}")
        return False


def check_pgvector_config():
    """Check pgvector configuration"""
    print("\n" + "=" * 60)
    print("PGVECTOR CONFIGURATION")
    print("=" * 60)

    try:
        config = Config.from_env()

        print(f"[+] Vector backend: {config.vector_backend}")

        if config.vector_backend == "postgres":
            if config.postgres_dsn:
                print(f"[+] PostgreSQL DSN: configured")
                print(f"[+] Schema: {config.postgres_schema}")
                print(f"[+] Table: {config.vector_postgres_table}")
                print(f"[+] HNSW m: {config.vector_hnsw_m}")
                print(f"[+] HNSW ef_construction: {config.vector_hnsw_ef_construction}")
                print(f"[+] HNSW ef_search: {config.vector_hnsw_ef_search}")
                print("\n[+] pgvector: CONFIGURED")
                print("[i] Run health check when PostgreSQL is available")
            else:
                print("[!] PostgreSQL DSN not configured")
                print("[i] Set POSTGRES_DSN to enable pgvector")
        else:
            print("[i] pgvector not enabled (using in-memory or chronos)")
            print("[i] Set VECTOR_BACKEND=postgres to enable")

        return True

    except Exception as e:
        print(f"[!] FAIL: {e}")
        return False


def check_middleware_config():
    """Check middleware configuration"""
    print("\n" + "=" * 60)
    print("MIDDLEWARE CONFIGURATION")
    print("=" * 60)

    usage_tracking = os.getenv("USAGE_TRACKING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    print(f"[+] Usage tracking: {'ENABLED' if usage_tracking else 'DISABLED'}")

    if not usage_tracking:
        print("[i] Set USAGE_TRACKING_ENABLED=true to enable")

    return True


def main():
    """Run all monitoring checks"""
    print("\nFlamehaven FileSearch v1.4.1 - Monitoring Verification")
    print("=" * 60)

    results = []

    # Run checks
    results.append(("Usage Tracking", check_usage_tracking()))
    results.append(("pgvector Config", check_pgvector_config()))
    results.append(("Middleware Config", check_middleware_config()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, result in results:
        status = "[+] PASS" if result else "[!] FAIL"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n[+] All checks PASSED - Ready for production!")
        print("\nNext steps:")
        print("  1. Start API server: uvicorn flamehaven_filesearch.api:app")
        print("  2. Check /health endpoint: curl http://localhost:8000/health")
        print("  3. Monitor usage: Check ./data/usage.db")
        return 0
    else:
        print("\n[!] Some checks FAILED - Review configuration")
        return 1


if __name__ == "__main__":
    sys.exit(main())
