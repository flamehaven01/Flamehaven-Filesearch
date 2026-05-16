# Flamehaven-Filesearch v1.6.3 Patch Set — Technical Audit Record

> Audience: AI / external auditors. Format: dense, code-level, verifiable.
> Purpose: record exactly what changed, whether it deviates from the
> ORIGINAL DESIGN INTENT, and the better/worse trade-offs.
> Base commit: `5424077` (v1.6.2). Date: 2026-05-16.
>
> RELEASE SCOPE CLARIFICATION (added post-audit, 2026-05-16):
> The v1.6.3 git tag bundles TWO distinct bodies of work:
> (A) The 4 deliberate patches documented in §1–§4 of this audit:
>     P1 search_confidence REST, P2 rate limits, P3 embedding abstraction,
>     P4 snapshot persistence. These are the audit subjects.
> (B) Pre-existing uncommitted work present in the working tree at the time
>     of tagging: Obsidian Light Mode (obsidian_lite.py, knowledge_atom.py,
>     text_chunker.py changes), P5 watcher, P6 query expansion, quality_gate.py
>     (from v1.6.2 era), exact-note resolution hardening, _ingest.py/_search_local.py
>     refactors, P0 bugfixes (live→file, exact_note_match post-P6 regression).
>
> This document audits (A) only. (B) is not in scope — auditors requiring
> full coverage of (B) should treat each sub-component separately.
> The CHANGELOG [1.6.3] entry covers both (A) and (B) as a single release bundle.

---

## 0. Original Design Intent (baseline contract)

Sourced from in-repo docstrings/architecture, treated as the consistency oracle:

| ID | Original invariant | Source |
|----|--------------------|--------|
| INV-1 | Embeddings: zero ML deps, `<1ms`, **deterministic** (same text → same vector) | `engine/embedding_generator.py` class docstring |
| INV-2 | Vector index (ChronosGrid) is **in-memory**; persistence ONLY via PostgreSQL backend | `vector_store.py`, `chronos_grid.py` |
| INV-3 | `search_confidence` is computed by the quality gate and **returned to caller** | `engine/quality_gate.py::compute_search_confidence`, `_search_local.py::_run_hybrid_rerank` |
| INV-4 | Rate limits are safety defaults (10/min upload, 100/min search) | `api.py` decorators |
| INV-5 | Zero-config default behavior must not require new env vars | implicit; `Config` dataclass defaults |

Consistency verdict legend: `PRESERVED` (default path unchanged) · `ADDITIVE` (new opt-in capability) · `RESTORED` (fixes a regression vs intent) · `DEVIATION` (changes behavior when feature enabled).

---

## 1. P1 — `search_confidence` exposure

### 1a. Schema fix (`api.py`)
- **Change**: `class SearchResponse(BaseModel)` gained 3 fields:
  `search_confidence: Optional[float]`, `exact_note_match: Optional[bool]`, `low_confidence: Optional[bool]`.
- **Root cause**: FastAPI serializes through `response_model=SearchResponse`. Pydantic
  drops keys absent from the model. `_local_search` returned `search_confidence`
  internally (INV-3) but it was **silently stripped at the REST boundary**.
- **Consistency**: `RESTORED`. The original intent (INV-3) was for confidence to reach
  the caller. The model omission was a regression; this re-aligns REST output with intent.

### 1b. Provider-path computation (`_search_local.py::_provider_search`)
- **Discovery via audit**: `_provider_search` (used by ALL non-Gemini providers, i.e.
  `LLM_PROVIDER=ollama` — the actual Studio config) **never computed confidence at all**.
  Only `_local_search` (Gemini-absent local fallback) did. So even after 1a, the
  ollama path returned `search_confidence: null`.
- **Change**: added retrieval-path tracking + heuristic confidence:

  | retrieval_path | confidence | trigger |
  |----------------|-----------|---------|
  | `exact_note` | `exact_note[1]` (0.84–0.92) | `_exact_note_resolution` hit |
  | `semantic` | 0.70 | ChronosGrid vector resonance resolved docs |
  | `substring` | 0.55 | raw substring scan fallback |
  | `lexical_backstop` | 0.45 | BM25 lexical backstop |
  | `none` | 0.30 | nothing resolved |

  Return dict now includes `search_confidence` (rounded 4dp), `exact_note_match: true`
  when applicable, `low_confidence: true` when `conf <= 0.45`.
