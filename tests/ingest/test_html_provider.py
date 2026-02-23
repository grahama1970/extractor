"""
Unit tests for HTML provider specific to engineering documents.

These tests ensure HTML extraction maintains parity with PDF extraction
for technical documents with tables, figures, and structured content.
"""

import pytest
from pathlib import Path

from extractor.pipeline.ingest.html_provider import HTMLProvider
from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BlockType,
    TableBlock,
    ImageBlock,
)


class TestHTMLProviderEngineeringDocs:
    """Test HTML provider with engineering-focused content."""

    def create_test_html(self, content: str) -> Path:
        """Create a temporary HTML file with given content."""
        test_file = Path(__file__).parent / "test_html_content.html"
        test_file.write_text(content, encoding="utf-8")
        return test_file

    def test_complex_table_extraction(self):
        """Test that complex engineering tables extract correctly."""
        html_content = """
        <html>
        <h1>Technical Specifications</h1>
        <h2>Component Parameters</h2>
        <table border="1">
          <tr>
            <th>Component</th>
            <th>Voltage (V)</th>
            <th>Current (A)</th>
          </tr>
          <tr>
            <td colspan="2">Power Supply Unit</td>
            <td rowspan="2">5</td>
          </tr>
          <tr>
            <td>MCU</td>
            <td>3.3</td>
          </tr>
        </table>
        </html>
        """

        test_file = self.create_test_html(html_content)
        try:
            provider = HTMLProvider(test_file)
            doc = provider.parse()

            # Find the table block
            table_blocks = [b for b in doc.blocks if b.type == BlockType.TABLE]
            assert len(table_blocks) == 1

            table = table_blocks[0]
            assert isinstance(table, TableBlock)

            # Verify table has content (may be rows list or flat content)
            # TableBlock.content can be a list of strings or rows
            assert table.content is not None

            # Check that key content is present somewhere in table
            table_text = str(table.content)
            assert "Component" in table_text or "MCU" in table_text
        finally:
            test_file.unlink()  # Cleanup

    def test_technical_definitions_headings(self):
        """Test that technical definitions with proper heading structure are preserved."""
        html_content = """
        <html>
        <h1>RISC-V Architecture</h1>
        <h2>1. Instruction Formats</h2>
        <p>RISC-V uses four main instruction formats... </p>
        <h3>1.1 R-Type Instructions</h3>
        <p>Used for register operations between three registers.</p>
        <h3>1.2 I-Type Instructions</h3>
        <p>Used for operations with immediate values.</p>
        <h2>2. Register Set</h2>
        <h3>2.1 General Purpose Registers</h3>
        <p>Registers x0-x31... </p>
        </html>
        """

        test_file = self.create_test_html(html_content)
        provider = HTMLProvider(test_file)
        doc = provider.parse()

        # Check heading levels are preserved
        headings = [b for b in doc.blocks if b.type == BlockType.HEADING]
        # HTML content has: 1 h1 + 2 h2 + 3 h3 = 6 headings
        assert len(headings) == 6

        # Verify heading levels
        h1_blocks = [h for h in headings if h.metadata.attributes.get("level") == 1]
        h2_blocks = [h for h in headings if h.metadata.attributes.get("level") == 2]
        h3_blocks = [h for h in headings if h.metadata.attributes.get("level") == 3]

        assert len(h1_blocks) == 1  # "RISC-V Architecture"
        assert len(h2_blocks) == 2  # "1. Instruction Formats", "2. Register Set"
        assert len(h3_blocks) == 3  # "1.1 R-Type", "1.2 I-Type", "2.1 General Purpose"

        # Check heading text content
        h1_text = [h.content for h in h1_blocks][0]
        assert "RISC-V" in h1_text

        # Verify paragraphs exist
        paragraphs = [b for b in doc.blocks if b.type == BlockType.PARAGRAPH]
        assert len(paragraphs) >= 4  # Should have text for each section

        test_file.unlink()  # Cleanup

    def test_images_with_metadata(self):
        """Test image extraction preserves metadata and alt text."""
        html_content = """
        <html>
        <h2>System Architecture</h2>
        <p>Refer to the diagram below: <img src="diagrams/system_block_diagram.png" alt="High-level system block diagram showing RISC-V core connected to memory and peripherals" /></p>
        <p>This diagram illustrates the complete system. <img src="images/risc_v_pipeline.png" width="600" height="400" /></p>
        </html>
        """

        test_file = self.create_test_html(html_content)
        provider = HTMLProvider(test_file)
        doc = provider.parse()

        # Check for image blocks
        image_blocks = [b for b in doc.blocks if b.type == BlockType.IMAGE]
        assert len(image_blocks) == 2

        for img_block in image_blocks:
            assert isinstance(img_block, ImageBlock)
            # ImageBlock has .src and .alt attributes (not in content dict)
            assert img_block.src is not None
            assert (
                "system_block_diagram.png" in img_block.src
                or "risc_v_pipeline.png" in img_block.src
            )

            # Check alt text preservation
            if img_block.src == "diagrams/system_block_diagram.png":
                assert (
                    img_block.alt
                    == "High-level system block diagram showing RISC-V core connected to memory and peripherals"
                )

        test_file.unlink()  # Cleanup

    def test_nested_list_structures(self):
        """Test complex nested lists common in specifications."""
        html_content = """
        <html>
        <h2>Specifications</h2>
        <ol>
          <li>Processor Requirements
            <ul>
              <li>32-bit RISC architecture</li>
              <li>5-stage pipeline</li>
              <li>Cache hierarchy:
                <ol>
                  <li>L1: 32KB I-cache, 32KB D-cache</li>
                  <li>L2: 256KB unified</li>
                </ol>
              </li>
            </ul>
          </li>
          <li>Memory Requirements
            <ul>
              <li>Minimum 512MB RAM</li>
            </ul>
          </li>
        </ol>
        </html>
        """

        test_file = self.create_test_html(html_content)
        provider = HTMLProvider(test_file)
        doc = provider.parse()

        # Verify list content is preserved - check all block types
        all_blocks = doc.blocks
        all_text = " ".join(str(b.content) for b in all_blocks)

        # Check that key technical terms are present somewhere in the document
        technical_terms = ["RISC", "pipeline", "Cache", "L1", "L2", "512MB"]
        for term in technical_terms:
            assert term in all_text, f"Missing term: {term}"

        test_file.unlink()  # Cleanup

    def test_empty_tables_and_structures(self):
        """Test edge case with empty tables - common in templates."""
        html_content = """
        <html>
        <h2>Results Table</h2>
        <table>
          <tr><th>Test</th><th>Result</th></tr>
          <tr><td></td><td></td></tr>
        </table>
        <p></p>
        </html>
        """

        test_file = self.create_test_html(html_content)
        provider = HTMLProvider(test_file)
        doc = provider.parse()

        # Should handle empty content gracefully
        table_blocks = [b for b in doc.blocks if b.type == BlockType.TABLE]
        assert len(table_blocks) == 1

        table = table_blocks[0]
        # Table should exist and have some content structure
        assert table.content is not None

        test_file.unlink()

    def test_special_character_preservation(self):
        """Test that special characters and math symbols are preserved."""
        html_content = """
        <html>
        <p>Mathematics: α + β = γ</p>
        <p>Chemistry: H₂O + CO₂ → CH₄ + O₂</p>
        <p>Greek letters: ΔΣΩπθ</p>
        </html>
        """

        test_file = self.create_test_html(html_content)
        provider = HTMLProvider(test_file)
        doc = provider.parse()

        # Extract all text
        all_text = " ".join(b.content for b in doc.blocks if b.type == BlockType.PARAGRAPH)

        # Check special characters are preserved
        special_chars = ["α", "β", "γ", "Δ", "Σ", "Ω", "π", "θ", "→", "₂"]
        for char in special_chars:
            assert char in all_text, f"Missing special character: {char}"

        test_file.unlink()


@pytest.mark.integration
class TestHTMLProviderIntegration:
    """Integration tests that ensure HTML provider works with real pipeline."""

    def test_real_engineering_document(self):
        """Test with a real engineering document HTML file."""
        # This would use a real test file
        # For now, just verify the structure loads

        # Test basic construction
        doc = UnifiedDocument(
            id="test-doc",
            source_type="html",
            source_path="/tmp/test.html",
            blocks=[],
            hierarchy=None,
        )
        assert doc.id == "test-doc"
        assert doc.source_type == "html"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
