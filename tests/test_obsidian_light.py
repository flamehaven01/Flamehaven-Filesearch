import pytest
from urllib.parse import quote

from flamehaven_filesearch import Config, FlamehavenFileSearch
from flamehaven_filesearch.engine.obsidian_lite import (
    build_obsidian_chunks,
    build_obsidian_embedding_text,
    parse_obsidian_markdown,
)


def test_parse_obsidian_markdown_extracts_structure():
    text = (
        "---\n"
        "title: Memory Note\n"
        "tags:\n"
        "  - project/memory\n"
        "  - obsidian\n"
        "aliases:\n"
        "  - Infinite Memory\n"
        "---\n"
        "# Alpha\n"
        "Links to [[Graph Memory|graph]] and [[Vault/Note#Section]].\n\n"
        "Inline tag #retrieval appears here.\n"
    )

    note = parse_obsidian_markdown(text)

    assert note.frontmatter["title"] == "Memory Note"
    assert note.aliases == ["Infinite Memory"]
    assert note.headings == ["Alpha"]
    assert "project/memory" in note.tags
    assert "retrieval" in note.tags
    assert note.wikilinks == ["Graph Memory", "Vault/Note"]


def test_obsidian_embedding_text_includes_metadata():
    note = parse_obsidian_markdown(
        "---\n"
        "title: My Note\n"
        "tags: memory, graph\n"
        "---\n"
        "# Section\n"
        "See [[Target Note]]."
    )

    embedding_text = build_obsidian_embedding_text(note)

    assert "Title: My Note" in embedding_text
    assert "#memory" in embedding_text
    assert "Target Note" in embedding_text
    assert "Section" in embedding_text


def test_build_obsidian_chunks_preserves_headings_and_links():
    note = parse_obsidian_markdown(
        "# Root\n"
        "This chunk references [[Linked Note]] and #tagged context.\n\n"
        "## Child\n"
        "Additional details for retrieval quality."
    )

    chunks = build_obsidian_chunks(note, max_tokens=20, min_tokens=1, context_window=1)

    assert chunks
    assert any(chunk.get("headings") for chunk in chunks)
    assert any(
        "Linked Note" in chunk.get("metadata", {}).get("obsidian_wikilinks", [])
        for chunk in chunks
    )


def test_build_obsidian_chunks_resplits_dense_section():
    note = parse_obsidian_markdown(
        "# Root\n" + ("Dense paragraph for resplitting. " * 120)
    )

    chunks = build_obsidian_chunks(
        note,
        max_tokens=400,
        min_tokens=1,
        context_window=0,
        resplit_chunk_chars=220,
        resplit_overlap_chars=40,
    )

    assert len(chunks) >= 2
    assert all(len(chunk["text"]) <= 260 for chunk in chunks)


@pytest.fixture
def offline_obsidian_searcher():
    config = Config(api_key=None, obsidian_light_mode=True)
    return FlamehavenFileSearch(config=config, allow_offline=True)


def test_upload_file_obsidian_light_indexes_note_structure(
    offline_obsidian_searcher, tmp_path
):
    note_path = tmp_path / "vault_note.md"
    note_path.write_text(
        "---\n"
        "title: Vault Note\n"
        "tags:\n"
        "  - memory\n"
        "---\n"
        "# Hub\n"
        "Connects to [[System Map]] and #retrieval patterns.\n\n"
        "## Detail\n"
        "Chunk content for semantic retrieval and local snippets.\n",
        encoding="utf-8",
    )

    result = offline_obsidian_searcher.upload_file(str(note_path), store_name="vault")

    assert result["status"] == "success"
    docs = offline_obsidian_searcher._local_store_docs["vault"]
    assert docs[0]["metadata"]["obsidian"]["wikilinks"] == ["System Map"]

    atoms = list(offline_obsidian_searcher._atom_store_docs["vault"].values())
    assert atoms
    assert any(atom["metadata"].get("headings") for atom in atoms)
    assert any(
        "retrieval" in atom["metadata"].get("obsidian_tags", []) for atom in atoms
    )