- **Consistency**: `ADDITIVE` + **flagged inconsistency**: this confidence is a
  **path-class heuristic**, NOT the rank-divergence math
  (`compute_search_confidence` = `raw_rrf_score * agreement_factor`) used by
  `_local_search`/`_run_hybrid_rerank`. **Same field name, two different derivations**
  depending on `LLM_PROVIDER`. External consumers MUST NOT compare `search_confidence`
  numerically across Gemini-path vs provider-path responses. This is a known
  semantic split introduced by this patch; documented deliberately.

### Verification (generic — reproduce on any indexed store)
```
query=<exact note title>     → confidence≈0.92  exact_note_match=true   top=<that note>
query=<topical phrase>       → confidence≈0.70  (semantic path)
query=<random nonsense>      → confidence≈0.70  sources>0  ← see §3 risk (DSP)
```

---

## 2. P2 — Configurable rate limits (`api.py`)

- **Change**: module-level `_UPLOAD_SINGLE_RATE`, `_UPLOAD_MULTI_RATE`, `_SEARCH_RATE`
  read from env at import (`UPLOAD_RATE_LIMIT`, `UPLOAD_MULTI_RATE_LIMIT`,
  `SEARCH_RATE_LIMIT`). All 8 `@limiter.limit("…")` decorators (single/multi/search,
  incl. legacy aliases) now reference these vars.
- **Mechanism note**: slowapi resolves the decorator string at import time. Env must
  be set before module import — satisfied by an env-loading launcher (e.g. the
  bundled `serve.py`) or by exporting the vars before `uvicorn`.
- **Defaults unchanged**: `10/minute`, `5/minute`, `100/minute` (INV-4 intact).
- **Consistency**: `PRESERVED`. Zero behavior change unless env override set.
- **Trade-off**: setting e.g. `UPLOAD_RATE_LIMIT=30/minute` weakens an abuse safeguard.
  Acceptable for single-tenant local deploy; document for any multi-tenant exposure.

---

## 3. P3 — Embedding provider abstraction (`engine/embedding_generator.py`)

- **Added**: `class OllamaEmbeddingProvider` (interface-compatible with
  `EmbeddingGenerator`: `generate`, `generate_image_bytes`, `generate_multimodal`,
  `batch_generate`, `get_cache_stats`, `clear_cache`, `vector_dim` property).
- **Added**: `create_embedding_provider(provider, ollama_model, ollama_base_url)`
  factory; `get_embedding_generator()` singleton now routes via factory.
- **Behavior**: `EMBEDDING_PROVIDER=ollama` → calls Ollama `POST /api/embeddings`.
  - probe `/api/tags` on first use; if unreachable or model absent → DSP fallback.
  - 3 consecutive failures → session-level DSP fallback latch.
  - LRU cache (1024) keyed by `model:text[:256]`.
  - `vector_dim` discovered at runtime (e.g. `nomic-embed-text` = 768) — ChronosGrid
    is constructed from `embedding_generator.vector_dim`, so dim change propagates
    correctly within a process.
- **Consistency vs INV-1**:
  - Default `EMBEDDING_PROVIDER=dsp` → `PRESERVED` (DSP unchanged, still <1ms, deterministic, zero-dep).
  - `EMBEDDING_PROVIDER=ollama` → **`DEVIATION` (opt-in)**: breaks determinism
    (neural model), adds network dependency, latency ~5–30ms/embed, requires
    external Ollama process. This is an explicit, gated trade of INV-1 for retrieval
    quality (~78.7% → ~88–92% similarity). Fallback preserves zero-dep guarantee
    when ollama is selected-but-down.
- **Worse / risk**:
  - Quality ceiling raised but ONLY if user runs Ollama; otherwise transparent no-op.
  - `nonsense query → confidence 0.70` (see §1 verification) is the **DSP semantic
    discrimination weakness** (hash collisions always find "something"), NOT a patch
    bug. It is precisely the failure mode P3 exists to remedy. Auditors: low DSP
    discrimination + heuristic provider-path confidence ⇒ provider-path
    `search_confidence` is weak as a relevance gate UNTIL `EMBEDDING_PROVIDER=ollama`.
