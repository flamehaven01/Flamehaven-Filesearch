"""
Lightweight Obsidian Markdown helpers.

Keeps the dependency profile minimal: regex + stdlib only.
Used to preserve a note's internal structure (frontmatter, headings, tags,
wikilinks) during indexing without requiring a full Obsidian integration layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .context_extractor import ContextConfig, ContextExtractor
from .text_chunker import chunk_text, resplit_chunks_character_windows

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"(?<!\!)\[\[([^\]]+)\]\]")
_INLINE_TAG_RE = re.compile(r"(?<![\w/])#(\w[\w/\-]*)", re.UNICODE)


@dataclass
class ObsidianNote:
    frontmatter: Dict[str, Any]
    body: str
    headings: List[str]
    wikilinks: List[str]
    tags: List[str]
    aliases: List[str]

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "headings": self.headings,
            "wikilinks": self.wikilinks,
            "tags": self.tags,
            "aliases": self.aliases,
            "frontmatter": self.frontmatter,
        }


def parse_obsidian_markdown(text: str) -> ObsidianNote:
    frontmatter, body = _split_frontmatter(text or "")
    aliases = _coerce_list(frontmatter.get("aliases"))
    fm_tags = _coerce_list(frontmatter.get("tags"))
    body_tags = _extract_inline_tags(body)
    tags = _dedupe_keep_order(fm_tags + body_tags)
    wikilinks = _extract_wikilinks(body)
    headings = [m.group(2).strip() for m in _HEADING_RE.finditer(body)]
    return ObsidianNote(
        frontmatter=frontmatter,
        body=body.strip(),
        headings=headings,
        wikilinks=wikilinks,
        tags=tags,
        aliases=aliases,
    )


def build_obsidian_embedding_text(note: ObsidianNote) -> str:
    parts: List[str] = []
    title = note.frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        parts.append(f"Title: {title.strip()}")
    if note.aliases:
        parts.append("Aliases: " + ", ".join(note.aliases))
    if note.tags:
        parts.append("Tags: " + ", ".join(f"#{tag}" for tag in note.tags))
    if note.wikilinks:
        parts.append("Links: " + ", ".join(note.wikilinks[:20]))
    if note.headings:
        parts.append("Headings: " + " | ".join(note.headings[:20]))
    if note.body:
        parts.append(note.body)
    return "\n".join(parts).strip()


def build_obsidian_chunks(
    note: ObsidianNote,
    *,
    max_tokens: int = 256,
    min_tokens: int = 32,
    context_window: int = 1,
    resplit_chunk_chars: int = 1200,
    resplit_overlap_chars: int = 160,
) -> List[Dict[str, Any]]:
    chunks = chunk_text(note.body, max_tokens=max_tokens, min_tokens=min_tokens)
    chunks = resplit_chunks_character_windows(
        chunks,
        chunk_size_chars=resplit_chunk_chars,
        chunk_overlap_chars=resplit_overlap_chars,
    )
    enriched = ContextExtractor(
        ContextConfig(window_size=context_window, include_headings=True)
    ).enrich_chunks(chunks)

    out: List[Dict[str, Any]] = []
    for chunk in enriched:
        local_links = _extract_wikilinks(chunk.get("text", ""))
        local_tags = _extract_inline_tags(chunk.get("text", ""))
        prefix: List[str] = []
        if chunk.get("headings"):
            prefix.append("Headings: " + " > ".join(chunk["headings"]))
        if local_tags:
            prefix.append("Tags: " + ", ".join(f"#{tag}" for tag in local_tags))
        if local_links:
            prefix.append("Links: " + ", ".join(local_links[:10]))
        chunk_text_value = chunk.get("text", "")
        if prefix:
            chunk_text_value = "\n".join(prefix + [chunk_text_value])
        out.append(
            {
                "text": chunk_text_value,
                "headings": chunk.get("headings", []),
                "context": chunk.get("context", ""),
                "metadata": {
                    "obsidian_tags": _dedupe_keep_order(note.tags + local_tags),
                    "obsidian_wikilinks": local_links,
                    "obsidian_aliases": note.aliases,
                },
            }
        )
    return out


def _split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    return _parse_simple_frontmatter(raw), text[match.end() :]


def _parse_simple_frontmatter(raw: str) -> Dict[str, Any]:
    """
    Parse a minimal YAML subset used commonly in Obsidian notes.

    Supported:
    - key: value
    - key:
      - item1
      - item2
    """
    result: Dict[str, Any] = {}
    current_list_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key:
            result.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        if ":" not in line:
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            current_list_key = None
            continue
        if not value:
            result[key] = []
            current_list_key = key
            continue
        result[key] = _coerce_scalar(value)
        current_list_key = None
    return result


def _coerce_scalar(value: str) -> Any:
    value = value.strip().strip("\"'")
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        # Handle inline YAML arrays: [item1, item2, item3]
        if cleaned.startswith("[") and cleaned.endswith("]"):
            inner = cleaned[1:-1]
            parts = [p.strip().strip("\"'") for p in inner.split(",")]
            return [p for p in parts if p]
        if "," in cleaned:
            parts = [p.strip() for p in cleaned.split(",")]
            return [p for p in parts if p]
        return [cleaned] if cleaned else []
    return [str(value).strip()]


def _extract_wikilinks(text: str) -> List[str]:
    links: List[str] = []
    for raw in _WIKILINK_RE.findall(text or ""):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            links.append(target)
    return _dedupe_keep_order(links)


def _extract_inline_tags(text: str) -> List[str]:
    return _dedupe_keep_order(_INLINE_TAG_RE.findall(text or ""))


def _dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        key = value.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
