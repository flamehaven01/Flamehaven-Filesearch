"""
tools/watch_ingest.py — Auto re-ingest watcher (general utility).

Watches a directory tree and re-uploads changed / new files to a running
Flamehaven-Filesearch server via the REST API. Solves the "manual re-run
on every vault edit" gap without coupling the engine to any deployment.

Design (keeps the engine's zero-required-dep philosophy):
  - Uses `watchdog` if installed (event-based, low latency).
  - Else falls back to a stdlib polling loop (mtime+size+sha1 scan).
  - Local state map detects *real* content changes; combined with the
    server's content-fingerprint dedup, unchanged files are no-ops.
  - Debounce window coalesces editor save-storms into one batch.

Limitations (documented, not hidden):
  - Deletions: the REST API exposes no per-document delete; a removed file
    is logged as a warning but its index entry persists until the store is
    rebuilt / server restarted from a fresh snapshot. Acceptable for
    append-mostly knowledge vaults.
  - Single watcher per store assumed (matches single-writer persistence).

Usage:
    python tools/watch_ingest.py --dir /path/to/vault --store mystore \
        --base-url http://127.0.0.1:8000 --api-key sk_live_xxx

Env fallbacks: FAS_WATCH_DIR, FAS_STORE, FAS_BASE_URL, FAS_API_KEY,
               FAS_WATCH_EXTS (comma list), FAS_WATCH_DEBOUNCE (seconds),
               FAS_WATCH_POLL (seconds, polling-mode interval).
"""

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Dict, Set, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    print("[watch] 'requests' is required: pip install requests", file=sys.stderr)
    sys.exit(1)

_DEFAULT_EXTS = {
    ".md", ".txt", ".pdf", ".docx", ".doc", ".rtf",
    ".xlsx", ".xls", ".pptx", ".ppt", ".hwp", ".hwpx",
}


# mtime-keyed hash cache: path -> (mtime, size, sha1)
# Avoids re-hashing unchanged files every poll cycle on large trees.
_HASH_CACHE: Dict[Path, Tuple[float, int, str]] = {}


def _content_key(path: Path) -> Tuple[int, str]:
    """
    (size, sha1) — the AUTHORITATIVE change signal. Pure mtime touches
    (atomic-save, `touch`, editor rewrites with identical bytes) do NOT
    change this, so they do NOT trigger a re-upload. sha1 covers the
    first 1MB for speed; combined with exact size this is collision-safe
    for document corpora in practice.
    """
    st = path.stat()
    cached = _HASH_CACHE.get(path)
    if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
        return cached[1], cached[2]  # reuse cached sha1, skip re-hash
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(1024 * 1024))
    digest = h.hexdigest()
    _HASH_CACHE[path] = (st.st_mtime, st.st_size, digest)
    return st.st_size, digest


def _scan(root: Path, exts: Set[str]) -> Dict[Path, Tuple[int, str]]:
    out: Dict[Path, Tuple[int, str]] = {}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            try:
                out[p] = _content_key(p)
            except OSError:
                continue
    return out


def _upload(base_url: str, api_key: str, store: str, path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            r = requests.post(
                f"{base_url.rstrip('/')}/api/upload/single",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (path.name, f, "application/octet-stream")},
                data={"store": store},
                timeout=30,
            )
        if r.status_code == 200:
            dedup = ""
            try:
                if r.json().get("deduplicated"):
                    dedup = " (dedup no-op)"
            except Exception:
                pass
            print(f"[watch] ✅ {path.name}{dedup}")
            return True
        if r.status_code == 429:
            print(f"[watch] ⏳ rate limited on {path.name} — will retry next cycle")
            return False
        print(f"[watch] ⚠️ {path.name}: {r.status_code} {r.text[:120]}")
        return False
    except Exception as e:
        print(f"[watch] ❌ {path.name}: {e}")
        return False


# Content keys already pushed to the server this session — gate redundant uploads
_UPLOADED: Dict[Path, Tuple[int, str]] = {}