- **Non-neural alternative (see §3b/P6)**: the DSP *recall* gap (related-but-no-
  lexical-overlap) has a second, INV-1-preserving lever — query expansion — that
  does NOT require engaging the P3 neural deviation. P3 (neural) and P6
  (expansion) are independent and composable.

### 3b. P6 — Non-neural query expansion (`engine/query_expansion.py`)
- **Mechanism**: optional `QueryExpander` loads a deployment-supplied JSON
  `{term: [synonyms]}` map; `IntentRefiner` appends matched synonyms to the
  refined query. DSP = signed-hash feature accumulation ⇒ injecting synonyms
  that occur in target docs adds overlapping hash dims (and BM25 terms),
  raising cosine/recall for zero-lexical-overlap-but-related queries.
- **Consistency**: INV-1 `PRESERVED` (deterministic, zero-dep, no model);
  INV-5 `PRESERVED` (no map ⇒ strict no-op; new config optional).
  Engine ships **mechanism only, zero built-in vocabulary** — domain maps are
  deployment-owned (separation-clean). `ADDITIVE`.
- **Verified**: 4 queries with no lexical overlap to their target note
  (synonym-only reachability) now return the correct note as top hit.
- **Residual limit (honest)**: expansion bridges only *mapped* relations.
  Unmapped novel semantic relations remain the structural DSP floor — that
  subset is closeable solely via P3 (neural). So #2 is *narrowed, not
  eliminated*, by non-neural means; full closure still requires P3.
