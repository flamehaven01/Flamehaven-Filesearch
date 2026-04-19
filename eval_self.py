"""
Flamehaven FileSearch Self-Evaluation
Uploads own docs/source, runs a structured QA battery across all search modes,
and reports measurable retrieval metrics.
"""
import sys
import time
import textwrap
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from flamehaven_filesearch import FlamehavenFileSearch, Config

# ---------------------------------------------------------------------------
# Corpus: split into audit (docs-only) and source for full-pack evaluation.
# Use AUDIT_CORPUS alone for lightweight doc-quality checks.
# CORPUS_FILES (default) = full pack: docs + key source files.
# ---------------------------------------------------------------------------
AUDIT_CORPUS = [
    "README.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "docs/wiki/Architecture.md",
    "docs/wiki/Hybrid_Search.md",
    "docs/wiki/Configuration.md",
    "docs/wiki/Document_Parsing.md",
    "docs/wiki/Benchmarks.md",
    "docs/wiki/API_Reference.md",
    "docs/wiki/Production_Deployment.md",
    "docs/wiki/Troubleshooting.md",
]

SOURCE_CORPUS = [
    "flamehaven_filesearch/core.py",
    "flamehaven_filesearch/_ingest.py",
    "flamehaven_filesearch/_search_local.py",
    "flamehaven_filesearch/_search_cloud.py",
    "flamehaven_filesearch/engine/hybrid_search.py",
    "flamehaven_filesearch/engine/knowledge_atom.py",
    "flamehaven_filesearch/config.py",
]

CORPUS_FILES = AUDIT_CORPUS + SOURCE_CORPUS  # full pack (default)

# ---------------------------------------------------------------------------
# QA battery: (question, expected_keywords, relevant_source_keywords)
# Each entry is tested across keyword / semantic / hybrid modes.
# ---------------------------------------------------------------------------
QA_BATTERY = [
    # --- Architecture ---
    (
        "What is the mixin architecture used in core.py?",
        ["ingest", "mixin", "search"],
        ["core.py", "_ingest", "_search"],
    ),
    (
        "How does BM25 tokenize Korean text?",
        ["ac00", "d7a3", "hangul", "korean", "tokenize", "findall"],
        ["hybrid_search.py", "Hybrid_Search.md"],
    ),
    (
        "What is Reciprocal Rank Fusion and what is the k parameter?",
        ["rrf", "rank", "fusion", "60"],
        ["hybrid_search.py", "Hybrid_Search.md"],
    ),
    (
        "What is a KnowledgeAtom and how are chunk URIs formatted?",
        ["atom", "chunk", "uri", "#c"],
        ["knowledge_atom.py", "Hybrid_Search.md"],
    ),
    (
        "What is the stable URI scheme for local documents?",
        ["local://", "quote", "abs_path"],
        ["_ingest.py", "Hybrid_Search.md", "Architecture.md"],
    ),
    # --- Features ---
    (
        "What file formats does Flamehaven support?",
        ["pdf", "docx", "xlsx", "pptx"],
        ["README.md", "Document_Parsing.md"],
    ),
    (
        "How many tests does the test suite have?",
        ["443"],
        ["README.md", "Benchmarks.md", "CHANGELOG.md"],
    ),
    (
        "What search modes are available?",
        ["keyword", "semantic", "hybrid"],
        ["README.md", "Architecture.md"],
    ),
    (
        "How is vector embedding generated without ML frameworks?",
        ["dsp", "deterministic", "hash", "384"],
        ["Architecture.md", "Benchmarks.md"],
    ),
    (
        "What is the current version of Flamehaven FileSearch?",
        ["1.6.0"],
        ["README.md", "CHANGELOG.md"],
    ),
    # --- Config / API ---
    (
        "How do I configure Ollama as the LLM provider?",
        ["ollama", "llm_provider", "local_model"],
        ["Configuration.md", "CHANGELOG.md"],
    ),
    (
        "What is the default maximum file size?",
        ["50", "mb"],
        ["Configuration.md", "README.md"],
    ),
    # --- Ops ---
    (
        "How do I run the Docker container?",
        ["docker", "run", "8000"],
        ["README.md", "Production_Deployment.md"],
    ),
    (
        "What causes 401 Unauthorized errors?",
        ["admin", "key", "bearer", "authorization"],
        ["Troubleshooting.md"],
    ),
]

MODES = ["keyword", "semantic", "hybrid"]


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def answer_hits(answer: str, expected_keywords: list) -> int:
    a = answer.lower()
    return sum(1 for kw in expected_keywords if kw.lower() in a)


def source_hits(sources: list, relevant_keywords: list) -> int:
    uris = " ".join(s.get("uri", "") + s.get("title", "") for s in sources).lower()
    return sum(1 for kw in relevant_keywords if kw.lower() in uris)


def pct(num: int, den: int) -> str:
    return f"{100*num/den:.0f}%" if den else "N/A"


# ---------------------------------------------------------------------------
# Evaluation sub-routines (extracted from main to reduce complexity)
# ---------------------------------------------------------------------------

