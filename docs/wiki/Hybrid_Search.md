# Hybrid Search: BM25 + RRF

Added in **v1.6.0**. Implemented in `engine/hybrid_search.py` and `engine/knowledge_atom.py`.

---

## Overview

Hybrid search fuses two complementary retrieval signals via Reciprocal Rank Fusion (RRF):

| Signal | Source | Strengths |
|---|---|---|
| **BM25** | `engine/hybrid_search.py` | Exact term match, Korean+English, fast |
| **Semantic** | ChronosGrid (DSP v2.0) | Synonyms, paraphrase, cross-lingual |

The fused ranked list is resolved to document dicts via stable URI lookup.

---

## Activating Hybrid Search

Pass `search_mode="hybrid"` to `search()`:

```python
result = searcher.search(
    "RAG pipeline performance",
    store_name="docs",
    search_mode="hybrid",
)
```

Or via REST API:

```json
POST /api/search
{
  "query": "RAG pipeline performance",
  "store": "docs",
  "search_mode": "hybrid"
}
```

---

## BM25 Engine

```python
from flamehaven_filesearch.engine.hybrid_search import BM25

bm25 = BM25(k1=1.5, b=0.75)
bm25.fit(["document one text", "document two text"])
results = bm25.search("document text", top_k=5)
# [{"id": 0, "score": 1.23}, ...]
```

**Tokenizer:** `re.findall(r"[a-z0-9\uac00-\ud7a3]+", text.lower())`
- ASCII alphanumerics: English, numbers
- `\uac00-\ud7a3`: Korean Hangul syllable block (AC00–D7A3)

**Index lifecycle:**
- Built lazily on first hybrid search after any upload
- Marked dirty (`_bm25_dirty`) when new files are added
- Corpus includes both main docs and KnowledgeAtom chunk atoms

---

## RRF Fusion

```
RRF(doc d) = sum over lists L of [ 1 / (k + rank_L(d)) ]
```

- `k = 60` (standard smoothing constant)
- Doc ID: stable URI string (works across both result lists)
- Outputs top-k fused results, resolved to full doc dicts

---

## KnowledgeAtom Indexing

Each uploaded file produces:
1. **File-level doc** — full content, URI `local://<store>/<encoded_abs_path>`
2. **Chunk atoms** — 800-char windows (120-char overlap), URI `local://<store>/<encoded_abs_path>#c0001`, `#c0002`, ...

Chunks shorter than 80 chars are dropped (noise filter).

Each chunk atom is:
- Embedded via `embedding_generator.generate(chunk_text)`
- Injected into ChronosGrid for semantic retrieval
- Registered in `_atom_store_docs` for URI lookup during RRF resolution

This means hybrid search operates at chunk granularity — a query for a specific
paragraph will surface that paragraph's atom, not just the parent file.

---

## Stable URI Scheme

```
local://<store_name>/<urllib.parse.quote(abs_path, safe='')>
```

Example:
```
local://docs/C%3A%5CUsers%5Cdream%5Cdocs%5Creport.pdf
```

- Globally unique: two files named `README.md` in different directories get different URIs
- Reversible: `urllib.parse.unquote(uri.split("/", 3)[-1])` recovers the absolute path
- Fragment URIs for atoms: append `#c0001` to the base file URI

---

## Search Flow (hybrid mode)

