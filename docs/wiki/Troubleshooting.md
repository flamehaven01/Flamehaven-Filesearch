# Troubleshooting Guide

This guide expands on the quick tips in `README.md`. Work through the checklist
from top to bottom whenever something behaves unexpectedly.

---

## 1. Environment & Installation

| Symptom | Root Cause | Resolution |
|---------|------------|------------|
| `ModuleNotFoundError: flamehaven_filesearch` | Old pip resolver or partially installed extras | `python -m pip install -U pip` then `pip install -e ".[dev,api]"` |
| `ImportError: No module named 'google'` | `google-genai` extra missing | `pip install flamehaven-filesearch[google]` or set `allow_offline=True` |
| `poetry` / `pipx` virtualenv conflicts | PATH still points to global interpreter | Activate the venv explicitly (`source .venv/bin/activate` or `.\.venv\Scripts\Activate`) |

### Verify installation

```bash
python -m pip check                 # dependency integrity
python -m flamehaven_filesearch.cli --help
python - <<'PY'
from flamehaven_filesearch import FlamehavenFileSearch
print("Version:", FlamehavenFileSearch().config.default_model)
PY
```

---

## 2. API Key & Authentication

1. Run `python - <<'PY'` snippet below to ensure whitespace was trimmed.
   ```python
   import os
   key = os.getenv("GEMINI_API_KEY")
   print("Key length:", len(key or ""))
   print("Contains space:", " " in (key or ""))
   ```
2. Keys copied from emails often include smart quotes—paste them into a plain
   text editor first.
3. For CI, use repository secrets and pass them as `env` in workflows instead of
   committing `.env`.

---

## 3. Server Startup Issues

| Symptom | Fix |
|---------|-----|
| `RuntimeError: Event loop is closed` on Windows | Use `python -m uvicorn flamehaven_filesearch.api:app --reload --loop asyncio` |
| `Address already in use` | Another process occupies `:8000`. Kill it or set `PORT=8080`. |
| Logs show `Service not initialized` | Startup hook failed. Run `ENVIRONMENT=development flamehaven-api` to get verbose tracebacks. |

**Checklist:**

- [ ] `pip check` passes.
- [ ] `GEMINI_API_KEY` exported.
- [ ] `DATA_DIR` writable (default: cwd).
- [ ] `uvicorn` reachable (`which uvicorn`).

---

## 4. Upload Problems

### Hidden & Path Traversal Files

The validators reject filenames containing path separators, reserved names, or
leading dots. The response body includes `detail` explaining the decision. If
you genuinely need to import such files, rename them before upload.

### Large Files (>50MB)

| Option | Description |
|--------|-------------|
| Increase limit | `export MAX_FILE_SIZE_MB=200` before starting the API |
| Split PDFs | Use `pypdf` or `gs` to split into chapters |
| Batch CLI | Call `FlamehavenFileSearch.upload_files([...])` so errors are grouped |

---

## 5. Search Quality

1. **Cache Miss vs Hit** – Check logs for `Cache MISS` messages. First queries
   will be slower (~2-3 s). Repeated queries should drop below 10 ms.
2. **Temperature** – For more deterministic answers set
   `searcher.search(..., temperature=0.1)`.
3. **Max Sources** – Reduce `config.max_sources` to avoid noisy citations.
4. **Prompt Hygiene** – Avoid overly long queries; the validator clamps to 1 000
   characters. Shorter, direct questions produce better answers.

---

## 6. Rate Limiting

Default limits: `10/minute` for uploads, `100/minute` for searches/metrics.

- To override, set environment variable `UPLOAD_RATE_LIMIT=30/minute` (and
  similar for other endpoints) before launching the API.
- During pytest runs the custom `rate_limit_key` isolates suites via the
  `PYTEST_CURRENT_TEST` marker. If you run multiple local servers concurrently,
  export different `RATE_LIMIT_PREFIX` values.

---

## 7. Logging & Diagnostics

| Use Case | Command |
|----------|---------|
| Structured logs | `ENVIRONMENT=production flamehaven-api` (default) |
| Human-readable logs | `ENVIRONMENT=development flamehaven-api` |
| Trace request IDs | `curl -H "X-Request-ID: debug-123" ...` |
| Export Prometheus snapshot | `FLAMEHAVEN_METRICS_ENABLED=1 curl http://localhost:8000/prometheus > metrics.prom` |

If logs are missing, ensure your container runtime pipes STDOUT/STDERR to the
host (e.g., `docker logs`).

---

## 8. Docker & Deployment

| Issue | Resolution |
|-------|------------|
| `ModuleNotFoundError` in container | Rebuild after `pyproject.toml` edits: `docker build --no-cache ...` |
| Volume permissions | Run `docker run -u $(id -u):$(id -g)` or adjust `DATA_DIR` owner |
| Health endpoint unreachable | Ensure reverse proxy forwards `/health` without authentication |

---

## 9. Support Channels

- **GitHub Discussions** for “How do I…” questions.
- **GitHub Issues** for reproducible bugs (include logs & `curl /health` output).
- **Security vulnerabilities**: email `security@flamehaven.space`.

When filing issues, attach:

```
Environment: macOS 14.6, Python 3.11.9, flamehaven-filesearch 1.1.0
Command: curl ...
Expected: ...
Actual: ...
Logs: (attach relevant snippet)
```

Having this information drastically shortens turnaround time.
