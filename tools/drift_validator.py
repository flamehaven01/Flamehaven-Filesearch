#!/usr/bin/env python3
"""
Document Drift Validator for FLAMEHAVEN FileSearch

Validates documentation-code synchronization and fails CI if drift exceeds thresholds.
Computes:
- README completeness score
- Documentation coherence score
- Broken link detection
- Markdown quality metrics
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class DriftValidator:
    """Validates documentation drift metrics"""

    # Required README sections for minimum quality
    # Project-specific sections for Flamehaven FileSearch
    REQUIRED_README_SECTIONS = [
        r"(Installation|Quick Start)",  # Accept Quick Start as alternative to Installation
        "Configuration",
        r"(Features|Key Features)",  # Features section required
        r"(Roadmap|Troubleshooting)",  # Roadmap or Troubleshooting for future planning
        "License",
    ]

    # Thresholds for CI/CD gate
    MIN_README_SCORE = 0.6  # 60% completeness
    MIN_COHERENCE_SCORE = 0.7  # 70% consistency
    MAX_BROKEN_LINKS = 3
    MAX_WARNINGS = 20

    def __init__(self, project_root: str = "."):
        """Initialize validator with project root"""
        self.project_root = Path(project_root)
        self.metrics = {
            "readme_score": 0.0,
            "coherence_score": 0.0,
            "errors": [],
            "warnings": [],
        }

    def validate(self) -> Tuple[bool, Dict]:
        """
        Run full drift validation

        Returns:
            (passed: bool, metrics: dict)
        """
        logger.info("Starting document drift validation...")

        # Check README completeness
        self._validate_readme()

        # Check markdown quality
        self._validate_markdown()

        # Compute scores
        passed = self._compute_results()

        return passed, self.metrics

    def _validate_readme(self):
        """Validate README.md completeness"""
        readme_path = self.project_root / "README.md"

        if not readme_path.exists():
            self.metrics["errors"].append("README.md not found")
            self.metrics["readme_score"] = 0.0
            return

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for required sections
        found_sections = 0
        for section_pattern in self.REQUIRED_README_SECTIONS:
            # Case-insensitive section search (handle regex patterns)
            # Use double braces {{ }} to escape the regex quantifier in f-string
            pattern = f"^#{{1,2}}\\s+{section_pattern}"
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                found_sections += 1
            else:
                # Extract a readable section name from the pattern
                readable_section = section_pattern.split("|")[0].strip("()")
                self.metrics["warnings"].append(
                    f"README.md: missing section matching '{readable_section}'"
                )

        # Calculate README score
        self.metrics["readme_score"] = found_sections / len(
            self.REQUIRED_README_SECTIONS
        )

        # Check for broken links
        self._check_links(content, readme_path)

    def _check_links(self, content: str, readme_path: Path):
        """Check for broken markdown links"""
        # Pattern for markdown links: [text](path)
        link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
        matches = re.finditer(link_pattern, content)

        for match in matches:
            link_text, link_path = match.groups()

            # Skip external links (http/https)
            if link_path.startswith(("http://", "https://", "#")):
                continue

            # Check if file exists
            resolved_path = readme_path.parent / link_path
            if not resolved_path.exists() and not link_path.startswith("#"):
                error_msg = f"README.md: broken link -> {link_path}"
                if error_msg not in self.metrics["errors"]:
                    self.metrics["errors"].append(error_msg)

    def _validate_markdown(self):
        """Validate markdown quality across documentation files"""
        md_files = list(self.project_root.glob("**/*.md"))

        for md_file in md_files:
            # Skip hidden directories and build artifacts
            if any(
                part.startswith(".")
                for part in md_file.parts
                if part != self.project_root.name
            ):
                continue

            self._check_markdown_quality(md_file)

    def _check_markdown_quality(self, md_file: Path):
        """Check individual markdown file for quality issues"""
        try:
            with open(md_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read {md_file}: {e}")
            return

        # Check for heading level jumps (e.g., # to ####)
        headings = re.findall(r"^(#{1,6})\s", content, re.MULTILINE)
        if headings:
            levels = [len(h) for h in headings]
            for i in range(1, len(levels)):
                jump = levels[i] - levels[i - 1]
                if jump > 1:  # Jump of more than 1 level
                    # Find the heading text for context
                    heading_pattern = rf"^#{{{levels[i]}}}\s+(.+)$"
                    heading_match = re.search(heading_pattern, content, re.MULTILINE)
                    heading_text = (
                        heading_match.group(1) if heading_match else "Unknown"
                    )
                    warning = (
                        f"{md_file.relative_to(self.project_root)}: "
                        f"heading level jumps from {levels[i-1]} to {levels[i]} "
                        f"({heading_text})"
                    )
                    if warning not in self.metrics["warnings"]:
                        self.metrics["warnings"].append(warning)

        # Check for files without headings (non-markdown content)
        if not headings and not content.startswith("<!DOCTYPE"):
            if len(content.strip()) > 0:
                warning = f"{md_file.relative_to(self.project_root)}: missing headings"
                if warning not in self.metrics["warnings"]:
                    self.metrics["warnings"].append(warning)

    def _compute_results(self) -> bool:
        """
        Compute final validation result

        Returns:
            bool: True if all thresholds passed
        """
        # Ensure readme_score is set
        if "readme_score" not in self.metrics:
            self.metrics["readme_score"] = 0.0

        # Compute coherence score (inverse of warning/error ratio)
        total_issues = len(self.metrics["errors"]) + len(self.metrics["warnings"])
        self.metrics["coherence_score"] = max(0, 1.0 - (total_issues / 50))

        # Log results
        logger.info(f"README Score: {self.metrics['readme_score']:.1%}")
        logger.info(f"Coherence Score: {self.metrics['coherence_score']:.1%}")
        logger.info(f"Errors: {len(self.metrics['errors'])}")
        logger.info(f"Warnings: {len(self.metrics['warnings'])}")

        # Check thresholds
        passed = True

        if self.metrics["readme_score"] < self.MIN_README_SCORE:
            logger.error(
                f"README score {self.metrics['readme_score']:.1%} "
                f"below minimum {self.MIN_README_SCORE:.1%}"
            )
            passed = False

        if len(self.metrics["errors"]) > self.MAX_BROKEN_LINKS:
            logger.error(
                f"Too many broken links: {len(self.metrics['errors'])} "
                f"(max: {self.MAX_BROKEN_LINKS})"
            )
            passed = False

        if len(self.metrics["warnings"]) > self.MAX_WARNINGS:
            logger.error(
                f"Too many warnings: {len(self.metrics['warnings'])} "
                f"(max: {self.MAX_WARNINGS})"
            )
            passed = False

        if passed:
            logger.info("Document drift validation PASSED")
        else:
            logger.error("Document drift validation FAILED")

        return passed

    def save_report(self, output_path: str = ".audit/doc_drift_report.json"):
        """Save validation report to JSON"""
        output_file = self.project_root / output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "metrics": self.metrics,
            "thresholds": {
                "min_readme_score": self.MIN_README_SCORE,
                "min_coherence_score": self.MIN_COHERENCE_SCORE,
                "max_broken_links": self.MAX_BROKEN_LINKS,
                "max_warnings": self.MAX_WARNINGS,
            },
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved to {output_file}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate documentation drift metrics")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--report",
        default=".audit/doc_drift_report.json",
        help="Output report path",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Fail if any warnings present",
    )

    args = parser.parse_args()

    validator = DriftValidator(project_root=args.project_root)
    passed, metrics = validator.validate()

    # Save report
    validator.save_report(args.report)

    # Print summary
    print("\n" + "=" * 60)
    print("DOCUMENT DRIFT VALIDATION REPORT")
    print("=" * 60)
    print(f"README Score:     {metrics['readme_score']:.1%}")
    print(f"Coherence Score:  {metrics['coherence_score']:.1%}")
    print(f"Errors:           {len(metrics['errors'])}")
    print(f"Warnings:         {len(metrics['warnings'])}")
    print("=" * 60)

    if metrics["errors"]:
        print("\nERRORS:")
        for error in metrics["errors"]:
            print(f"  - {error}")

    if metrics["warnings"] and args.fail_on_warnings:
        print("\nWARNINGS:")
        for warning in metrics["warnings"][:10]:  # Show first 10
            print(f"  - {warning}")
        if len(metrics["warnings"]) > 10:
            print(f"  ... and {len(metrics['warnings']) - 10} more")

    # Exit with appropriate code
    if passed:
        if args.fail_on_warnings and metrics["warnings"]:
            sys.exit(1)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
