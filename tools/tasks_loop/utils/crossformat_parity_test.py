#!/usr/bin/env python3
"""
crossformat_parity_test.py

Cross-Format Parity Validation
==============================

The core validation principle: Given the SAME semantic content in different file formats,
the extractor pipeline should produce EQUIVALENT output (Markdown + ArangoDB JSON).

This tool:
1. Takes a directory of multi-format fixtures (same content in PDF, HTML, MD, XML, etc.)
2. Runs each format through the extractor pipeline
3. Compares the resulting Markdown and JSON outputs
4. Reports parity metrics and divergences

Usage:
    python crossformat_parity_test.py --fixture-dir data/input/sanity_fixtures/generated
    python crossformat_parity_test.py --fixture-dir fixtures/ --name bht_cv32a65x --reference pdf
"""

import argparse
import json
import difflib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Add extractor to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@dataclass
class ExtractionResult:
    """Result from extracting a single format."""
    format: str
    success: bool
    error: Optional[str] = None
    markdown: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    json_output: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParityScore:
    """Parity comparison between two formats."""
    format_a: str
    format_b: str
    section_count_match: bool
    section_titles_similarity: float  # 0.0 - 1.0
    requirement_ids_match: bool
    table_count_match: bool
    markdown_similarity: float  # 0.0 - 1.0
    overall_score: float  # 0.0 - 1.0
    divergences: List[str] = field(default_factory=list)


def extract_structured_format(filepath: Path, output_dir: Path) -> ExtractionResult:
    """Extract a structured format (HTML, MD, XML, RST, DOCX, etc.) using UnifiedAdapter."""
    fmt = filepath.suffix.lstrip('.').lower()
    result = ExtractionResult(format=fmt, success=False)

    try:
        from extractor.core.providers.registry import provider_from_filepath
        from extractor.pipeline.adapters.unified_adapter import UnifiedAdapter

        # Step 1: Provider extracts to UnifiedDocument
        provider_cls = provider_from_filepath(str(filepath))
        # Some providers (ImageProvider) require filepath in constructor
        try:
            provider = provider_cls()
            unified_doc = provider.extract_document(str(filepath))
        except TypeError:
            # Provider requires filepath in constructor
            provider = provider_cls(str(filepath))
            unified_doc = provider.extract_document()

        # Step 2: UnifiedAdapter converts to pipeline artifacts
        adapter = UnifiedAdapter(unified_doc, output_dir)
        adapter.write_artifacts()

        # Step 3: Read the generated artifacts
        sections_file = output_dir / "04_section_builder/json_output/04_sections.json"
        tables_file = output_dir / "05_table_extractor/json_output/05_tables.json"
        figures_file = output_dir / "06_figure_extractor/json_output/06_figures.json"

        if sections_file.exists():
            sections_data = json.loads(sections_file.read_text())
            result.sections = sections_data.get("sections", [])

        if tables_file.exists():
            tables_data = json.loads(tables_file.read_text())
            result.tables = tables_data.get("tables", [])

        # Build markdown from sections (same as PDF pipeline output)
        result.markdown = _sections_to_markdown(result.sections)

        # Extract requirements from sections
        result.requirements = _extract_requirements_from_sections(result.sections)

        # Store raw blocks count for reference
        result.blocks = [{"id": f"block-{i}"} for i in range(len(unified_doc.blocks))]

        result.json_output = {
            "sections": result.sections,
            "requirements": result.requirements,
            "tables": result.tables,
            "block_count": len(unified_doc.blocks),
        }
        result.success = True

    except Exception as e:
        import traceback
        result.error = f"{str(e)}\n{traceback.format_exc()}"

    return result


def _extract_requirements_from_sections(sections: List[Dict]) -> List[Dict]:
    """Extract requirements from section blocks."""
    import re
    reqs = []

    for section in sections:
        for block in section.get("blocks", []):
            text = block.get("text", "")

            # Check for REQ- in text content (HTML, MD, PDF, etc.)
            if text and "REQ-" in text:
                match = re.search(r'(REQ-[\w-]+)[:\s]+(.+)', text)
                if match and not any(r['id'] == match.group(1) for r in reqs):
                    reqs.append({'id': match.group(1), 'text': match.group(2).strip()})

            # Check for REQ- in metadata attributes (XML with <requirement id="REQ-...">)
            # Structure can be: metadata.attributes.attributes.id (from UnifiedAdapter)
            # or: metadata.attributes.id (direct)
            metadata = block.get("metadata", {})
            if metadata:
                attrs = metadata.get("attributes", {})
                # Check direct attributes
                req_id = attrs.get("id", "")
                # Check nested attributes (XML provider nests original XML attributes)
                if not req_id and isinstance(attrs.get("attributes"), dict):
                    req_id = attrs["attributes"].get("id", "")
                if req_id and req_id.startswith("REQ-"):
                    if not any(r['id'] == req_id for r in reqs):
                        reqs.append({'id': req_id, 'text': text.strip() if text else ""})

        # Also check section title
        title = section.get("title", "")
        if "REQ-" in title:
            match = re.search(r'(REQ-[\w-]+)[:\s]+(.+)', title)
            if match and not any(r['id'] == match.group(1) for r in reqs):
                reqs.append({'id': match.group(1), 'text': match.group(2).strip()})

    return reqs


