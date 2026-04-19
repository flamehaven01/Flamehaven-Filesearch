#!/usr/bin/env python3
"""
Slop Detector - Context-Aware Hype Term Detection
==================================================
Scans documentation and code for marketing hype terms with contextual filtering.

Features:
- Severity levels (error, warning, info)
- Context-aware filtering (ignore terms in appropriate contexts)
- File type differentiation (stricter for .md, lenient for .py)
- Hyphenated term support
- Exclusion patterns for venv/build directories

Usage:
    python tools/slop_detector.py --input-report .audit/doc_drift_report.json \
                                   --output-report .audit/doc_drift_report.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Context-aware hype term definitions
# Format: term -> (suggestion, contexts_to_ignore, severity)
HYPE_TERMS = {
    # Marketing hype (Critical)
    "blazingly": ("highly", [], "error"),
    "supercharged": ("enhanced", [], "error"),
    "revolutionary": ("improved", [], "warning"),
    "game-changing": ("significant", [], "warning"),
    "paradigm shift": ("architectural change", [], "error"),
    "synergy": ("integration", [], "error"),
    # Overused AI buzzwords (Context-sensitive)
    "agentic": (
        "autonomous",
        ["multi-agent", "agent-based", "agent system"],
        "warning",
    ),
    "sovereign": ("independent", ["data sovereignty", "sovereign identity"], "warning"),
    # Architectural terms (Docs only, contextual)
    "orchestration": (
        "coordination",
        ["kubernetes", "k8s", "docker", "workflow"],
        "info",
    ),
    "hyper-scale": ("scalable", [], "warning"),
    # Vague intensifiers
    "holistic": ("comprehensive", [], "warning"),
    # Controversial technical terms (Context-dependent)
    "byzantine": ("fault-tolerant", ["consensus", "distributed", "bft"], "info"),
    "golden-gate": ("primary-gate", [], "warning"),
    "singularity": ("convergence", ["AI singularity"], "warning"),
}

# Directories to exclude from scanning
EXCLUDE_PATTERNS = [
    ".venv",
    "venv",
    "env",
    "site-packages",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".egg-info",
    ".audit",
    "artifacts",
    ".mypy_cache",
    ".tox",
    "htmlcov",
    "coverage",
]


def should_exclude(file_path: Path) -> bool:
    """Check if file should be excluded from scanning."""
    if file_path.name == "slop_detector.py":
        return True
    return any(pattern in file_path.parts for pattern in EXCLUDE_PATTERNS)


def get_context(content: str, match_pos: int, window: int = 100) -> str:
    """Extract context around match for contextual filtering."""
    start = max(0, match_pos - window)
    end = min(len(content), match_pos + window)
    return content[start:end].lower()


def should_ignore_match(term: str, context: str, ignore_contexts: List[str]) -> bool:
    """Check if match should be ignored based on context."""
    return any(ignore_ctx.lower() in context for ignore_ctx in ignore_contexts)


def is_in_code_block(content: str, match_pos: int) -> bool:
    """Check if match is inside a markdown code block (```)."""
    before_match = content[:match_pos]
    backtick_count = before_match.count("```")
    return backtick_count % 2 == 1


# ---------------------------------------------------------------------------
# scan_for_slop sub-routines
# ---------------------------------------------------------------------------

def _collect_target_files(project_root: Path) -> List[Tuple[Path, bool]]:
    """Return (path, is_docs) pairs for all scannable files, exclusions applied."""
    md_files = [f for f in project_root.glob("**/*.md") if not should_exclude(f)]
    py_files = [f for f in project_root.glob("**/*.py") if not should_exclude(f)]
    return [(f, True) for f in md_files] + [(f, False) for f in py_files]


def _build_term_pattern(term: str) -> "re.Pattern[str]":
    """Build a case-insensitive regex for a hype term."""
    if "-" in term or " " in term:
        return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)


