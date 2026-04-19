#!/usr/bin/env python3
"""
Report Summary Generator - GitHub Actions Step Summary
=======================================================
Generates formatted markdown summary for GitHub Actions.

Features:
- Metrics overview table
- Broken links listing
- Slop findings grouped by severity
- Collapsible sections for long lists
- PR comment formatting support

Usage:
    python tools/report_summary_generator.py \
        --report .audit/doc_drift_report.json \
        --output-format step-summary \
        --github-step-summary $GITHUB_STEP_SUMMARY
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, TextIO


# ---------------------------------------------------------------------------
# Step-summary helpers
# ---------------------------------------------------------------------------

def _write_slop_severity_block(
    severity: str, slop_findings: List[Dict], output: TextIO
) -> None:
    """Write one severity block inside the step-summary slop section."""
    severity_findings = [s for s in slop_findings if s["severity"] == severity]
    if not severity_findings:
        return
    emoji = {"error": "🔴", "warning": "⚠️", "info": "ℹ️"}[severity]
    output.write(f"#### {emoji} {severity.title()} ({len(severity_findings)})\n\n")
    output.write("| File | Line | Term | Suggestion |\n")
    output.write("|------|------|------|------------|\n")
    for s in severity_findings[:10]:
        output.write(
            f"| `{s['file']}` | {s.get('line', '?')} | `{s['term']}` | `{s['suggestion']}` |\n"
        )
    if len(severity_findings) > 10:
        output.write(f"\n*...and {len(severity_findings) - 10} more*\n\n")


def write_step_summary(report: Dict, output: TextIO) -> None:
    """Write GitHub Actions step summary in markdown format."""
    metrics = report.get("metrics", {})
    slop_findings = metrics.get("slop_findings", [])
    errors = metrics.get("errors", [])

    output.write("## 📊 Documentation Drift & Sanity Report\n\n")
    output.write("### Metrics\n")
    output.write(f"- **README Score**: {metrics.get('readme_score', 0):.1%}\n")
    output.write(f"- **Coherence Score**: {metrics.get('coherence_score', 0):.1%}\n")
    output.write(f"- **Broken Links**: {len(errors)}\n")
    output.write(f"- **Slop Terms**: {len(slop_findings)}\n")
    output.write(f"  - Errors: {metrics.get('slop_errors', 0)}\n")
    output.write(f"  - Warnings: {metrics.get('slop_warnings', 0)}\n")
    output.write(f"  - Info: {metrics.get('slop_infos', 0)}\n\n")

    if errors:
        output.write("### ❌ Broken Links\n")
        for error in errors[:10]:
            output.write(f"- {error}\n")
        if len(errors) > 10:
            output.write(f"\n*...and {len(errors) - 10} more*\n")

    if slop_findings:
        output.write("\n### 🧹 Hype Terms Detected\n\n")
        for severity in ("error", "warning", "info"):
            _write_slop_severity_block(severity, slop_findings, output)


# ---------------------------------------------------------------------------
# PR-comment helpers
# ---------------------------------------------------------------------------

def _write_critical_slop(critical_slop: List[Dict], output: TextIO) -> None:
    output.write(f"### 🔴 Critical Hype Terms ({len(critical_slop)})\n")
    output.write("> **Action Required**: These marketing terms must be replaced.\n\n")
    for s in critical_slop[:5]:
        output.write(
            f"- `{s['file']}:{s.get('line', '?')}`: **{s['term']}** → _{s['suggestion']}_\n"
        )
    if len(critical_slop) <= 5:
        return
    output.write(
        f"\n<details><summary>Show {len(critical_slop) - 5} more critical terms</summary>\n\n"
    )
    for s in critical_slop[5:]:
        output.write(
            f"- `{s['file']}:{s.get('line', '?')}`: **{s['term']}** → _{s['suggestion']}_\n"
        )
    output.write("\n</details>\n\n")


def _write_warning_slop(warning_slop: List[Dict], output: TextIO) -> None:
    output.write(
        f"<details><summary>⚠️ Warning Terms ({len(warning_slop)}) - Review Recommended</summary>\n\n"
    )
    for s in warning_slop[:10]:
        output.write(
            f"- `{s['file']}:{s.get('line', '?')}`: **{s['term']}** → _{s['suggestion']}_\n"
        )
    if len(warning_slop) > 10:
        output.write(f"\n*...and {len(warning_slop) - 10} more*\n")
    output.write("\n</details>\n\n")


def write_pr_comment(report: Dict, output: TextIO) -> None:
    """Write PR comment in markdown format."""
    metrics = report.get("metrics", {})
    readme_score = metrics.get("readme_score", 0) * 100
    errors = metrics.get("errors", [])
    slop_findings = metrics.get("slop_findings", [])
    slop_errors = metrics.get("slop_errors", 0)
    slop_warnings = metrics.get("slop_warnings", 0)

    readme_emoji = "✅" if readme_score >= 60 else "❌"
    errors_emoji = "✅" if len(errors) <= 3 else "❌"
    slop_emoji = "✅" if slop_errors == 0 else "❌"

    output.write("## 📚 Documentation Drift & Sanity Check\n\n")
    output.write("### Metrics\n")
    output.write("| Metric | Value | Status | Threshold |\n")
    output.write("|--------|-------|--------|-----------|  \n")
    output.write(f"| README Score | `{readme_score:.1f}%` | {readme_emoji} | ≥ 60% |\n")
    output.write(f"| Broken Links | `{len(errors)}` | {errors_emoji} | ≤ 3 |\n")
    output.write(f"| Slop Terms (Critical) | `{slop_errors}` | {slop_emoji} | 0 |\n")
    output.write(f"| Slop Terms (Warning) | `{slop_warnings}` | ⚠️ | - |\n\n")

    if not slop_findings:
        output.write(f"\n---\n*Report generated at {datetime.utcnow().isoformat()}Z*\n")
        return

    critical_slop = [s for s in slop_findings if s["severity"] == "error"]
    warning_slop = [s for s in slop_findings if s["severity"] == "warning"]

    if critical_slop:
        _write_critical_slop(critical_slop, output)
    if warning_slop:
        _write_warning_slop(warning_slop, output)

    output.write(f"\n---\n*Report generated at {datetime.utcnow().isoformat()}Z*\n")


# ---------------------------------------------------------------------------
# main helpers
# ---------------------------------------------------------------------------

def _resolve_output_file(args: argparse.Namespace) -> Path | None:
    """Determine the output file path from args and environment."""
    if args.output:
        return args.output
    if args.output_format != "step-summary":
        return None
    if args.github_step_summary:
        return args.github_step_summary
    env_val = os.environ.get("GITHUB_STEP_SUMMARY")
    return Path(env_val) if env_val else None


def _write_output(
    report: Dict, output_format: str, output_file: Path | None
) -> None:
    """Dispatch report writing to file or stdout."""
    writer = write_step_summary if output_format == "step-summary" else write_pr_comment
    if output_file:
        with output_file.open("a", encoding="utf-8") as f:
            writer(report, f)
    else:
        writer(report, sys.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate formatted summary from drift report"
    )
    parser.add_argument(
        "--report", type=Path, required=True, help="Path to drift report JSON file"
    )
    parser.add_argument(
        "--output-format",
        choices=["step-summary", "pr-comment"],
        default="step-summary",
        help="Output format (default: step-summary)",
    )
    parser.add_argument(
        "--github-step-summary",
        type=Path,
        help="Path to GITHUB_STEP_SUMMARY file (auto-detected from env if not specified)",
    )
    parser.add_argument(
        "--output", type=Path, help="Output file path (default: stdout)"
    )
    args = parser.parse_args()

    if not args.report.exists():
        print(f"::error::Report file not found: {args.report}", file=sys.stderr)
        return 1

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"::error::Failed to parse report JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"::error::Failed to read report: {e}", file=sys.stderr)
        return 1

    output_file = _resolve_output_file(args)

    try:
        _write_output(report, args.output_format, output_file)
    except Exception as e:
        print(f"::error::Failed to generate summary: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
