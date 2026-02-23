#!/usr/bin/env python3
"""
Extractor Skill Sanity Check
=============================

Comprehensive test suite that validates all supported document formats
and extraction modes.

Usage:
    python scripts/sanity_check_extractor.py              # Run all tests
    python scripts/sanity_check_extractor.py --fast-only  # Skip VLM tests
    python scripts/sanity_check_extractor.py --format pdf # Test specific format
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

# Add extractor to path
EXTRACTOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(EXTRACTOR_ROOT / "src"))

# Consistent BHT CV32A65X fixtures based on real PDF content
FIXTURES_DIR = EXTRACTOR_ROOT / "data/input/sanity_fixtures"

# Test fixture configurations (using real BHT CV32A65X content)
TEST_FIXTURES = {
    "html": {
        "file": "bht_cv32a65x.html",
        "expected_blocks_min": 8,  # Headers, paragraphs, table, lists
        "expected_sections_min": 1,
    },
    "markdown": {
        "file": "bht_cv32a65x.md",
        "expected_blocks_min": 8,
        "expected_sections_min": 1,
    },
    "xml": {
        "file": "bht_cv32a65x.xml",
        "expected_blocks_min": 5,
        "expected_sections_min": 1,
    },
    "rst": {
        "file": "bht_cv32a65x.rst",
        "expected_blocks_min": 5,
        "expected_sections_min": 1,
    },
}

# Legacy test file templates (for fallback/quick tests)
TEST_FILES = {
    "html": {
        "extension": ".html",
        "content": """<!DOCTYPE html>
<html>
<head><title>Sanity Test Document</title></head>
<body>
<h1>Introduction</h1>
<p>This is a sanity test HTML document for the extractor skill.</p>
<h2>Requirements</h2>
<ul>
<li>REQ-001: The system shall process HTML documents</li>
<li>REQ-002: The system shall extract sections and tables</li>
</ul>
<table>
<tr><th>ID</th><th>Description</th><th>Status</th></tr>
<tr><td>1</td><td>First requirement</td><td>Pass</td></tr>
<tr><td>2</td><td>Second requirement</td><td>Pass</td></tr>
</table>
<h2>Conclusion</h2>
<p>End of test document.</p>
</body>
</html>""",
        "expected_blocks_min": 5,
    },
    "markdown": {
        "extension": ".md",
        "content": """# Sanity Test Document

## Introduction
This is a sanity test Markdown document for the extractor skill.

## Requirements
- REQ-001: The system shall process Markdown documents
- REQ-002: The system shall extract headers and lists

## Data Table

| ID | Description | Status |
|----|-------------|--------|
| 1  | First item  | Pass   |
| 2  | Second item | Pass   |

## Conclusion
End of test document.
""",
        "expected_blocks_min": 4,
    },
    "xml": {
        "extension": ".xml",
        "content": """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <title>Sanity Test Document</title>
  <metadata>
    <author>Extractor Sanity Test</author>
    <date>2026-01-16</date>
  </metadata>
  <section name="Introduction">
    <paragraph>This is a sanity test XML document for the extractor skill.</paragraph>
  </section>
  <section name="Requirements">
    <requirement id="REQ-001">The system shall process XML documents</requirement>
    <requirement id="REQ-002">The system shall extract elements with attributes</requirement>
  </section>
  <section name="Conclusion">
    <paragraph>End of test document.</paragraph>
  </section>
</document>""",
        "expected_blocks_min": 3,
    },
    "rst": {
        "extension": ".rst",
        "content": """==================
Sanity Test Document
==================

Introduction
============
This is a sanity test RST document for the extractor skill.

Requirements
============
* REQ-001: The system shall process RST documents
* REQ-002: The system shall extract headers and lists

