# Quality Gate — Dogfood Test Results

**Date:** 2026-04-23
**Version:** v1.6.2
**Test file:** `tests/test_quality_gate_integration.py`
**Mode:** offline (`allow_offline=True`) — zero API key required
**Runtime:** ~5.6 s

---

## Checklist (C1–C14) — 14/14 PASS

### Initialization

| # | Target | Result |
|---|---|---|
| C1 | `FlamehavenFileSearch._quality_gate` is `SearchQualityGate` | PASS |
| C2 | `FlamehavenFileSearch._meta_learner` is `SearchMetaLearner` | PASS |
| C3 | `FlamehavenFileSearch._meta_alpha` initialized as `{}` | PASS |

### Keyword path — confidence priors

| # | Target | Result |
|---|---|---|
| C4 | Keyword search with match → `search_confidence == 0.7` | PASS |
| C5 | Keyword search without match → `search_confidence == 0.3` | PASS |

### Hybrid response schema

| # | Target | Result |
|---|---|---|
| C6 | Hybrid search always includes `search_confidence` key | PASS |
| C7 | `search_confidence` is `float` in `[0, 1]` | PASS |
| C8 | `low_confidence` absent on PASS / FORGE results | PASS |

### FORGE path (monkeypatched confidence 0.55–0.60)

| # | Target | Result |
|---|---|---|
| C9 | FORGE verdict: keyword-matched docs appended to sources | PASS |
| C10 | FORGE verdict: `low_confidence` key not present | PASS |

### INHIBIT path (monkeypatched confidence 0.10–0.20)

| # | Target | Result |
|---|---|---|
| C11 | INHIBIT verdict: `low_confidence == True` in response | PASS |
| C12 | INHIBIT verdict: `answer` and `sources` still returned | PASS |

### Meta-learner wiring

| # | Target | Result |
|---|---|---|
| C13 | `meta_learner._total` increments by 1 after each search | PASS |
| C14 | `should_adapt()` returns `True` exactly at `adapt_every` multiple | PASS |

---

## Key Findings

### Coverage delta

| Module | Before | After | Note |
|---|---|---|---|
| `engine/quality_gate.py` | 99% (unit) | 99% (unit) + 58% (integration) | MetaLearner EMA branches hit live |
| `_search_local.py` | 10% | **70%** | Full hybrid / keyword / fallback paths exercised |
| `_ingest.py` | 16% | **58%** | Local upload + chunk atom injection path exercised |
| `engine/hybrid_search.py` | 19% | **94%** | BM25 fit + search + RRF fully exercised |
| `engine/knowledge_atom.py` | 24% | **88%** | chunk_and_inject path reached |
| Total project | 27% | **38.5%** | +11.5 pp from integration suite alone |

### FORGE / INHIBIT strategy

Both paths are tested via `monkeypatch` on `_run_hybrid_rerank` rather than
engineering document content to produce specific Jaccard divergence values.
Rationale: DSP v2.0 vector output for short `.txt` files is deterministic but
not easily controlled to hit a target divergence band. Monkeypatching the one
method that returns `(docs, confidence)` tests the wiring cleanly without
coupling to vector implementation details.

### Temp document lifecycle

Three `.txt` files (retrieval / neural / hybrid topic) created via
`tmp_path_factory` pytest fixture — auto-deleted after module scope completes.
No manual teardown required.

### Offline operation confirmed

`FlamehavenFileSearch(allow_offline=True)` with `Config()` (no API key):
- DSP v2.0 embedding generation: operational
- BM25 index build + search: operational
- ChronosGrid HNSW (memory backend): operational
- KnowledgeAtom chunk injection: operational
- Quality gate + meta-learner: operational

All 14 tests pass with zero network calls.