def extract_pdf_format(filepath: Path, output_dir: Path) -> ExtractionResult:
    """Extract PDF using the full pipeline."""
    result = ExtractionResult(format='pdf', success=False)

    try:
        # Use specific flags instead of --offline-smoke to enable table extraction
        # Skip LLM stages but run Camelot table extraction
        cmd = [
            sys.executable, "-m", "extractor.pipeline",
            "--skip-proving",           # Skip Lean4 prover
            "--skip-annotator09a",       # Skip PDF annotator
            "--skip-fig-descriptions",   # Skip VLM figure descriptions
            "--summary-only",            # Skip section summarization
            "--pdf", str(filepath),
            "--out", str(output_dir),
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=180,
        )

        if proc.returncode == 0:
            # Read sections
            sections_file = output_dir / "04_section_builder/json_output/04_sections.json"
            if sections_file.exists():
                data = json.loads(sections_file.read_text())
                result.sections = data.get("sections", [])

            # Read markdown export if available
            md_file = output_dir / "10_markdown_exporter/json_output/10_markdown.json"
            if md_file.exists():
                md_data = json.loads(md_file.read_text())
                result.markdown = md_data.get("markdown", "")
            else:
                # Build markdown from sections
                result.markdown = _sections_to_markdown(result.sections)

            # Read requirements from Stage 08 if available, otherwise use regex extraction
            req_file = output_dir / "08_extract_requirements/json_output/08_requirements.json"
            if req_file.exists():
                req_data = json.loads(req_file.read_text())
                result.requirements = req_data.get("requirements", [])

            # Fallback: extract requirements from sections using regex (same as other formats)
            if not result.requirements:
                result.requirements = _extract_requirements_from_sections(result.sections)

            # Read tables
            tables_file = output_dir / "05_table_extractor/json_output/05_tables.json"
            if tables_file.exists():
                tables_data = json.loads(tables_file.read_text())
                result.tables = tables_data.get("tables", [])

            result.json_output = {
                "sections": result.sections,
                "requirements": result.requirements,
                "tables": result.tables,
            }
            result.success = True
        else:
            result.error = proc.stderr[:500] if proc.stderr else "Pipeline failed"

    except subprocess.TimeoutExpired:
        result.error = "Timeout (180s)"
    except Exception as e:
        result.error = str(e)

    return result


def _sections_to_markdown(sections: List[Dict]) -> str:
    """Convert sections to markdown."""
    lines = []
    for section in sections:
        level = section.get('level', 1)
        title = section.get('title', section.get('display_title', ''))
        lines.append(f"{'#' * level} {title}")
        lines.append("")

        for block in section.get('blocks', []):
            text = block.get('text', '')
            if text:
                lines.append(text)
                lines.append("")

    return "\n".join(lines)


def calculate_text_similarity(text_a: str, text_b: str) -> float:
    """Calculate similarity between two texts using SequenceMatcher."""
    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0

    # Normalize whitespace
    text_a = ' '.join(text_a.split())
    text_b = ' '.join(text_b.split())

    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


