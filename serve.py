"""
serve.py — Generic local launcher for Flamehaven-Filesearch.

Loads a `.env` file from this directory into the process environment, then
starts the FastAPI server via uvicorn. This is a general convenience for any
local/offline deployment — it contains NO deployment-specific logic. All
deployment choices live in `.env` (which is gitignored).

Usage:
    python serve.py
    # or with a custom env file:
    FAS_ENV_FILE=/path/to/.env python serve.py
"""

import os
from pathlib import Path


def _load_env(env_path: Path) -> int:
    """Load KEY=VALUE lines from an env file into os.environ. Returns count."""
    if not env_path.exists():
        return 0
    loaded = 0
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key:
            os.environ[key] = value
            loaded += 1
    return loaded


def main() -> None:
    here = Path(__file__).parent
    env_file = Path(os.getenv("FAS_ENV_FILE", here / ".env"))
    n = _load_env(env_file)
    print(f"[serve] Loaded {n} env vars from {env_file}")
    print(f"[serve] PERSIST_PATH={os.getenv('PERSIST_PATH', '(disabled)')}")
    print(f"[serve] EMBEDDING_PROVIDER={os.getenv('EMBEDDING_PROVIDER', 'dsp')}")
    print(f"[serve] LLM_PROVIDER={os.getenv('LLM_PROVIDER', 'gemini')}")

    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"[serve] Starting uvicorn on {host}:{port}")
    uvicorn.run("flamehaven_filesearch.api:app", host=host, port=port)


if __name__ == "__main__":
    main()
