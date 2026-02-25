#!/usr/bin/env python3
"""
test_fixture.py - End-to-end fixture test runner.

Seamless, reliable, and straightforward workflow:
1. Generate synthetic PDF from twin_config.yml (if needed)
2. Run extraction in accurate mode
3. Compare output against *_expected.json
4. Return pass/fail with detailed report

Usage:
    python test_fixture.py fixtures/sparta_stress_test/
    python test_fixture.py fixtures/sparta_stress_test/ --regenerate
    python test_fixture.py fixtures/sparta_stress_test/ --verbose
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass, field

# Colors for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class TestResult:
    """Result of a single test check."""

    name: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FixtureTestReport:
    """Complete test report for a fixture."""

    fixture_name: str
    passed: bool
    results: List[TestResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    extraction_output_path: Path = None

    def add_result(self, name: str, passed: bool, message: str, **details):
        self.results.append(TestResult(name, passed, message, details))
        if not passed:
            self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def find_twin_config(fixture_dir: Path) -> Path:
    """Find twin_config.yml in fixture directory."""
    for name in ["twin_config.yml", "twin_config.yaml", "config.yml"]:
        p = fixture_dir / name
        if p.exists():
            return p
    return None


def generate_fixture(fixture_dir: Path, config_path: Path) -> Tuple[bool, Path]:
    """Generate synthetic PDF from twin_config.yml."""
    output_pdf = fixture_dir / f"{fixture_dir.name}.pdf"

    # Find generator script
    utils_dir = Path(__file__).parent
    generator = utils_dir / "generate_complex_fixture.py"

    if not generator.exists():
        print(f"{RED}Error: Generator script not found: {generator}{RESET}")
        return False, None

    cmd = [sys.executable, str(generator), str(output_pdf), "--config", str(config_path)]

    print(f"{BLUE}Generating synthetic PDF...{RESET}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"{RED}Generation failed:{RESET}")
        print(result.stderr)
        return False, None

    if not output_pdf.exists():
        print(f"{RED}PDF not created: {output_pdf}{RESET}")
        return False, None

    print(f"{GREEN}Generated: {output_pdf}{RESET}")
    return True, output_pdf


def run_extraction(pdf_path: Path, output_dir: Path) -> Tuple[bool, str]:
    """Run extraction pipeline in accurate mode."""
    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline",
        str(pdf_path),
        "--out",
        str(output_dir),
        "--use-llm",
    ]

    env = {**subprocess.os.environ, "PIPELINE_MODE": "accurate", "TABLE_LLM_ASSIST": "1"}

    print(f"{BLUE}Running extraction (accurate mode)...{RESET}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        return False, result.stderr

    return True, result.stdout


def load_json_safe(path: Path) -> Dict[str, Any]:
    """Load JSON file, return empty dict on error."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def compare_tables(extracted: Dict, expected: Dict, report: FixtureTestReport):
    """Compare extracted tables against expected."""
    # Check for generic headers
    tables = extracted.get("tables", [])
    quality_warnings = extracted.get("quality_warnings", [])

    if quality_warnings:
        for warn in quality_warnings:
            if "generic integer headers" in warn.lower():
                report.add_result(
                    "table_headers",
                    False,
                    f"Generic headers detected: {warn}",
                    quality_warnings=quality_warnings,
                )
                return

    # Check if expected headers are present
    expected_headers = expected.get("tables", {}).get("expected_headers", [])
    if expected_headers and tables:
        found_semantic = False
        for table in tables:
            columns = table.get("pandas_metrics", {}).get("columns", [])
            # Check if any expected header is present
            for hdr in expected_headers:
                if hdr in columns:
                    found_semantic = True
                    break

        if not found_semantic:
            report.add_result(
                "table_headers",
                False,
                f"Expected semantic headers not found. Expected: {expected_headers}",
                found_columns=(
                    tables[0].get("pandas_metrics", {}).get("columns") if tables else None
                ),
            )
            return

    report.add_result("table_headers", True, "Table headers look semantic")