- **Precision trade-off (honest, measured)**: expansion appends synonyms to
  `refined_query`, which is also what exact-note title matching scores
  against. Observed: query `"Hook Formulas"` (an exact note title) went from
  `exact_note_match=true, conf=0.92` (pre-P6) to `exact=None, conf≈0.70`
  (post-P6) — the synonym dilution drops the title score below the
  exact-note threshold. **Top result stays correct** (`Hook Formulas.md`
  ranked #1), so functional quality holds, but the high-confidence
  exact-note signal is sacrificed for recall. Net: P6 trades exact-title
  precision/confidence for semantic recall. A future refinement is to run
  exact-note resolution on the ORIGINAL (pre-expansion) query; deferred,
  documented rather than hidden.
- **Pre-existing orthogonal bug noted**: `IntentRefiner._find_similar`
  (Levenshtein≤2 typo fuzzing) miscorrects common words (observed:
  `live → file`). Not introduced by this patch set; P6's multi-word match
  uses the raw normalized query so it is robust to it. Flagged for separate
  fix.

---

## 4. P4 — Snapshot persistence (`persistence.py` NEW, `core.py`, `_ingest.py`, `config.py`)

- **Added file** `persistence.py`: `FlamehavenPersistence` (atomic JSON write via
  temp+`os.replace`), `get_persistence()` factory. Layout:
  `{PERSIST_PATH}/stores/{store}_docs.json` `{schema_version, docs[], atoms{}}`.
- **`core.py`**:
  - `__init__`: `self._persistence = get_persistence(config.persist_path)`.
  - on startup (non-native client): `_restore_from_persistence()` →
    reloads `_local_store_docs` + `_atom_store_docs`, **regenerates embeddings
    from persisted `content`**, re-injects into ChronosGrid, marks BM25 dirty.
  - `delete_store()` → also `persistence.delete_store()`.
  - embedding-provider selection wired from `config.embedding_provider`.
- **`_ingest.py`**: after successful local upload → `self._snapshot_store(store)`
  (guarded by `hasattr`, so the mixin stays decoupled).
- **`config.py`**: +`persist_path`, +`embedding_provider`, +`ollama_embedding_model`
  (dataclass defaults, `from_env`, `to_dict`).
- **Consistency vs INV-2 / INV-5**:
  - `PERSIST_PATH` unset → `_persistence is None`, all hooks no-op → `PRESERVED`
    (original in-memory-only / Postgres-only architecture intact; INV-5 intact,
    no new required env).
  - `PERSIST_PATH` set → `ADDITIVE`: a third persistence tier between
    pure-memory and PostgreSQL. Does NOT touch the Postgres path.
- **Design subtlety (positive)**: snapshot stores **content, not vectors**. Restore
  re-embeds. ⇒ snapshot is **embedding-provider-agnostic**: a DSP-era snapshot
  restored under `EMBEDDING_PROVIDER=ollama` yields 768-dim vectors consistently
  (ChronosGrid built from live `vector_dim`). No stale-vector dimension hazard.
- **Worse / risk (must document)**:
  - **Write amplification**: full store JSON rewritten on EVERY upload — O(n) per
    upload, not incremental. 35 docs = 724 KB (fine). At 10⁴+ docs this is a
    throughput concern; future work = append/delta log.
  - **Single-writer assumption**: not thread/process-safe. Multi-worker uvicorn
    would race the snapshot file. Matches existing single-worker default but is a
    hard constraint, not a soft one.
  - Restore cost = re-embed all docs. DSP: 255 docs ≈ ~1.3 s cold (negligible).
    Under `EMBEDDING_PROVIDER=ollama`: 255 × ~5–30 ms + network ⇒ multi-second to
    minutes cold start. Trade-off shifts with P3.

### Verification (restart test — generic)
```
server restart → log: "[Persist] Loaded store '<name>' — <D> docs, <A> atoms"
                       "[Persist] Restored <D+A> documents across <N> stores"
→ store searchable immediately, ZERO re-ingest
   (reference: a 35-doc/220-atom store cold-restores in ~1.3s under DSP;
    previously required a full ~4min REST re-ingest)
```

---

## 5. Net assessment

| Axis | Before | After (default) | After (ollama+persist) |
|------|--------|-----------------|------------------------|
| Confidence observability | none at REST | all paths expose it | same |
| Confidence rigor (provider path) | n/a | heuristic (path-class) | heuristic |
| Restart cost | full re-ingest | full re-ingest (persist off) | ~instant (DSP) / slow (ollama) |
| Retrieval quality | DSP 78.7% | DSP 78.7% | neural 88–92% |
| Determinism (INV-1) | yes | **yes** | no (opt-in) |
| New required config | — | **none** (INV-5 ok) | none |
| External deps added | — | none | Ollama process (opt-in) |

**Consistency summary**: 3 of 4 patches are `PRESERVED`/`RESTORED`/`ADDITIVE` with
zero default-path behavior change. The only `DEVIATION` (P3-ollama, P4-restore-cost)
is strictly opt-in and gated. One **flagged semantic inconsistency**: `search_confidence`
is rank-divergence-derived on the Gemini/local path but path-class-heuristic on the
provider path — same field, two derivations. Do not cross-compare.

**Regressions**: none in default config. Risks are all behind `PERSIST_PATH` /
`EMBEDDING_PROVIDER` opt-in flags and are enumerated above.

## 5b. Deployment bindings — out of scope for this (general) record

This document is the **general, upstreamable patch record** for the
flamehaven-filesearch engine. It deliberately contains NO deployment-specific
configuration, secrets, vault content, or environment bindings.

A given deployment chooses `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `PERSIST_PATH`,
rate limits, etc. via its own (gitignored) `.env`. Those choices — and the
behavioral consequences they pin (e.g. which `search_confidence` derivation is
active per §1b, whether INV-1 holds per §3) — are properties of the *deployment*,
not of the engine, and MUST be documented by the deployment owner, not here.

Auditor guidance: to audit a specific running instance, obtain that deployment's
binding record and combine it with §1–§5 above. The §1b confidence-derivation
split and the §3 INV-1 deviation are real engine properties; whether they are
*active* depends entirely on deployment env flags.

## 6. External re-verification commands
```bash
# P1: confidence present + exact-note semantics (substitute your own store/query)
curl -s -XPOST :8000/api/search -H 'Authorization: Bearer <key>' \
  -d '{"query":"<known title>","store_name":"<store>","search_mode":"hybrid"}' | jq .search_confidence,.exact_note_match
# P2: limits reflect env
python -c "import os;os.environ['SEARCH_RATE_LIMIT']='7/minute';import flamehaven_filesearch.api as a;print(a._SEARCH_RATE)"
# P3: provider routing + DSP fallback
python -c "from flamehaven_filesearch.engine.embedding_generator import create_embedding_provider as f;print(type(f('ollama')).__name__)"
# P4: restart restore (grep server log)
grep -a 'Persist.*Restored' server.log
```