def _flush(base_url, api_key, store, changed: Set[Path]) -> Set[Path]:
    """Upload paths whose CONTENT changed; return the set that failed (retry)."""
    failed: Set[Path] = set()
    for path in sorted(changed):
        if not path.exists():
            print(f"[watch] 🗑️  {path.name} deleted — index entry persists "
                  f"until store rebuild (see module docstring)")
            _UPLOADED.pop(path, None)
            continue
        try:
            key = _content_key(path)
        except OSError:
            failed.add(path)
            continue
        if _UPLOADED.get(path) == key:
            # mtime-only / spurious event — content identical, skip
            continue
        if _upload(base_url, api_key, store, path):
            _UPLOADED[path] = key
        else:
            failed.add(path)
    return failed


def run_polling(root, exts, base_url, api_key, store, poll, debounce) -> None:
    print(f"[watch] polling mode (watchdog not installed) — interval={poll}s")
    state = _scan(root, exts)
    print(f"[watch] baseline: {len(state)} files under {root}")
    pending: Set[Path] = set()
    last_change = 0.0
    while True:
        time.sleep(poll)
        current = _scan(root, exts)
        for p, sig in current.items():
            if state.get(p) != sig:
                pending.add(p)
                last_change = time.time()
        for p in set(state) - set(current):
            pending.add(p)
            last_change = time.time()
        state = current
        if pending and (time.time() - last_change) >= debounce:
            print(f"[watch] flushing {len(pending)} change(s)")
            failed = _flush(base_url, api_key, store, pending)
            pending = failed  # retry failures next cycle


def run_watchdog(root, exts, base_url, api_key, store, debounce) -> None:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    pending: Set[Path] = set()
    state = {"last": 0.0}

    class H(FileSystemEventHandler):
        def _maybe(self, path_str: str):
            p = Path(path_str)
            if p.suffix.lower() in exts:
                pending.add(p)
                state["last"] = time.time()

        def on_modified(self, e):
            if not e.is_directory:
                self._maybe(e.src_path)

        def on_created(self, e):
            if not e.is_directory:
                self._maybe(e.src_path)

        def on_deleted(self, e):
            if not e.is_directory:
                self._maybe(e.src_path)

    obs = Observer()
    obs.schedule(H(), str(root), recursive=True)
    obs.start()
    print(f"[watch] watchdog mode — watching {root}")
    try:
        while True:
            time.sleep(1)
            if pending and (time.time() - state["last"]) >= debounce:
                batch = set(pending)
                pending.clear()
                print(f"[watch] flushing {len(batch)} change(s)")
                failed = _flush(base_url, api_key, store, batch)
                pending.update(failed)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto re-ingest watcher for Flamehaven-Filesearch")
    ap.add_argument("--dir", default=os.getenv("FAS_WATCH_DIR"))
    ap.add_argument("--store", default=os.getenv("FAS_STORE", "default"))
    ap.add_argument("--base-url", default=os.getenv("FAS_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--api-key", default=os.getenv("FAS_API_KEY"))
    ap.add_argument("--exts", default=os.getenv("FAS_WATCH_EXTS", ""))
    ap.add_argument("--debounce", type=float, default=float(os.getenv("FAS_WATCH_DEBOUNCE", "3.0")))
    ap.add_argument("--poll", type=float, default=float(os.getenv("FAS_WATCH_POLL", "5.0")))
    args = ap.parse_args()

    if not args.dir or not args.api_key:
        print("[watch] --dir and --api-key (or FAS_WATCH_DIR / FAS_API_KEY) required",
              file=sys.stderr)
        sys.exit(2)

    root = Path(args.dir).expanduser().resolve()
    if not root.is_dir():
        print(f"[watch] not a directory: {root}", file=sys.stderr)
        sys.exit(2)

    exts = (
        {e if e.startswith(".") else f".{e}" for e in
         (x.strip().lower() for x in args.exts.split(",")) if e}
        or _DEFAULT_EXTS
    )

    print(f"[watch] dir={root} store={args.store} url={args.base_url} "
          f"exts={sorted(exts)} debounce={args.debounce}s")

    try:
        import watchdog  # noqa: F401
        run_watchdog(root, exts, args.base_url, args.api_key, args.store, args.debounce)
    except ImportError:
        run_polling(root, exts, args.base_url, args.api_key, args.store,
                    args.poll, args.debounce)


if __name__ == "__main__":
    main()