def test_upload_file_deduplicates_filename_alias_with_same_content(
    offline_obsidian_searcher, tmp_path
):
    first_path = tmp_path / "Graph Memory.md"
    second_path = tmp_path / "graph-memory.txt"
    content = "# Graph Memory\nShared note body for dedupe.\n"
    first_path.write_text(content, encoding="utf-8")
    second_path.write_text(content, encoding="utf-8")

    first = offline_obsidian_searcher.upload_file(str(first_path), store_name="vault")
    second = offline_obsidian_searcher.upload_file(str(second_path), store_name="vault")

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["deduplicated"] is True
    assert len(offline_obsidian_searcher._local_store_docs["vault"]) == 1


def test_semantic_search_uses_neighbor_context_in_answer(
    offline_obsidian_searcher, tmp_path
):
    note_path = tmp_path / "contextual_note.md"
    note_path.write_text(
        "# Hub\n"
        "This hub explains the surrounding architecture and bridge context.\n\n"
        "## Detail\n"
        "The resonance manifold is stabilized by the local bridge anchor token.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(note_path), store_name="vault")
    result = offline_obsidian_searcher.search(
        "bridge anchor token",
        store_name="vault",
        search_mode="semantic",
    )

    assert result["status"] == "success"
    assert "bridge anchor token" in result["answer"].lower()
    assert "surrounding architecture" in result["answer"].lower()


def test_provider_rag_prompt_includes_contextual_chunk_text(
    offline_obsidian_searcher, tmp_path
):
    note_path = tmp_path / "provider_note.md"
    note_path.write_text(
        "# Parent\n"
        "Parent context is important for synthesis.\n\n"
        "## Child\n"
        "Precise semantic target lives in this child section.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(note_path), store_name="vault")
    atoms = list(offline_obsidian_searcher._atom_store_docs["vault"].values())
    target_atom = next(atom for atom in atoms if "semantic target" in atom["content"])

    prompt = offline_obsidian_searcher._build_rag_prompt(
        "Where is the semantic target?",
        [target_atom],
    )

    assert "Parent context is important" in prompt
    assert "Precise semantic target" in prompt


def test_bm25_ranked_uses_filename_lexical_signal(
    offline_obsidian_searcher, tmp_path
):
    note_path = tmp_path / "Collatz and Consciousness.md"
    note_path.write_text(
        "## Recursive Identity\n"
        "This note discusses recursive systems without repeating the filename.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(note_path), store_name="vault")
    offline_obsidian_searcher._rebuild_bm25("vault")
    ranked = offline_obsidian_searcher._collect_bm25_ranked(
        "vault",
        "Collatz and Consciousness",
        5,
    )

    assert ranked
    top_doc = offline_obsidian_searcher._get_doc_by_uri("vault", ranked[0]["id"])
    assert top_doc is not None
    assert top_doc["title"] == "Collatz and Consciousness.md"


def test_semantic_rerank_penalizes_external_reference_folder(
    offline_obsidian_searcher, tmp_path
):
    internal_path = tmp_path / "Ai Identity Experiment.md"
    internal_path.write_text(
        "# Ai Identity Experiment\n"
        "Internal vault note with the main experiment framing.\n",
        encoding="utf-8",
    )
    external_dir = tmp_path / "000 외부 논문 핵심"
    external_dir.mkdir()
    external_path = external_dir / "support.md"
    external_path.write_text(
        "# Support Note\n"
        "AI identity experiment support material from external references.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(internal_path), store_name="vault")
    offline_obsidian_searcher.upload_file(str(external_path), store_name="vault")

    internal_uri = (
        f"local://vault/{quote(str(internal_path.resolve()), safe='')}"
    )
    external_uri = (
        f"local://vault/{quote(str(external_path.resolve()), safe='')}"
    )

    offline_obsidian_searcher._active_query_for_semantic_rerank = (
        "AI identity experiment"
    )
    ranked = offline_obsidian_searcher._collect_sem_ranked(
        "vault",
        [
            ({"uri": external_uri}, 0.91),
            ({"uri": internal_uri}, 0.88),
        ],
    )
    offline_obsidian_searcher._active_query_for_semantic_rerank = ""

    assert ranked[0]["id"] == internal_uri


def test_keyword_search_uses_lexical_backstop_for_title_prefix(
    offline_obsidian_searcher, tmp_path
):
    note_path = tmp_path / "Collatz and Consciousness.md"
    note_path.write_text(
        "## Recursive Identity\n"
        "This body avoids restating the title verbatim.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(note_path), store_name="vault")
    result = offline_obsidian_searcher.search(
        "collatz and consc",
        store_name="vault",
        search_mode="keyword",
    )

    assert result["status"] == "success"
    assert result["sources"]
    assert result["sources"][0]["title"] == "Collatz and Consciousness.md"


def test_exact_file_post_filter_prefers_exact_note_cluster(
    offline_obsidian_searcher, tmp_path
):
    target_path = tmp_path / "Collatz and Consciousness.md"
    distractor_path = tmp_path / "Noise.md"
    target_path.write_text(
        "# Collatz and Consciousness\n"
        "Internal note about recursive cognition.\n",
        encoding="utf-8",
    )
    distractor_path.write_text(
        "# Noise\n"
        "Collatz and consciousness are mentioned once in a broader survey.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(target_path), store_name="vault")
    offline_obsidian_searcher.upload_file(str(distractor_path), store_name="vault")

    docs = offline_obsidian_searcher._local_store_docs["vault"]
    filtered = offline_obsidian_searcher._apply_exact_file_post_filter(
        docs,
        "Collatz and Consciousness",
    )

    assert filtered
    assert all(doc["title"] == "Collatz and Consciousness.md" for doc in filtered)


def test_semantic_search_prefers_exact_note_resolution(
    offline_obsidian_searcher, tmp_path
):
    target_path = tmp_path / "Collatz and Consciousness.md"
    distractor_path = tmp_path / "survey.md"
    target_path.write_text(
        "# Collatz and Consciousness\n"
        "Recursive identity note with the main target content.\n",
        encoding="utf-8",
    )
    distractor_path.write_text(
        "# Survey\n"
        "This broad survey mentions collatz and consciousness in passing.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(target_path), store_name="vault")
    offline_obsidian_searcher.upload_file(str(distractor_path), store_name="vault")

    result = offline_obsidian_searcher.search(
        "Collatz and Consciousness",
        store_name="vault",
        search_mode="semantic",
    )

    assert result["status"] == "success"
    assert result.get("exact_note_match") is True
    assert result["search_confidence"] >= 0.84
    assert result["sources"][0]["title"] == "Collatz and Consciousness.md"


def test_hybrid_search_promotes_exact_note_resolution(
    offline_obsidian_searcher, tmp_path
):
    target_path = tmp_path / "Collatz and Consciousness.md"
    secondary_path = tmp_path / "Recursive Cognition Companion.md"
    target_path.write_text(
        "# Collatz and Consciousness\n"
        "Primary exact note for this lookup.\n",
        encoding="utf-8",
    )
    secondary_path.write_text(
        "# Companion\n"
        "Related recursive cognition material.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(target_path), store_name="vault")
    offline_obsidian_searcher.upload_file(str(secondary_path), store_name="vault")

    result = offline_obsidian_searcher.search(
        "Collatz and Consciousness",
        store_name="vault",
        search_mode="hybrid",
    )

    assert result["status"] == "success"
    assert result.get("exact_note_match") is True
    assert result["search_confidence"] >= 0.84
    assert result["sources"][0]["title"] == "Collatz and Consciousness.md"
    assert result.get("low_confidence", False) is False


def test_exact_note_resolution_arbitrates_between_multiple_title_candidates(
    offline_obsidian_searcher, tmp_path
):
    exact_path = tmp_path / "Collatz and Consciousness.md"
    extended_path = tmp_path / "Collatz and Consciousness A Flame-Based Exploration.md"
    exact_path.write_text(
        "# Collatz and Consciousness\n"
        "Short canonical note.\n",
        encoding="utf-8",
    )
    extended_path.write_text(
        "# Collatz and Consciousness: A Flame-Based Exploration\n"
        "Longer derivative note.\n",
        encoding="utf-8",
    )

    offline_obsidian_searcher.upload_file(str(exact_path), store_name="vault")
    offline_obsidian_searcher.upload_file(str(extended_path), store_name="vault")

    docs = offline_obsidian_searcher._local_store_docs["vault"]
    resolved = offline_obsidian_searcher._exact_note_resolution(
        docs,
        "Collatz and Consciousness",
        max_per_cluster=2,
    )

    assert resolved is not None
    selected_docs, confidence = resolved
    assert confidence >= 0.84
    assert selected_docs[0]["title"] == "Collatz and Consciousness.md"