def _match_to_finding(
    match: "re.Match[str]",
    content: str,
    is_docs: bool,
    term: str,
    suggestion: str,
    ignore_contexts: List[str],
    severity: str,
    file_path: Path,
    project_root: Path,
) -> Optional[Dict]:
    """Convert a regex match to a finding dict, or None if filtered out."""
    match_context = get_context(content, match.start())
    if should_ignore_match(term, match_context, ignore_contexts):
        return None
    if is_docs and is_in_code_block(content, match.start()):
        return None

    line_num = content[: match.start()].count("\n") + 1
    lines = content.split("\n")
    line_content = lines[line_num - 1] if line_num <= len(lines) else ""

    return {
        "file": str(file_path.relative_to(project_root)),
        "line": line_num,
        "term": match.group(0),
        "suggestion": suggestion,
        "severity": severity,
        "context": line_content.strip()[:100],
    }


def _scan_file_for_term(
    content: str,
    file_path: Path,
    project_root: Path,
    is_docs: bool,
    term: str,
    suggestion: str,
    ignore_contexts: List[str],
    severity: str,
) -> List[Dict]:
    """Return all findings for one (file, term) pair."""
    if not is_docs and severity == "info":
        return []
    pattern = _build_term_pattern(term)
    findings = []
    for match in pattern.finditer(content):
        finding = _match_to_finding(
            match, content, is_docs, term, suggestion,
            ignore_contexts, severity, file_path, project_root,
        )
        if finding is not None:
            findings.append(finding)
    return findings


def _scan_single_file(file_path: Path, project_root: Path, is_docs: bool) -> List[Dict]:
    """Scan one file across all HYPE_TERMS. Returns findings list."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"::warning::Failed to scan {file_path}: {e}", file=sys.stderr)
        return []

    findings: List[Dict] = []
    for term, (suggestion, ignore_contexts, severity) in HYPE_TERMS.items():
        findings.extend(
            _scan_file_for_term(
                content, file_path, project_root, is_docs,
                term, suggestion, ignore_contexts, severity,
            )
        )
    return findings


def scan_for_slop(project_root: Path) -> List[Dict]:
    """Scan files for hype terms with context awareness.

    Returns a list of findings (file, line, term, suggestion, severity, context).
    """
    findings: List[Dict] = []
    for file_path, is_docs in _collect_target_files(project_root):
        findings.extend(_scan_single_file(file_path, project_root, is_docs))
    return findings


# ---------------------------------------------------------------------------
# Report update
# ---------------------------------------------------------------------------

def update_report_with_slop(report_path: Path, slop_findings: List[Dict]) -> None:
    """Update existing drift report with slop findings using atomic write."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))

        errors   = [s for s in slop_findings if s["severity"] == "error"]
        warnings = [s for s in slop_findings if s["severity"] == "warning"]
        infos    = [s for s in slop_findings if s["severity"] == "info"]

        report["metrics"]["slop_findings"] = slop_findings
        report["metrics"]["slop_errors"]   = len(errors)
        report["metrics"]["slop_warnings"] = len(warnings)
        report["metrics"]["slop_infos"]    = len(infos)

        temp_path = report_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        temp_path.replace(report_path)

        print(f"Slop detection complete:")
        print(f"  Total: {len(slop_findings)}")
        print(f"  Errors: {len(errors)}")
        print(f"  Warnings: {len(warnings)}")
        print(f"  Info: {len(infos)}")

    except json.JSONDecodeError as e:
        print(f"::error::Invalid JSON in report file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"::error::Failed to update report: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect hype/slop terms in documentation with context awareness"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path("."),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--input-report", type=Path, required=True,
        help="Input drift report JSON file (e.g., .audit/doc_drift_report.json)",
    )
    parser.add_argument(
        "--output-report", type=Path, required=True,
        help="Output report JSON file (can be same as input for in-place update)",
    )

    args = parser.parse_args()

    if not args.input_report.exists():
        print(f"::error::Input report not found: {args.input_report}", file=sys.stderr)
        return 1

    print(f"Scanning {args.project_root} for slop terms...")
    slop_findings = scan_for_slop(args.project_root)
    update_report_with_slop(args.output_report, slop_findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
