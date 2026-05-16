"""
Local probe for Obsidian-light indexing and retrieval.

Indexes a folder of Markdown/text notes with FlamehavenFileSearch in offline mode
and runs a small suite of semantic/hybrid queries. Designed for vault smoke tests,
not long-running production serving.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable

from flamehaven_filesearch import Config, FlamehavenFileSearch


TEXT_EXTS = {".md", ".markdown", ".txt"}


def collect_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTS
    )


def run_probe(
    root: Path,
    store_name: str,
    queries: Iterable[str],
) -> dict:
    cfg = Config(
        api_key=None,
        obsidian_light_mode=True,
        obsidian_chunk_max_tokens=256,
        obsidian_chunk_min_tokens=32,
        obsidian_context_window=1,
    )
    searcher = FlamehavenFileSearch(config=cfg, allow_offline=True)

    files = collect_files(root)
    ingest_started = time.time()
    ingested = 0
    failed: list[dict] = []

    for file_path in files:
        result = searcher.upload_file(str(file_path), store_name=store_name)
        if result.get("status") == "success":
            ingested += 1
        else:
            failed.append({"file": str(file_path), "result": result})

    ingest_elapsed = time.time() - ingest_started

    query_results = []
    for query in queries:
        semantic = searcher.search(query, store_name=store_name, search_mode="semantic")
        hybrid = searcher.search(query, store_name=store_name, search_mode="hybrid")
        query_results.append(
            {
                "query": query,
                "semantic": summarize_result(semantic),
                "hybrid": summarize_result(hybrid),
            }
        )

    atom_count = len(searcher._atom_store_docs.get(store_name, {}))
    doc_count = len(searcher._local_store_docs.get(store_name, []))
    return {
        "root": str(root),
        "store_name": store_name,
        "files_seen": len(files),
        "files_ingested": ingested,
        "files_failed": len(failed),
        "ingest_seconds": round(ingest_elapsed, 3),
        "doc_count": doc_count,
        "atom_count": atom_count,
        "queries": query_results,
        "failures": failed[:20],
    }


def summarize_result(result: dict) -> dict:
    return {
        "status": result.get("status"),
        "answer": (result.get("answer") or "")[:700],
        "sources": result.get("sources") or [],
        "search_confidence": result.get("search_confidence"),
        "low_confidence": result.get("low_confidence", False),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--store", default="probe")
    parser.add_argument("--report")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Repeatable query input. If omitted, built-in defaults are used.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    queries = args.queries or [
        "Collatz and Consciousness",
        "drift-free dreamline",
        "ripple consciousness effect",
        "symbolic AI identity experiment",
        "메타 사고의 경계",
    ]

    report = run_probe(root=root, store_name=args.store, queries=queries)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)

    if args.report:
        Path(args.report).write_text(rendered, encoding="utf-8")

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
