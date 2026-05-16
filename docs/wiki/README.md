# Documentation Hub

Versioned documentation for `Flamehaven-Filesearch`.

## Core Guides

| Topic | Description |
|---|---|
| [API Reference](API_Reference.md) | REST endpoints, request and response schemas, auth expectations |
| [Architecture](Architecture.md) | System layers, ingestion flow, retrieval flow, storage layout |
| [Configuration](Configuration.md) | Environment variables, config fields, provider/backend options |
| [Document Parsing](Document_Parsing.md) | Supported formats and extraction behavior |
| [Hybrid Search](Hybrid_Search.md) | BM25, semantic retrieval, RRF, KnowledgeAtom flow |
| [Benchmarks](Benchmarks.md) | Performance notes and measurement approach |
| [Framework Integrations](Framework_Integrations.md) | LangChain, LlamaIndex, Haystack, CrewAI adapters |
| [Production Deployment](Production_Deployment.md) | Docker and service deployment guidance |
| [Troubleshooting](Troubleshooting.md) | Common failures and remediation steps |

## Obsidian / Vault Operations

| Topic | Description |
|---|---|
| [Obsidian Light Mode](Obsidian_Light_Mode.md) | Markdown-first vault indexing, structure extraction, exact note resolution |
| [Release and Tagging](Release_and_Tagging.md) | Changelog discipline, release flow, and git tag policy |

## Notes

- Documentation in this folder should track unreleased code changes before a git tag is created.
- When a feature changes search behavior, update both the user-facing guide and `CHANGELOG.md`.