def _upload_corpus(fs: FlamehavenFileSearch) -> tuple:
    """Upload all corpus files. Returns (ok_count, fail_count, elapsed_ms)."""
    ok, fail = 0, 0
    t0 = time.time()
    for fname in CORPUS_FILES:
        fp = BASE / fname
        if not fp.exists():
            print(f"  [!] MISSING: {fname}")
            fail += 1
            continue
        r = fs.upload_file(str(fp), store_name="eval")
        if r["status"] == "success":
            ok += 1
        else:
            print(f"  [-] FAIL {fname}: {r.get('message')}")
            fail += 1
    return ok, fail, (time.time() - t0) * 1000


def _run_qa_row(
    fs: FlamehavenFileSearch,
    question: str,
    exp_kw: list,
    rel_src: list,
    accum: dict,
) -> str:
    """Run one QA question across all modes; update accum; return formatted row."""
    row_parts = [f"{question[:43]:<45}"]
    for mode in MODES:
        t0 = time.time()
        r = fs.search(question, store_name="eval", search_mode=mode)
        lat = (time.time() - t0) * 1000
        answer = r.get("answer", "")
        sources = r.get("sources", [])
        ah = answer_hits(answer, exp_kw)
        sh = source_hits(sources, rel_src)
        accum[mode]["ans_hit"] += ah
        accum[mode]["ans_total"] += len(exp_kw)
        accum[mode]["src_hit"] += sh
        accum[mode]["src_total"] += len(rel_src)
        accum[mode]["latency_ms"].append(lat)
        if ah > 0:
            accum[mode]["answered"] += 1
        row_parts.append(f"A:{ah}/{len(exp_kw)} S:{sh}/{len(rel_src)}".rjust(14))
    return "".join(row_parts)


def _print_summary(accum: dict) -> None:
    """Print per-mode summary table."""
    print("\n" + "=" * 60)
    print(f"{'Metric':<30}" + "".join(f"{m:>14}" for m in MODES))
    print("-" * 60)
    rows = [
        ("Answer keyword recall", "ans_hit", "ans_total"),
        ("Source hit rate",       "src_hit", "src_total"),
        ("Questions answered",    "answered", None),
        ("Avg latency (ms)",      "latency_ms", None),
    ]
    for label, key_num, key_den in rows:
        cells = [f"{label:<30}"]
        for m in MODES:
            d = accum[m]
            if key_den:
                val = pct(d[key_num], d[key_den])
            elif key_num == "answered":
                val = f"{d['answered']}/{len(QA_BATTERY)}"
            else:
                lats = d["latency_ms"]
                val = f"{sum(lats)/len(lats):.0f}ms" if lats else "N/A"
            cells.append(f"{val:>14}")
        print("".join(cells))


def _make_accum() -> dict:
    """Return a fresh per-mode accumulator for QA metrics."""
    return {
        m: {"ans_hit": 0, "ans_total": 0, "src_hit": 0, "src_total": 0,
            "answered": 0, "latency_ms": []}
        for m in MODES
    }


def _make_header() -> str:
    """Return the formatted column header string for the QA table."""
    return f"{'Query':<45}" + "".join(f"{'[' + m + ']':>14}" for m in MODES)


def _print_snippets(fs: FlamehavenFileSearch) -> None:
    """Print hybrid-mode snippet quality for first 3 questions."""
    print("\n[=] Notable snippet quality (hybrid, first 3 questions):")
    for question, _, _ in QA_BATTERY[:3]:
        r = fs.search(question, store_name="eval", search_mode="hybrid")
        ans = r.get("answer", "").strip()[:200]
        srcs = [s.get("title", "?") for s in r.get("sources", [])[:2]]
        print(f"\n  Q: {question}")
        print(textwrap.fill(ans, 70, initial_indent="  A: ", subsequent_indent="     "))
        print(f"  Sources: {srcs}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("[>] Flamehaven FileSearch Self-Evaluation v1.6.0")
    print("=" * 60)

    fs = FlamehavenFileSearch(config=Config(api_key=None), allow_offline=True)

    print(f"\n[+] Uploading {len(CORPUS_FILES)} files...")
    ok, fail, upload_ms = _upload_corpus(fs)
    print(f"  uploaded: {ok}/{len(CORPUS_FILES)} in {upload_ms:.0f}ms")
    print(f"  docs: {len(fs._local_store_docs.get('eval', []))} | "
          f"chunk atoms: {len(fs._atom_store_docs.get('eval', {}))}")

    print(f"\n[=] {len(QA_BATTERY)} queries x {len(MODES)} modes = "
          f"{len(QA_BATTERY) * len(MODES)} searches\n")

    accum = _make_accum()
    header = _make_header()
    print(header)
    print("-" * len(header))
    for question, exp_kw, rel_src in QA_BATTERY:
        print(_run_qa_row(fs, question, exp_kw, rel_src, accum))

    _print_summary(accum)
    _print_snippets(fs)
    print("\n[+] Evaluation complete.")


if __name__ == "__main__":
    main()