Conclusion
==========
End of test document.
""",
        "expected_blocks_min": 3,
    },
}


class SanityChecker:
    """Comprehensive sanity checker for extractor skill."""

    def __init__(self, test_dir: Path = None, verbose: bool = True):
        self.test_dir = test_dir or Path(tempfile.mkdtemp(prefix="extractor_sanity_"))
        self.verbose = verbose
        self.results: List[Dict[str, Any]] = []

        # Ensure test directory exists
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Find a test PDF
        self.test_pdf = self._find_test_pdf()

    def _find_test_pdf(self) -> Path:
        """Find a suitable test PDF."""
        candidates = [
            EXTRACTOR_ROOT / "tools/tasks_loop/fixtures/example_test/source.pdf",
            EXTRACTOR_ROOT / "tools/tasks_loop/fixtures/skill_test/source.pdf",
        ]
        for cand in candidates:
            if cand.exists():
                return cand
        # Search for any PDF
        for pdf in EXTRACTOR_ROOT.rglob("*.pdf"):
            if "node_modules" not in str(pdf) and ".venv" not in str(pdf):
                return pdf
        return None

    def _create_test_file(self, format_name: str) -> Path:
        """Create a test file for the given format."""
        if format_name not in TEST_FILES:
            raise ValueError(f"Unknown format: {format_name}")

        config = TEST_FILES[format_name]
        filepath = self.test_dir / f"sanity_test{config['extension']}"
        filepath.write_text(config["content"])
        return filepath

    def _log(self, msg: str, level: str = "INFO"):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            prefix = {"INFO": "ℹ️ ", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️ "}.get(level, "")
            print(f"{prefix} {msg}")

    def test_structured_format(self, format_name: str, use_fixtures: bool = True) -> Dict[str, Any]:
        """Test a structured format (HTML, Markdown, XML, RST, etc.).

        Args:
            format_name: The format to test (html, markdown, xml, rst)
            use_fixtures: If True, use BHT fixtures; otherwise use generated test files
        """
        self._log(f"Testing {format_name.upper()} format...")

        result = {
            "format": format_name,
            "mode": "structured",
            "fixture": "bht_cv32a65x" if use_fixtures else "generated",
            "success": False,
            "error": None,
            "blocks": 0,
            "duration_ms": 0,
        }

        try:
            # Use fixture or create test file
            if use_fixtures and format_name in TEST_FIXTURES:
                filepath = FIXTURES_DIR / TEST_FIXTURES[format_name]["file"]
                if not filepath.exists():
                    self._log(f"Fixture not found: {filepath}, falling back to generated", "WARN")
                    filepath = self._create_test_file(format_name)
                    result["fixture"] = "generated"
                expected_min = TEST_FIXTURES[format_name].get("expected_blocks_min", 1)
            else:
                filepath = self._create_test_file(format_name)
                result["fixture"] = "generated"
                expected_min = TEST_FILES[format_name].get("expected_blocks_min", 1)

            # Import and run extractor
            from extractor.core.providers.registry import provider_from_filepath

            t0 = time.monotonic()
            provider_cls = provider_from_filepath(str(filepath))
            provider = provider_cls()
            doc = provider.extract_document(str(filepath))
            duration = int((time.monotonic() - t0) * 1000)

            # Validate result
            blocks = len(doc.blocks) if doc.blocks else 0

            result["success"] = blocks >= expected_min
            result["blocks"] = blocks
            result["duration_ms"] = duration
            result["has_hierarchy"] = doc.hierarchy is not None
            result["has_full_text"] = bool(doc.full_text)
            result["filepath"] = str(filepath)

            if result["success"]:
                self._log(
                    f"{format_name.upper()}: {blocks} blocks in {duration}ms ({result['fixture']})",
                    "PASS",
                )
            else:
                result["error"] = f"Expected at least {expected_min} blocks, got {blocks}"
                self._log(f"{format_name.upper()}: {result['error']}", "FAIL")

        except Exception as e:
            result["error"] = str(e)
            self._log(f"{format_name.upper()}: {e}", "FAIL")

        self.results.append(result)
        return result

    def test_pdf_fast(self) -> Dict[str, Any]:
        """Test PDF extraction in fast (offline) mode."""
        self._log("Testing PDF fast mode...")

        result = {
            "format": "pdf",
            "mode": "fast",
            "success": False,
            "error": None,
            "sections": 0,
            "duration_ms": 0,
        }

        if not self.test_pdf:
            result["error"] = "No test PDF found"
            self._log("PDF fast: No test PDF found", "FAIL")
            self.results.append(result)
            return result

        try:
            import subprocess

            out_dir = self.test_dir / "pdf_fast_output"
            out_dir.mkdir(exist_ok=True)

            cmd = [
                sys.executable,
                "-m",
                "extractor.pipeline",
                "--offline-smoke",
                "--pdf",
                str(self.test_pdf),
                "--out",
                str(out_dir),
            ]

            t0 = time.monotonic()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(EXTRACTOR_ROOT),
                timeout=120,
            )
            duration = int((time.monotonic() - t0) * 1000)

            result["duration_ms"] = duration

            if proc.returncode == 0:
                # Check sections output
                sections_file = out_dir / "04_section_builder/json_output/04_sections.json"
                if sections_file.exists():
                    data = json.loads(sections_file.read_text())
                    sections = len(data.get("sections", []))
                    result["sections"] = sections
                    result["success"] = sections > 0
                    result["preset"] = None

                    # Check for preset detection
                    profile_file = out_dir / "00_profile_detector/profile.json"
                    if profile_file.exists():
                        profile = json.loads(profile_file.read_text())
                        result["preset"] = profile.get("preset_name")

                    self._log(
                        f"PDF fast: {sections} sections in {duration}ms (preset={result['preset']})",
                        "PASS",
                    )
                else:
                    result["error"] = "Sections file not found"
                    self._log(f"PDF fast: {result['error']}", "FAIL")
            else:
                result["error"] = proc.stderr[:500] if proc.stderr else "Pipeline failed"
                self._log("PDF fast: Pipeline failed", "FAIL")

        except subprocess.TimeoutExpired:
            result["error"] = "Timeout (120s)"
            self._log("PDF fast: Timeout", "FAIL")
        except Exception as e:
            result["error"] = str(e)
            self._log(f"PDF fast: {e}", "FAIL")

        self.results.append(result)
        return result

    def test_pdf_accurate(self) -> Dict[str, Any]:
        """Test PDF extraction in accurate mode (with VLM)."""
        self._log("Testing PDF accurate mode (VLM enabled)...")

        result = {
            "format": "pdf",
            "mode": "accurate",
            "success": False,
            "error": None,
            "sections": 0,
            "duration_ms": 0,
        }

        if not self.test_pdf:
            result["error"] = "No test PDF found"
            self._log("PDF accurate: No test PDF found", "FAIL")
            self.results.append(result)
            return result

        # Check for API key
        if not os.getenv("CHUTES_API_KEY"):
            result["error"] = "CHUTES_API_KEY not set"
            self._log("PDF accurate: API key missing", "WARN")
            self.results.append(result)
            return result

        try:
            import subprocess

            out_dir = self.test_dir / "pdf_accurate_output"
            out_dir.mkdir(exist_ok=True)

            cmd = [
                sys.executable,
                "-m",
                "extractor.pipeline",
                "--use-llm",
                "--skip-proving",  # Skip Lean4 proving (requires separate container)
                "--pdf",
                str(self.test_pdf),
                "--out",
                str(out_dir),
            ]

            t0 = time.monotonic()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(EXTRACTOR_ROOT),
                timeout=120,  # 2 min is enough for VLM without Lean4 proving
            )
            duration = int((time.monotonic() - t0) * 1000)

            result["duration_ms"] = duration

            if proc.returncode == 0:
                sections_file = out_dir / "04_section_builder/json_output/04_sections.json"
                if sections_file.exists():
                    data = json.loads(sections_file.read_text())
                    sections = len(data.get("sections", []))
                    result["sections"] = sections
                    result["success"] = sections > 0

                    # Check for VLM enrichment (figures/tables with descriptions)
                    figures_file = out_dir / "06b_figure_describer/json_output/06b_figures.json"
                    if figures_file.exists():
                        fig_data = json.loads(figures_file.read_text())
                        result["figures_described"] = sum(
                            1 for f in fig_data.get("figures", []) if f.get("ai_description")
                        )

                    self._log(f"PDF accurate: {sections} sections in {duration}ms", "PASS")
                else:
                    result["error"] = "Sections file not found"
                    self._log(f"PDF accurate: {result['error']}", "FAIL")
            else:
                result["error"] = proc.stderr[:500] if proc.stderr else "Pipeline failed"
                self._log("PDF accurate: Pipeline failed", "FAIL")

        except subprocess.TimeoutExpired:
            result["error"] = "Timeout (120s)"
            self._log("PDF accurate: Timeout", "FAIL")
        except Exception as e:
            result["error"] = str(e)
            self._log(f"PDF accurate: {e}", "FAIL")

        self.results.append(result)
        return result

    def test_pipeline_sanity(self) -> Dict[str, Any]:
        """Test that all pipeline steps have run() and sanity() functions."""
        self._log("Testing pipeline step consistency...")

        result = {
            "format": "pipeline",
            "mode": "sanity",
            "success": False,
            "error": None,
            "steps_ok": 0,
            "steps_total": 0,
        }

        steps = [
            "s00_profile_detector",
            "s01_annotation_processor",
            "s02_marker_extractor",
            "s03_suspicious_headers",
            "s04_section_builder",
            "s04a_layout_audit",
            "s05_table_extractor",
            "s05b_table_describer",
            "s05c_table_merger",
            "s06_figure_extractor",
            "s06b_figure_describer",
            "s07_duckdb_ingest",
            "s07b_text_cleaner",
            "s08_extract_requirements",
            "s08_lean4_theorem_prover",
            "s09_section_summarizer",
            "s10_markdown_exporter",
            "s10_arangodb_exporter",
            "s14_report_generator",
        ]

        ok = 0
        issues = []

        for step in steps:
            try:
                mod = __import__(f"extractor.pipeline.steps.{step}", fromlist=[step])
                has_sanity = hasattr(mod, "sanity") and callable(getattr(mod, "sanity"))
                has_run = hasattr(mod, "run") and callable(getattr(mod, "run"))

                if has_sanity and has_run:
                    ok += 1
                else:
                    missing = []
                    if not has_run:
                        missing.append("run()")
                    if not has_sanity:
                        missing.append("sanity()")
                    issues.append(f"{step}: missing {' and '.join(missing)}")
            except Exception as e:
                issues.append(f"{step}: import error - {e}")

        result["steps_ok"] = ok
        result["steps_total"] = len(steps)
        result["success"] = ok == len(steps)

        if issues:
            result["issues"] = issues
            result["error"] = f"{len(issues)} steps have issues"

        if result["success"]:
            self._log(f"Pipeline sanity: {ok}/{len(steps)} steps OK", "PASS")
        else:
            self._log(f"Pipeline sanity: {ok}/{len(steps)} steps OK", "FAIL")
            for issue in issues:
                self._log(f"  - {issue}", "WARN")

        self.results.append(result)
        return result

    def run_all(
        self, fast_only: bool = False, formats: List[str] = None, use_fixtures: bool = True
    ) -> Dict[str, Any]:
        """Run all sanity checks.

        Args:
            fast_only: If True, skip VLM/accurate PDF tests
            formats: List of formats to test (default: all)
            use_fixtures: If True, use BHT CV32A65X fixtures; otherwise use generated test files
        """
        fixture_mode = "BHT fixtures" if use_fixtures else "generated files"
        self._log(f"Starting extractor sanity check (test_dir={self.test_dir}, {fixture_mode})")
        self._log("")

        t0 = time.monotonic()

        # Pipeline consistency check
        self.test_pipeline_sanity()
        self._log("")

        # Structured formats
        structured_formats = formats or ["html", "markdown", "xml", "rst"]
        for fmt in structured_formats:
            if fmt in TEST_FIXTURES or fmt in TEST_FILES:
                self.test_structured_format(fmt, use_fixtures=use_fixtures)
        self._log("")

        # PDF tests (always use fixtures - BHT PDF)
        if not formats or "pdf" in formats:
            self.test_pdf_fast()

            if not fast_only:
                self._log("")
                self.test_pdf_accurate()

        duration = int((time.monotonic() - t0) * 1000)

        # Summary
        passed = sum(1 for r in self.results if r.get("success"))
        total = len(self.results)

        self._log("")
        self._log("=" * 60)
        self._log(f"SANITY CHECK COMPLETE: {passed}/{total} tests passed in {duration}ms")
        self._log("=" * 60)

        return {
            "passed": passed,
            "total": total,
            "duration_ms": duration,
            "results": self.results,
            "success": passed == total,
        }


def main():
    parser = argparse.ArgumentParser(description="Extractor Skill Sanity Check")
    parser.add_argument("--fast-only", action="store_true", help="Skip VLM/accurate tests")
    parser.add_argument(
        "--format",
        choices=["pdf", "html", "markdown", "xml", "rst", "all"],
        default="all",
        help="Test specific format",
    )
    parser.add_argument("--output", "-o", type=Path, help="Output directory for test artifacts")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument(
        "--no-fixtures",
        action="store_true",
        help="Use generated test files instead of BHT CV32A65X fixtures",
    )

    args = parser.parse_args()

    # Load .env
    from dotenv import load_dotenv, find_dotenv

    load_dotenv(find_dotenv(usecwd=True))

    formats = None if args.format == "all" else [args.format]

    checker = SanityChecker(
        test_dir=args.output,
        verbose=not args.quiet,
    )

    results = checker.run_all(
        fast_only=args.fast_only,
        formats=formats,
        use_fixtures=not args.no_fixtures,
    )

    if args.json:
        print(json.dumps(results, indent=2, default=str))

    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
