#!/usr/bin/env python3
"""
Report Health Checker - Documentation Quality Threshold Validation
===================================================================
Validates documentation metrics against configurable thresholds.

Features:
- README score threshold checking
- Broken link counting
- Warning threshold validation
- Slop term severity-based gating
- GitHub Actions annotation output

Usage:
    python tools/report_health_checker.py \
        --report .audit/doc_drift_report.json \
        --readme-threshold 0.6 \
        --max-broken-links 3 \
        --max-warnings 20 \
        --max-slop-errors 0 \
        --slop-severity error
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


def print_github_notice(title: str, message: str) -> None:
    """Print GitHub Actions notice annotation"""
    print(f"::notice title={title}::{message}")


def print_github_error(message: str, file: str = None, line: int = None) -> None:
    """Print GitHub Actions error annotation"""
    location = ""
    if file:
        location = f"file={file}"
        if line:
            location += f",line={line}"
        location += "::"
    print(f"::error {location}{message}")


def print_github_warning(message: str) -> None:
    """Print GitHub Actions warning annotation"""
    print(f"::warning::{message}")


def check_health(
    report: Dict,
    readme_threshold: float,
    max_errors: int,
    max_warnings: int,
    max_slop_errors: int,
    slop_severity: str
) -> bool:
    """
    Check documentation health against thresholds

    Args:
        report: Parsed drift report dictionary
        readme_threshold: Minimum README score (0.0-1.0)
        max_errors: Maximum broken links allowed
        max_warnings: Maximum warnings allowed
        max_slop_errors: Maximum critical slop terms allowed
        slop_severity: Slop enforcement level (error, warning, info)

    Returns:
        True if all checks pass, False otherwise
    """
    metrics = report.get('metrics', {})

    readme_score = metrics.get('readme_score', 0)
    coherence_score = metrics.get('coherence_score', 0)
    errors = metrics.get('errors', [])
    warnings = metrics.get('warnings', [])
    slop_findings = metrics.get('slop_findings', [])
    slop_errors = metrics.get('slop_errors', 0)
    slop_warnings = metrics.get('slop_warnings', 0)
    slop_infos = metrics.get('slop_infos', 0)

    # Print metrics
    print_github_notice("Documentation Metrics", f"README Score: {readme_score:.1%}")
    print_github_notice("Documentation Metrics", f"Coherence Score: {coherence_score:.1%}")
    print_github_notice("Documentation Metrics", f"Broken Links: {len(errors)}")
    print_github_notice("Documentation Metrics", f"Warnings: {len(warnings)}")
    print_github_notice(
        "Sanity Metrics",
        f"Slop Terms: {len(slop_findings)} (Errors: {slop_errors}, Warnings: {slop_warnings}, Info: {slop_infos})"
    )

    failed = False

    # Check README score
    if readme_score < readme_threshold:
        print_github_error(
            f"README score {readme_score:.1%} below {readme_threshold:.0%} threshold"
        )
        failed = True

    # Check broken links
    error_count = len(errors)
    if error_count > max_errors:
        print_github_error(f"Too many broken links ({error_count} > {max_errors})")
        failed = True

    # Check warnings (non-blocking by default)
    warning_count = len(warnings)
    if warning_count > max_warnings:
        print_github_warning(
            f"Documentation has {warning_count} warnings (threshold: {max_warnings})"
        )

    # Check slop based on severity setting
    if slop_severity == 'error' and slop_errors > max_slop_errors:
        print_github_error(
            f"Found {slop_errors} critical hype terms (threshold: {max_slop_errors})"
        )
        # Print first 5 critical slop findings
        critical_slop = [f for f in slop_findings if f['severity'] == 'error']
        for s in critical_slop[:5]:
            print_github_error(
                f"'{s['term']}' -> Use '{s['suggestion']}'",
                file=s['file'],
                line=s.get('line')
            )
        if len(critical_slop) > 5:
            print_github_error(f"...and {len(critical_slop) - 5} more critical terms")
        failed = True
    elif slop_severity == 'warning' and slop_warnings > 0:
        print_github_warning(f"Found {slop_warnings} hype terms that should be reviewed")

    return not failed


def write_outputs(
    output_file: Path,
    metrics: Dict
) -> None:
    """
    Write outputs for GitHub Actions

    Args:
        output_file: GITHUB_OUTPUT file path
        metrics: Metrics dictionary from report
    """
    readme_score = metrics.get('readme_score', 0)
    coherence_score = metrics.get('coherence_score', 0)
    error_count = len(metrics.get('errors', []))
    warning_count = len(metrics.get('warnings', []))
    slop_count = len(metrics.get('slop_findings', []))
    slop_errors = metrics.get('slop_errors', 0)

    with output_file.open('a', encoding='utf-8') as f:
        f.write(f"readme_score={readme_score:.2%}\n")
        f.write(f"coherence_score={coherence_score:.2%}\n")
        f.write(f"error_count={error_count}\n")
        f.write(f"warning_count={warning_count}\n")
        f.write(f"slop_count={slop_count}\n")
        f.write(f"slop_errors={slop_errors}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Validate documentation health against thresholds"
    )
    parser.add_argument(
        '--report',
        type=Path,
        required=True,
        help='Path to drift report JSON file'
    )
    parser.add_argument(
        '--readme-threshold',
        type=float,
        default=0.6,
        help='Minimum README score (0.0-1.0, default: 0.6)'
    )
    parser.add_argument(
        '--max-broken-links',
        type=int,
        default=3,
        help='Maximum broken links allowed (default: 3)'
    )
    parser.add_argument(
        '--max-warnings',
        type=int,
        default=20,
        help='Maximum warnings allowed (default: 20)'
    )
    parser.add_argument(
        '--max-slop-errors',
        type=int,
        default=0,
        help='Maximum critical slop terms allowed (default: 0)'
    )
    parser.add_argument(
        '--slop-severity',
        choices=['error', 'warning', 'info'],
        default='error',
        help='Slop enforcement level (default: error)'
    )
    parser.add_argument(
        '--github-output',
        type=Path,
        help='Path to GITHUB_OUTPUT file (auto-detected from env if not specified)'
    )

    args = parser.parse_args()

    # Validate report exists
    if not args.report.exists():
        print_github_error(f"Report file not found: {args.report}")
        return 1

    # Read report
    try:
        report = json.loads(args.report.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print_github_error(f"Failed to parse report JSON: {e}")
        return 1
    except Exception as e:
        print_github_error(f"Failed to read report: {e}")
        return 1

    # Check health
    passed = check_health(
        report,
        args.readme_threshold,
        args.max_broken_links,
        args.max_warnings,
        args.max_slop_errors,
        args.slop_severity
    )

    # Write outputs if GITHUB_OUTPUT is available
    github_output = args.github_output
    if not github_output:
        import os
        github_output_env = os.environ.get('GITHUB_OUTPUT')
        if github_output_env:
            github_output = Path(github_output_env)

    if github_output:
        try:
            write_outputs(github_output, report.get('metrics', {}))
        except Exception as e:
            print_github_warning(f"Failed to write outputs: {e}")

    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