def calculate_list_similarity(list_a: List[str], list_b: List[str]) -> float:
    """Calculate similarity between two lists of strings."""
    if not list_a and not list_b:
        return 1.0
    if not list_a or not list_b:
        return 0.0

    set_a = set(list_a)
    set_b = set(list_b)

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def compare_results(result_a: ExtractionResult, result_b: ExtractionResult) -> ParityScore:
    """Compare two extraction results and compute parity score."""
    divergences = []

    # Section count
    section_count_a = len(result_a.sections)
    section_count_b = len(result_b.sections)
    section_count_match = section_count_a == section_count_b
    if not section_count_match:
        divergences.append(f"Section count: {result_a.format}={section_count_a}, {result_b.format}={section_count_b}")

    # Section titles similarity
    titles_a = [s.get('title', '') for s in result_a.sections]
    titles_b = [s.get('title', '') for s in result_b.sections]
    section_titles_similarity = calculate_list_similarity(titles_a, titles_b)
    if section_titles_similarity < 0.8:
        divergences.append(f"Section titles diverge: {titles_a[:3]} vs {titles_b[:3]}")

    # Requirement IDs
    req_ids_a = {r.get('id', '') for r in result_a.requirements}
    req_ids_b = {r.get('id', '') for r in result_b.requirements}
    requirement_ids_match = req_ids_a == req_ids_b
    if not requirement_ids_match:
        missing_in_b = req_ids_a - req_ids_b
        missing_in_a = req_ids_b - req_ids_a
        if missing_in_b:
            divergences.append(f"Requirements in {result_a.format} but not {result_b.format}: {missing_in_b}")
        if missing_in_a:
            divergences.append(f"Requirements in {result_b.format} but not {result_a.format}: {missing_in_a}")

    # Table count
    table_count_a = len(result_a.tables)
    table_count_b = len(result_b.tables)
    table_count_match = table_count_a == table_count_b
    if not table_count_match:
        divergences.append(f"Table count: {result_a.format}={table_count_a}, {result_b.format}={table_count_b}")

    # Markdown similarity
    markdown_similarity = calculate_text_similarity(result_a.markdown, result_b.markdown)
    if markdown_similarity < 0.7:
        divergences.append(f"Markdown similarity low: {markdown_similarity:.2f}")

    # Overall score (weighted average)
    overall_score = (
        (1.0 if section_count_match else 0.5) * 0.2 +
        section_titles_similarity * 0.2 +
        (1.0 if requirement_ids_match else 0.0) * 0.3 +
        (1.0 if table_count_match else 0.5) * 0.1 +
        markdown_similarity * 0.2
    )

    return ParityScore(
        format_a=result_a.format,
        format_b=result_b.format,
        section_count_match=section_count_match,
        section_titles_similarity=section_titles_similarity,
        requirement_ids_match=requirement_ids_match,
        table_count_match=table_count_match,
        markdown_similarity=markdown_similarity,
        overall_score=overall_score,
        divergences=divergences,
    )


