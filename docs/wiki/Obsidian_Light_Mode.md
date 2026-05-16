# Obsidian Light Mode

`Flamehaven-Filesearch` now supports a Markdown-first Obsidian ingestion path aimed at dense local vaults such as `STRUCTURA`.

This mode is intentionally light:

- No Obsidian plugin dependency
- No remote sync dependency
- No heavyweight graph database requirement
- Uses local Markdown files as the source of truth

## What It Does

When `obsidian_light_mode` is enabled for `.md` files, the ingest path:

1. Parses Obsidian-style frontmatter
2. Extracts aliases, tags, wikilinks, and headings
3. Builds structure-aware chunks from section and paragraph boundaries
4. Re-splits oversized dense chunks with character windows
5. Enriches each chunk with neighbor context
6. Indexes both file-level docs and chunk-level KnowledgeAtoms

This produces better note-level retrieval than legacy fixed `800`-character chunking.

## Features Added In The Current Unreleased Cycle

- Obsidian-specific metadata extraction
- Context-aware answer synthesis for semantic and provider-RAG paths
- Filename alias + content fingerprint deduplication during ingest
- Exact-file post-filter and lexical backstop
- Title-dominant exact note resolution
- Multi-candidate exact-title arbitration for near-duplicate note names

## Recommended Config

```python
from flamehaven_filesearch import Config

cfg = Config(
    api_key=None,
    obsidian_light_mode=True,
    obsidian_chunk_max_tokens=256,
    obsidian_chunk_min_tokens=32,
    obsidian_context_window=1,
    obsidian_resplit_chunk_chars=1200,
    obsidian_resplit_overlap_chars=160,
)
```

Environment variable equivalents:

```bash
export OBSIDIAN_LIGHT_MODE=true
export OBSIDIAN_CHUNK_MAX_TOKENS=256
export OBSIDIAN_CHUNK_MIN_TOKENS=32
export OBSIDIAN_CONTEXT_WINDOW=1
export OBSIDIAN_RESPLIT_CHUNK_CHARS=1200
export OBSIDIAN_RESPLIT_OVERLAP_CHARS=160
```

## Retrieval Behavior

The retrieval stack is now effectively:

1. Exact note resolution
2. Hybrid BM25 + semantic retrieval
3. Exact-file post-filter
4. Cluster dedupe
5. Contextual answer synthesis

This matters for dense vaults where many related notes share vocabulary.

## Known Behavior

- Strong note-name queries can resolve directly to a canonical note with elevated confidence.
- Near-duplicate titles are arbitrated by title closeness rather than raw semantic spread.
- File-level semantic retrieval can still differ from hybrid on highly derivative note families. Hybrid is the preferred mode for production use.

## Suggested Operating Pattern

- Treat the vault Markdown as the only source of truth.
- Re-index incrementally rather than maintaining a second manual memory store.
- Validate retrieval quality first on a dense folder such as `Library/Reserach Thesis`.
- Promote proven settings to the full vault only after query checks pass.