def compare_figures(extracted: Dict, config: Dict, report: FixtureTestReport):
    """Compare extracted figures against expected."""
    figure_count = extracted.get("figure_count", 0)
    # Get expected count from config (figures.expected_count)
    expected_count = config.get("figures", {}).get("expected_count", 0)

    # If config expects figures but none found
    if expected_count > 0 and figure_count == 0:
        report.add_result("figures", False, f"Expected {expected_count} figures, found 0")
        return

    # If no figures expected, just pass
    if expected_count == 0:
        report.add_result("figures", True, "No figures expected")
        return

    report.add_result("figures", True, f"Found {figure_count} figures")


def compare_sections(extracted: Dict, expected: Dict, config: Dict, report: FixtureTestReport):
    """Check for section pollution and trapped headers."""
    sections = extracted.get("sections", [])

    # Check for boilerplate patterns that should have been filtered
    text_noise = config.get("text_noise", [])
    ambiguous_headers = config.get("ambiguous_headers", [])

    pollution_found = []
    trapped_found = []

    for section in sections:
        title = section.get("title", "") or section.get("header_text", "")

        # Check for noise in titles
        for noise in text_noise:
            if noise.lower() in title.lower():
                pollution_found.append(f"'{title}' contains noise '{noise}'")

        # Check for ambiguous headers that shouldn't be section titles
        for amb in ambiguous_headers:
            amb_text = amb.get("text", "")
            if amb_text.lower() in title.lower():
                trapped_found.append(f"'{title}' contains ambiguous header '{amb_text}'")

    if pollution_found:
        report.add_result(
            "section_pollution",
            False,
            "Boilerplate text found in section titles",
            pollution=pollution_found,
        )
    else:
        report.add_result("section_pollution", True, "No boilerplate in section titles")

    if trapped_found:
        report.add_result(
            "trapped_headers",
            False,
            "Ambiguous text treated as section headers",
            trapped=trapped_found,
        )
    else:
        report.add_result("trapped_headers", True, "No trapped headers detected")

    # Check for false header from table data
    false_header = config.get("tables", {}).get("false_header_text", "")
    if false_header:
        for section in sections:
            title = section.get("title", "") or section.get("header_text", "")
            if false_header in title:
                report.add_result(
                    "table_data_as_header",
                    False,
                    f"Table data treated as section header: '{title}'",
                )
                return
        report.add_result("table_data_as_header", True, "Table data not mistaken for headers")


def compare_requirements(extracted: Dict, expected: Dict, report: FixtureTestReport):
    """Compare extracted requirements against expected critical content."""
    expected_items = expected.get("content", [])
    # Only check requirements/findings, not tables
    critical_reqs = [
        i
        for i in expected_items
        if i.get("strict_verification") and i.get("type") in ("Requirement", "Finding")
    ]

    if not critical_reqs:
        report.add_result("requirements", True, "No strict requirements to verify")
        return

    # Get all extracted text
    extracted_text = json.dumps(extracted).lower()

    missing = []
    for req in critical_reqs:
        req_id = req.get("id", "")
        req_text = req.get("text", "")

        # Check if requirement ID or key text appears in extraction
        if req_id.lower() not in extracted_text and req_text[:30].lower() not in extracted_text:
            missing.append(req_id)

    if missing:
        report.add_result(
            "requirements", False, f"Missing critical requirements: {missing}", missing=missing
        )
    else:
        report.add_result(
            "requirements", True, f"All {len(critical_reqs)} critical requirements found"
        )


