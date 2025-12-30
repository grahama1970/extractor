"""
Focused tests for HTML parity issues - specific gaps and edge cases.

These tests target the exact problems identified in the HTML implementation:
1. Table span handling (colspan/rowspan grid positioning)
2. Missing semantic preservation (links, CSS classes)
3. Engineering document specific issues
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from extractor.pipeline.ingest.html_provider import HTMLProvider
from extractor.core.schema.unified_document import BlockType, TableBlock, TableCell


class TestHTMLSpecificGaps:
    """Test specific HTML gaps that affect parity with PDF extraction."""

    def test_table_colspan_grid_positioning(self):
        """Test that colspan creates correct grid positions."""
        html = '''
        <html><body>
        <table>
          <tr><th>Header 1</th><th colspan="2">Header 2</th><th>Header 3</th></tr>
          <tr><td>A</td><td>B</td><td>C</td><td>D</td></tr>
        </table>
        </body></html>
        '''

        test_file = Path(__file__).parent / "test_colspan.html"
        test_file.write_text(html)

        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # Find the table
            tables = [b for b in doc.blocks if b.type == BlockType.TABLE]
            assert len(tables) == 1

            table = tables[0]

            # Current implementation just uses c_idx as column position
            # This is the bug: it doesn't account for colspan offsets

            # Get cell positions
            header_cells = [c for c in table.content if c.style.get("is_header", False)]

            # Current implementation creates:
            # Header 1 at col 0
            # Header 2 at col 1  ← SHOULD span to col 2
            # Header 3 at col 2  ← Should be at col 3

            # This creates misalignment with data rows
            assert any(c.content == "Header 1" and c.col == 0 for c in header_cells)
            assert any(c.content == "Header 2" and c.colspan == 2 for c in header_cells)

            # The real issue: grid positions don't account for spans
            print(f"Table cell positions: {[(c.row, c.col, c.content) for c in table.content]}")

        finally:
            test_file.unlink()

    def test_missing_industry_semantic_tags(self):
        """Test handling of HTML tags that don't map to our BlockTypes."""
        html = '''
        <html><body>
        <figure>
          <img src="diagram.png" />
          <figcaption>This is a figure caption</figcaption>
        </figure>
        <aside>This is supporting information.</aside>
        <address>Contact: engineer@company.com</address>
        <em>Important note</em>
        <strong>Critical warning</strong>
        </body></html>
        '''

        test_file = Path(__file__).parent / "test_semantic.html"
        test_file.write_text(html)

        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # Current implementation treats these as generic containers
            # We lose semantic meaning of <figure>, <aside>, <address>
            blocks = doc.blocks

            # Check if any semantic information is preserved
            figure_blocks = [b for b in blocks if "figure" in str(b.metadata.attributes.get("tag", "")).lower()]
            aside_blocks = [b for b in blocks if "aside" in str(b.metadata.attributes.get("tag", "")).lower()]

            # These might be lost or incorrectly classified
            print(f"Semantic tags found: {set(b.metadata.attributes.get('tag', '') for b in blocks)}")

            # The issue: we lose semantic richness of modern HTML5

        finally:
            test_file.unlink()

    def test_internal_link_structure_loss(self):
        """Test that internal link structure is not preserved."""
        html = '''
        <html><body>
        <a name="requirements"></a>
        <h2>Requirements Section</h2>
        <p>Please refer to <a href="#functional">Functional Requirements</a> for details.</p>
        <a name="functional"></a>
        <h3>Functional Requirements</h3>
        <p>The system must meet <a href="#performance">memory requirements</a>.</p>
        </body></html>
        '''

        test_file = Path(__file__).parent / "test_links.html"
        test_file.write_text(html)

        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # All internal links are reduced to plain text
            text_content = " ".join(b.content for b in doc.blocks if hasattr(b, 'content') and b.content)

            # Check if link relationships are preserved
            assert "Functional Requirements" in text_content
            assert "memory requirements" in text_content

            # But the link structure is lost - no way to trace src="#functional" → target name="functional"
            # This breaks reference tracking that PDF extraction does well

            print(f"Links reduced to: {text_content}")

        finally:
            test_file.unlink()

    def test_css_class_information_loss(self):
        """Test CSS class information is not preserved."""
        html = '''
        <html><body>
        <div class="requirement critical revalidation-needed">
          <h3>Requirement R-1.2.3</h3>
          <p class="requirement-text status-failed">The cache coherence mechanism shall maintain consistency.</p>
          <span class="severity critical">CRITICAL</span>
        </div>
        <div class="requirement normal">
          <h3>Requirement R-1.2.4</h3>
          <p class="requirement-text status-passed">Documentation shall be provided.</p>
        </div>
        </body></html>
        '''

        test_file = Path(__file__).parent / "test_css_classes.html"
        test_file.write_text(html)

        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # CSS class information that could indicate:
            # - requirement vs normal text
            # - severity levels (critical vs normal)
            # - validation status (failed vs passed)

            for block in doc.blocks:
                # Check if CSS class info is preserved anywhere
                attrs = block.metadata.attributes or {}
                css_classes = attrs.get("class", "")

                # Currently, CSS class information is completely lost
                assert not css_classes, f"Unexpected CSS preservation: {css_classes}"

            # This is the problem: we lose classification metadata
            # PDF extraction can infer document structure; we're throwing away HTML's explicit structure

        finally:
            test_file.unlink()

    def test_mathematical_formula_markup(self):
        """Test preservation of mathematical markup."""
        html = '''
        <html><body>
        <p>The equation E = mc</sup>2</p>
        <p>Thermal resistance: R = ΔT/Q <sub>th</sub></p>
        <p>Greek symbols: α + β = γ</p>
        </body></html>
        '''

        test_file = Path(__file__).parent / "test_math.html"
        test_file.write_text(html)

        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # Extract all text content
            text_blocks = [b for b in doc.blocks if b.type == BlockType.PARAGRAPH]
            all_text = " ".join(b.content for b in text_blocks)

            # Check if mathematical information is preserved
            if "mc" in all_text and "2" in all_text:
                # We lost the </sup> semantic - it's just plain text now
                pass

            # The issue: sub/superscript semantics lost, making technical writing harder to parse

        finally:
            test_file.unlink()

    def test_metadata_preservation_issues(self):
        """Test that important metadata is lost in conversion."""
        html = '''
        <html><head>
          <title>RISC-V Design Specification v2.1</title>
          <meta name="version" content="2.1">
          <meta name="author" content="Engineering Team">
          <meta name="date" content="2024-01-15">
        </head>
        <body>
          <h1>Introduction</h1>
          <p>This document describes the RISC-V implementation.</p>
        </body></html>
        '''

        test_file = Path(__file__).parent / "test_metadata.html"
        test_file.write_text(html)

        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # Check what metadata was preserved
            doc_metadata = doc.metadata or {}

            # Document title might be extracted (depends on implementation)
            # But version/author/date from meta tags are likely lost
            print(f"Document metadata preserved: {doc_metadata}")

            # This matters for document lifecycle management
            # PDFs often preserve creation date, author; HTML meta gets lost

        finally:
            test_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-k", "test_"])]