```
search(query, search_mode="hybrid")
  │
  ├─ intent_refiner.refine_intent(query)  → refined query
  │
  ├─ embedding_generator.generate(refined) → query vector
  │
  ├─ _query_vector_backend()
  │   └─ ChronosGrid.seek_vector_resonance(query_vec, top_k=5) → sem_results
  │
  └─ _local_search(search_mode="hybrid", semantic_results=sem_results)
      │
      └─ _run_hybrid_rerank(store_name, query, sem_results)
          │
          ├─ _rebuild_bm25(store_name)  [if dirty]
          │   └─ BM25.fit(docs + atoms)
          │
          ├─ BM25.search(query, top_k=max_sources*2*bm25_multiplier)  → bm25_ranked
          ├─ sem_results → sem_ranked  (URI-keyed)
          │
          ├─ reciprocal_rank_fusion([sem_ranked, bm25_ranked], k=60)
          │
          ├─ compute_search_confidence(raw_score, bm25_uris, sem_uris)
          │   └─ Jaccard rank divergence gate → confidence [0, 1]
          │
          └─ [_get_doc_by_uri(uri) for each fused item]  → (resolved_docs, confidence)
              │
              └─ SearchQualityGate.evaluate(confidence)
                  ├─ PASS   (> 0.75)  → return as-is
                  ├─ FORGE  (> 0.45)  → augment with keyword-matched docs
                  └─ INHIBIT (≤ 0.45) → add low_confidence: true to response
```

---

---

## Quality Gate & Meta-Learner (v1.6.2)

Added in **v1.6.2**. Implemented in `engine/quality_gate.py`. Zero new dependencies
— pure Python stdlib (`math`, `statistics`).

### Confidence Scoring

```python
from flamehaven_filesearch.engine.quality_gate import compute_search_confidence

confidence = compute_search_confidence(
    raw_score=0.8,          # top RRF score, normalised [0, 1]
    bm25_uris=bm25_uri_set, # Set[str] — top-k URIs from BM25
    semantic_uris=sem_uri_set, # Set[str] — top-k URIs from semantic
)
```

**Formula:**
```
divergence  = 1 - |bm25 ∩ semantic| / |bm25 ∪ semantic|   # Jaccard
confidence  = raw_score * max(0, 1 - divergence / 0.5)
```

| Divergence | Factor | Meaning |
|---|---|---|
| 0.0 (full overlap) | 1.00 | Both paths agreed — high trust |
| 0.25 | 0.50 | Moderate disagreement |
| ≥ 0.50 (no overlap) | 0.00 | Complete disagreement — collapsed |

### Quality Gate Verdicts

| Verdict | Condition | Action |
|---|---|---|
| **PASS** | confidence > 0.75 | Return fused results as-is |
| **FORGE** | 0.45 < confidence ≤ 0.75 | Augment with keyword-matched docs (fill gaps) |
| **INHIBIT** | confidence ≤ 0.45 | Return results + `low_confidence: true` in response |

FORGE verdict: after RRF resolution, iterates over `docs` and appends any
non-duplicate URI that produces a valid `_build_snippet()` hit, up to `max_sources`.

### Meta-Learner Alpha Adaptation

`SearchMetaLearner` tracks per-store `(mode, confidence)` history. Every 100
queries, it compares average confidence for semantic/hybrid vs keyword paths and
recommends a new alpha via EMA:

```
alpha_new = 0.70 * alpha_current + 0.30 * alpha_target
```

Alpha controls BM25 candidate pool size in `_run_hybrid_rerank`:

```python
bm25_multiplier = max(0.5, 1.5 - alpha)
bm25_top_k = max(1, int(max_sources * 2 * bm25_multiplier))
```

| alpha | bm25_multiplier | BM25 pool (max_sources=5) |
|---|---|---|
| 0.2 (keyword-dominant) | 1.3× | 13 candidates |
| 0.5 (balanced) | 1.0× | 10 candidates |
| 0.8 (semantic-dominant) | 0.7× | 7 candidates |

Alpha is clamped to [0.2, 0.8]. Stored per-store in `self._meta_alpha`.

---

## Configuration

No new config fields. Controlled by existing `Config`:

| Field | Default | Effect |
|---|---|---|
| `max_sources` | 5 | Top-k for BM25 and RRF output |
| `vector_index_backend` | `"auto"` | Selects ChronosGrid or postgres for semantic leg |

---

## Limitations

- BM25 index is in-memory per store; not persisted across process restarts.
  On restart, the index is rebuilt lazily on first hybrid search.
- Remote (Gemini API) mode does not use BM25. Hybrid mode only applies to
  local and provider-RAG modes.
- Chunk atom granularity is fixed at 800/120-char window/overlap.
  Future: configurable via `Config`.