def run_tests(
    fixture_dir: Path,
    regenerate: bool = False,
    verbose: bool = False,
    skip_extraction: bool = False,
) -> FixtureTestReport:
    """Run all tests on a fixture."""
    report = FixtureTestReport(fixture_name=fixture_dir.name, passed=True)

    # 1. Find config
    config_path = find_twin_config(fixture_dir)
    if not config_path:
        report.add_result("config", False, "No twin_config.yml found")
        return report

    import yaml

    config = yaml.safe_load(config_path.read_text())
    report.add_result("config", True, f"Loaded {config_path.name}")

    # 2. Generate PDF if needed
    pdf_path = fixture_dir / f"{fixture_dir.name}.pdf"
    expected_json = fixture_dir / f"{fixture_dir.name}_expected.json"

    if regenerate or not pdf_path.exists():
        success, pdf_path = generate_fixture(fixture_dir, config_path)
        if not success:
            report.add_result("generation", False, "PDF generation failed")
            return report
        report.add_result("generation", True, f"Generated {pdf_path.name}")
    else:
        report.add_result("generation", True, f"Using existing {pdf_path.name}")

    # 3. Run extraction (or use existing output)
    output_dir = fixture_dir / "extraction_output"

    if skip_extraction and output_dir.exists():
        report.add_result("extraction", True, "Using existing extraction output")
        report.extraction_output_path = output_dir
    else:
        success, output = run_extraction(pdf_path, output_dir)

        if not success:
            # Check if we have existing output we can use
            if output_dir.exists() and (output_dir / "05_table_extractor").exists():
                report.add_result(
                    "extraction", True, "Using existing output (new extraction failed)"
                )
                report.add_warning(f"Fresh extraction failed: {output[:200]}")
                report.extraction_output_path = output_dir
            else:
                report.add_result("extraction", False, f"Extraction failed: {output[:500]}")
                return report
        else:
            report.extraction_output_path = output_dir
            report.add_result("extraction", True, "Extraction completed")

    # 4. Load extraction outputs
    tables_json = output_dir / "05_table_extractor" / "json_output" / "05_tables.json"
    figures_json = output_dir / "06_figure_extractor" / "json_output" / "06_figures.json"
    sections_json = output_dir / "04_section_builder" / "json_output" / "04_sections.json"

    tables_data = load_json_safe(tables_json)
    figures_data = load_json_safe(figures_json)
    sections_data = load_json_safe(sections_json)
    expected_data = load_json_safe(expected_json)

    # 5. Run comparisons
    compare_tables(tables_data, config, report)
    compare_figures(figures_data, config, report)
    compare_sections(sections_data, expected_data, config, report)
    compare_requirements(sections_data, expected_data, report)

    return report


def print_report(report: FixtureTestReport, verbose: bool = False):
    """Print test report to console."""
    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}Fixture Test Report: {report.fixture_name}{RESET}")
    print(f"{'='*60}")

    for result in report.results:
        status = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {result.name}: {result.message}")

        if verbose and result.details:
            for k, v in result.details.items():
                print(f"         {k}: {v}")

    if report.warnings:
        print(f"\n{YELLOW}Warnings:{RESET}")
        for warn in report.warnings:
            print(f"  - {warn}")

    print()
    if report.passed:
        print(f"{GREEN}{BOLD}OVERALL: PASS{RESET}")
    else:
        print(f"{RED}{BOLD}OVERALL: FAIL{RESET}")
        failed = [r.name for r in report.results if not r.passed]
        print(f"Failed checks: {', '.join(failed)}")

    if report.extraction_output_path:
        print(f"\nOutput: {report.extraction_output_path}")

    print()


def main():
    parser = argparse.ArgumentParser(description="End-to-end fixture test runner")
    parser.add_argument("fixture_dir", type=Path, help="Path to fixture directory")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate PDF even if exists")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--skip-extraction", action="store_true", help="Use existing extraction output if available"
    )
    args = parser.parse_args()

    if not args.fixture_dir.is_dir():
        print(f"{RED}Error: Not a directory: {args.fixture_dir}{RESET}")
        sys.exit(2)

    report = run_tests(args.fixture_dir, args.regenerate, args.verbose, args.skip_extraction)

    if args.json:
        output = {
            "fixture": report.fixture_name,
            "passed": report.passed,
            "results": [
                {"name": r.name, "passed": r.passed, "message": r.message, **r.details}
                for r in report.results
            ],
            "warnings": report.warnings,
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(report, args.verbose)

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