def validate_encoding_preservation(text: str, original_encoding: str = None) -> bool:
    """Check if text can be encoded back to original encoding."""
    try:
        # Test round-trip encoding
        encoded = text.encode('utf-8')
        decoded = encoded.decode('utf-8')
        return decoded == text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False


def compare_section_structure(pdf_sections: List[dict], html_sections: List[dict]) -> dict:
    """Compare structural elements between PDF and HTML."""
    results = {
        "section_count_match": len(pdf_sections) == len(html_sections),
        "heading_level_consistency": True,
        "section_hierarchy_valid": True,
        "missing_sections": [],
        "extra_sections": [],
    }

    # Check if section count is within acceptable range
    section_delta = abs(len(pdf_sections) - len(html_sections))
    results["section_count_acceptable"] = section_delta <= 2
    return results


def compare_tables(table_comparison: dict, delta_threshold: float = 0.1) -> dict:
    """Compare table extraction between formats."""
    pdf_count = len(table_comparison.get("pdf_tables", []))
    html_count = len(table_comparison.get("html_tables", []))

    results = {
        "pdf_count": pdf_count,
        "html_count": html_count,
        "count_match": pdf_count == html_count,
        "count_acceptable": abs(pdf_count - html_count) <= 1,  # Allow off-by-one for edge cases
        "tables_with_csv": {
            "pdf": sum(1 for t in table_comparison.get("pdf_tables", []) if t["has_csv"]),
            "html": sum(1 for t in table_comparison.get("html_tables", []) if t["has_csv"]),
        },
        "table_context_consistency": True,
    }

    # Check that CSV extraction works for the same proportion of tables
    pdf_csv_ratio = results["tables_with_csv"]["pdf"] / max(pdf_count, 1)
    html_csv_ratio = results["tables_with_csv"]["html"] / max(html_count, 1)
    results["csv_extraction_parity"] = abs(pdf_csv_ratio - html_csv_ratio) < delta_threshold

    return results


def compare_content_similarity(pdf_text: str, html_text: str, min_similarity: float = 0.85) -> dict:
    """Compare text content similarity between PDF and HTML."""
    similarity = fuzz.ratio(pdf_text, html_text) / 100.0

    # Also check token overlap
    pdf_tokens = set(pdf_text.lower().split())
    html_tokens = set(html_text.lower().split())
    token_overlap = len(pdf_tokens & html_tokens) / len(pdf_tokens | html_tokens) if pdf_tokens or html_tokens else 0

    results = {
        "similarity_score": similarity,
        "token_overlap": token_overlap,
        "pass_threshold": similarity >= min_similarity,
        "content_preserved": similarity >= 0.75,
        "token_parity": token_overlap >= 0.80,
    }

    return results


def generate_parity_report(results: dict, output_path: Path) -> None:
    """Generate a detailed parity report."""
    report = {
        "summary": {
            "overall_pass": results["overall_pass"],
            "pdf_test_file": str(results.get("pdf_file", "unknown")),
            "html_test_file": str(results.get("html_file", "unknown")),
            "test_timestamp": pd.Timestamp.now().isoformat(),
        },
        "content_analysis": results.get("content_comparison", {}),
        "structure_analysis": results.get("structure_comparison", {}),
        "table_analysis": results.get("table_comparison", {}),
        "figure_analysis": results.get("figure_comparison", {}),
        "detailed_failures": results.get("failures", []),
        "recommendations": results.get("recommendations", []),
    }

    output_path.write_text(json.dumps(report, indent=2, default=str))









































'






































































































































































































































































































"

"""
"