class CrossFormatParityTester:
    """Run cross-format parity tests on a fixture directory."""

    def __init__(self, fixture_dir: Path, name: str = "fixture", verbose: bool = True):
        self.fixture_dir = fixture_dir
        self.name = name
        self.verbose = verbose
        self.results: Dict[str, ExtractionResult] = {}
        self.parity_scores: List[ParityScore] = []

    def _log(self, msg: str, level: str = "INFO"):
        if self.verbose:
            prefix = {"INFO": "  ", "PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}.get(level, "")
            print(f"{prefix} {msg}")

    def extract_all_formats(self):
        """Extract all available format files."""
        format_extensions = {
            'pdf': ['.pdf'],
            'html': ['.html', '.htm'],
            'md': ['.md', '.markdown'],
            'xml': ['.xml'],
            'rst': ['.rst'],
            'docx': ['.docx'],
            'pptx': ['.pptx'],
            'xlsx': ['.xlsx'],
            'epub': ['.epub'],
            'png': ['.png', '.jpg', '.jpeg'],
        }

        print(f"\n{'='*60}")
        print(f"CROSS-FORMAT PARITY TEST: {self.name}")
        print(f"{'='*60}")
        print(f"Fixture directory: {self.fixture_dir}")
        print()

        for fmt, extensions in format_extensions.items():
            for ext in extensions:
                filepath = self.fixture_dir / f"{self.name}{ext}"
                if filepath.exists():
                    self._log(f"Extracting {fmt.upper()} ({filepath.name})...")

                    with tempfile.TemporaryDirectory(prefix=f"parity_{fmt}_") as tmp:
                        output_dir = Path(tmp)

                        if fmt == 'pdf':
                            result = extract_pdf_format(filepath, output_dir)
                        elif fmt == 'png':
                            # Image extraction uses ImageProvider
                            result = extract_structured_format(filepath, output_dir)
                        else:
                            result = extract_structured_format(filepath, output_dir)

                        self.results[fmt] = result

                        if result.success:
                            self._log(
                                f"  -> {len(result.sections)} sections, "
                                f"{len(result.requirements)} reqs, "
                                f"{len(result.tables)} tables",
                                "PASS"
                            )
                        else:
                            self._log(f"  -> Failed: {result.error}", "FAIL")

                    break  # Only process first matching extension

    def compare_all_pairs(self, reference: str = None):
        """Compare all format pairs or against a reference."""
        print(f"\n{'='*60}")
        print("PARITY COMPARISONS")
        print(f"{'='*60}")

        successful_formats = [f for f, r in self.results.items() if r.success]

        if len(successful_formats) < 2:
            print("Need at least 2 successful extractions to compare")
            return

        if reference and reference in successful_formats:
            # Compare all against reference
            ref_result = self.results[reference]
            print(f"\nComparing all formats against reference: {reference.upper()}")
            print("-" * 40)

            for fmt in successful_formats:
                if fmt != reference:
                    score = compare_results(ref_result, self.results[fmt])
                    self.parity_scores.append(score)
                    self._report_score(score)
        else:
            # Compare all pairs
            print("\nPairwise comparisons:")
            print("-" * 40)

            for i, fmt_a in enumerate(successful_formats):
                for fmt_b in successful_formats[i+1:]:
                    score = compare_results(self.results[fmt_a], self.results[fmt_b])
                    self.parity_scores.append(score)
                    self._report_score(score)

    def _report_score(self, score: ParityScore):
        """Report a single parity score."""
        status = "PASS" if score.overall_score >= 0.8 else ("WARN" if score.overall_score >= 0.6 else "FAIL")

        print(f"\n{score.format_a.upper()} vs {score.format_b.upper()}: {score.overall_score:.1%} [{status}]")
        print(f"  Sections: {'match' if score.section_count_match else 'DIFFER'} "
              f"(titles: {score.section_titles_similarity:.0%})")
        print(f"  Requirements: {'match' if score.requirement_ids_match else 'DIFFER'}")
        print(f"  Tables: {'match' if score.table_count_match else 'DIFFER'}")
        print(f"  Markdown: {score.markdown_similarity:.0%}")

        if score.divergences:
            print(f"  Divergences:")
            for d in score.divergences[:5]:
                print(f"    - {d}")

    def generate_report(self) -> Dict[str, Any]:
        """Generate final parity report."""
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        successful = sum(1 for r in self.results.values() if r.success)
        total = len(self.results)

        avg_parity = sum(s.overall_score for s in self.parity_scores) / len(self.parity_scores) if self.parity_scores else 0

        print(f"\nFormats extracted: {successful}/{total}")
        print(f"Average parity score: {avg_parity:.1%}")

        # Identify best and worst pairs
        if self.parity_scores:
            best = max(self.parity_scores, key=lambda s: s.overall_score)
            worst = min(self.parity_scores, key=lambda s: s.overall_score)
            print(f"Best parity: {best.format_a} vs {best.format_b} ({best.overall_score:.1%})")
            print(f"Worst parity: {worst.format_a} vs {worst.format_b} ({worst.overall_score:.1%})")

        # Overall verdict
        if avg_parity >= 0.8:
            print(f"\nVERDICT: PASS - Cross-format parity is good")
        elif avg_parity >= 0.6:
            print(f"\nVERDICT: WARN - Some format divergences detected")
        else:
            print(f"\nVERDICT: FAIL - Significant cross-format divergences")

        return {
            "formats_tested": list(self.results.keys()),
            "formats_successful": [f for f, r in self.results.items() if r.success],
            "average_parity": avg_parity,
            "parity_scores": [
                {
                    "formats": [s.format_a, s.format_b],
                    "score": s.overall_score,
                    "divergences": s.divergences,
                }
                for s in self.parity_scores
            ],
        }


def main():
    parser = argparse.ArgumentParser(description="Cross-Format Parity Test")
    parser.add_argument("--fixture-dir", type=Path, required=True, help="Directory with multi-format fixtures")
    parser.add_argument("--name", type=str, default="bht_cv32a65x", help="Base filename of fixtures")
    parser.add_argument("--reference", type=str, default=None,
                        help="Reference format to compare against (e.g., 'pdf')")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if not args.fixture_dir.exists():
        print(f"Fixture directory not found: {args.fixture_dir}")
        return 1

    tester = CrossFormatParityTester(
        fixture_dir=args.fixture_dir,
        name=args.name,
        verbose=not args.quiet,
    )

    tester.extract_all_formats()
    tester.compare_all_pairs(reference=args.reference)
    report = tester.generate_report()

    if args.json:
        print(json.dumps(report, indent=2))

    # Exit code based on average parity
    return 0 if report.get("average_parity", 0) >= 0.6 else 1


if __name__ == "__main__":
    exit(main())
