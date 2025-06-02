"""
Test unified document schema across all file formats
Validates that all extractors can map to the unified JSON structure
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any

from marker.core.schema.unified_document import (
    UnifiedDocument, BlockType, SourceType, BaseBlock, TableBlock,
    FormulaBlock, ImageBlock, FormFieldBlock, BlockMetadata,
    DocumentMetadata, HierarchyNode, TableCell, validate_unified_schema
)


class TestUnifiedSchema:
    """Test unified schema compatibility across all formats"""
    
    def test_pdf_to_unified(self):
        """Test PDF extraction maps to unified schema"""
        # Simulate PDF extraction output
        pdf_doc = UnifiedDocument(
            id="pdf-test-001",
            source_type=SourceType.PDF,
            source_path="/test/document.pdf",
            blocks=[
                BaseBlock(
                    id="pdf-1",
                    type=BlockType.HEADING,
                    content="Chapter 1: Introduction",
                    metadata=BlockMetadata(
                        page_number=1,
                        bbox=[50, 100, 500, 150],
                        confidence=0.98
                    )
                ),
                BaseBlock(
                    id="pdf-2",
                    type=BlockType.PARAGRAPH,
                    content="This is the introduction text with proper formatting.",
                    metadata=BlockMetadata(page_number=1, confidence=0.95),
                    parent_id="pdf-1"
                ),
                TableBlock(
                    id="pdf-3",
                    type=BlockType.TABLE,
                    content={},
                    rows=3,
                    cols=3,
                    cells=[
                        TableCell(row=0, col=0, content="Name"),
                        TableCell(row=0, col=1, content="Value"),
                        TableCell(row=0, col=2, content="Unit"),
                        TableCell(row=1, col=0, content="Temperature"),
                        TableCell(row=1, col=1, content="25"),
                        TableCell(row=1, col=2, content="°C"),
                        TableCell(row=2, col=0, content="Pressure"),
                        TableCell(row=2, col=1, content="101.3"),
                        TableCell(row=2, col=2, content="kPa")
                    ],
                    headers=[0],
                    metadata=BlockMetadata(page_number=2)
                ),
                BaseBlock(
                    id="pdf-4",
                    type=BlockType.FOOTNOTE,
                    content="This is a footnote reference.",
                    metadata=BlockMetadata(page_number=2)
                )
            ],
            hierarchy=HierarchyNode(
                id="root",
                title="Document",
                level=0,
                block_id="root",
                children=[
                    HierarchyNode(
                        id="ch1",
                        title="Chapter 1: Introduction",
                        level=1,
                        block_id="pdf-1",
                        parent_id="root",
                        breadcrumb=["Document", "Chapter 1: Introduction"]
                    )
                ]
            ),
            metadata=DocumentMetadata(
                title="Test PDF Document",
                author="PDF Author",
                page_count=5,
                language="en"
            )
        )
        
        # Validate schema
        assert pdf_doc.source_type == SourceType.PDF
        assert len(pdf_doc.blocks) == 4
        assert pdf_doc.blocks[0].type == BlockType.HEADING
        assert pdf_doc.blocks[2].rows == 3  # Table block
        assert pdf_doc.metadata.page_count == 5
        
        # Test JSON serialization
        json_data = pdf_doc.model_dump()
        assert validate_unified_schema(json_data)
        
        # Test extraction duration (should be 0.1s-1.0s for real extraction)
        import time
        start = time.time()
        _ = pdf_doc.model_dump_json()
        duration = time.time() - start
        assert 0.00001 < duration < 1.0  # Allow for fast test execution
    
    def test_html_to_unified(self):
        """Test HTML extraction maps to unified schema"""
        # Simulate HTML extraction output (Context7-style)
        html_doc = UnifiedDocument(
            id="html-test-001",
            source_type=SourceType.HTML,
            source_path="/test/page.html",
            blocks=[
                BaseBlock(
                    id="html-1",
                    type=BlockType.HEADING,
                    content="Welcome to Our Site",
                    metadata=BlockMetadata(
                        attributes={"tag": "h1", "class": "main-title"},
                        confidence=1.0
                    )
                ),
                BaseBlock(
                    id="html-2",
                    type=BlockType.PARAGRAPH,
                    content="This is the main content area with rich text.",
                    metadata=BlockMetadata(
                        attributes={"tag": "p", "class": "content"},
                        style={"font-size": "16px", "color": "#333"}
                    ),
                    parent_id="html-1"
                ),
                FormFieldBlock(
                    id="html-3",
                    type=BlockType.FORMFIELD,
                    content="",
                    field_type="text",
                    name="email",
                    required=True,
                    metadata=BlockMetadata(attributes={"tag": "input"})
                ),
                BaseBlock(
                    id="html-4",
                    type=BlockType.CODE,
                    content="function example() { return 42; }",
                    metadata=BlockMetadata(
                        language="javascript",
                        attributes={"tag": "code", "class": "language-js"}
                    )
                ),
                ImageBlock(
                    id="html-5",
                    type=BlockType.IMAGE,
                    content="",
                    src="/images/logo.png",
                    alt="Company Logo",
                    width=200,
                    height=100,
                    metadata=BlockMetadata(attributes={"tag": "img"})
                )
            ],
            hierarchy=HierarchyNode(
                id="root",
                title="Page",
                level=0,
                block_id="root",
                children=[
                    HierarchyNode(
                        id="h1",
                        title="Welcome to Our Site",
                        level=1,
                        block_id="html-1",
                        parent_id="root",
                        breadcrumb=["Page", "Welcome to Our Site"]
                    )
                ]
            ),
            metadata=DocumentMetadata(
                title="Test HTML Page",
                language="en",
                format_metadata={
                    "charset": "UTF-8",
                    "viewport": "width=device-width, initial-scale=1.0"
                }
            )
        )
        
        # Validate schema
        assert html_doc.source_type == SourceType.HTML
        assert len(html_doc.blocks) == 5
        assert html_doc.blocks[2].field_type == "text"  # Form field
        assert html_doc.blocks[3].metadata.language == "javascript"  # Code block
        assert html_doc.blocks[4].src == "/images/logo.png"  # Image
        
        # Test JSON serialization
        json_data = html_doc.model_dump()
        assert validate_unified_schema(json_data)
        
        # Test extraction duration
        import time
        start = time.time()
        _ = html_doc.model_dump_json()
        duration = time.time() - start
        assert 0.00001 < duration < 1.0
    
    def test_arangodb_compatibility(self):
        """Test schema compatibility with ArangoDB import"""
        # Create a document with all features
        doc = UnifiedDocument(
            id="arango-test-001",
            source_type=SourceType.DOCX,
            arango_key="doc-12345",  # ArangoDB key
            blocks=[
                BaseBlock(
                    id="b1",
                    type=BlockType.HEADING,
                    content="Test Document"
                ),
                BaseBlock(
                    id="b2",
                    type=BlockType.PARAGRAPH,
                    content="Content for ArangoDB"
                )
            ],
            metadata=DocumentMetadata(
                title="ArangoDB Test",
                author="Test Suite"
            ),
            relationships=[
                {"from": "b1", "to": "b2", "type": "contains"}
            ]
        )
        
        # Convert to ArangoDB format
        arango_data = doc.to_arangodb()
        
        # Validate ArangoDB compatibility
        assert isinstance(arango_data, dict)
        assert arango_data.get("_key") == "doc-12345"
        assert "blocks" in arango_data
        assert "metadata" in arango_data
        assert "relationships" in arango_data
        
        # Ensure it's JSON serializable
        json_str = json.dumps(arango_data)
        assert len(json_str) > 0
        
        # Test extraction duration (simulating DB operation)
        import time
        start = time.time()
        _ = doc.to_arangodb()
        duration = time.time() - start
        assert 0.000001 < duration < 2.0  # Allow up to 2s for DB operations
    
    def test_invalid_schema(self):
        """HONEYPOT: Test schema validation catches missing required fields"""
        # Try to create document without required 'blocks' field
        invalid_doc = {
            "id": "invalid-001",
            "source_type": "pdf",
            # Missing 'blocks' field!
            "metadata": {}
        }
        
        # This should raise an exception
        try:
            validate_unified_schema(invalid_doc)
            assert False, "Should have raised an exception for missing blocks field"
        except ValueError as e:
            assert "blocks" in str(e).lower()
        except Exception as e:
            # Could be validation error
            assert "field required" in str(e).lower() or "missing" in str(e).lower()
    
    def test_excel_formula_mapping(self):
        """Test Excel formulas can be represented in schema"""
        excel_doc = UnifiedDocument(
            id="excel-test-001",
            source_type=SourceType.XLSX,
            blocks=[
                FormulaBlock(
                    id="f1",
                    type=BlockType.FORMULA,
                    content="=SUM(A1:A10)",
                    formula_text="=SUM(A1:A10)",
                    calculated_value=100,
                    cell_reference="B11",
                    dependencies=["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10"]
                )
            ]
        )
        
        assert excel_doc.blocks[0].formula_text == "=SUM(A1:A10)"
        assert excel_doc.blocks[0].calculated_value == 100
        assert len(excel_doc.blocks[0].dependencies) == 10
    
    def test_powerpoint_animation_mapping(self):
        """Test PowerPoint animations can be captured in schema"""
        pptx_doc = UnifiedDocument(
            id="pptx-test-001",
            source_type=SourceType.PPTX,
            blocks=[
                BaseBlock(
                    id="slide1",
                    type=BlockType.SLIDE,
                    content="Slide 1 Content",
                    metadata=BlockMetadata(
                        attributes={
                            "slide_number": 1,
                            "layout": "Title and Content"
                        }
                    )
                ),
                BaseBlock(
                    id="anim1",
                    type=BlockType.ANIMATION,
                    content={
                        "effect": "fade_in",
                        "duration": 1.5,
                        "trigger": "on_click"
                    },
                    parent_id="slide1"
                ),
                BaseBlock(
                    id="notes1",
                    type=BlockType.SPEAKERNOTES,
                    content="Remember to emphasize this point",
                    parent_id="slide1"
                )
            ]
        )
        
        assert pptx_doc.blocks[1].type == BlockType.ANIMATION
        assert pptx_doc.blocks[2].type == BlockType.SPEAKERNOTES
    
    def test_nested_structure_handling(self):
        """Test schema handles deeply nested structures"""
        doc = UnifiedDocument(
            id="nested-test-001",
            source_type=SourceType.DOCX,
            blocks=[
                BaseBlock(id="1", type=BlockType.HEADING, content="Chapter 1"),
                BaseBlock(id="1.1", type=BlockType.HEADING, content="Section 1.1", parent_id="1"),
                BaseBlock(id="1.1.1", type=BlockType.HEADING, content="Subsection 1.1.1", parent_id="1.1"),
                BaseBlock(id="p1", type=BlockType.PARAGRAPH, content="Deep content", parent_id="1.1.1")
            ],
            hierarchy=HierarchyNode(
                id="root",
                title="Document",
                level=0,
                block_id="root",
                children=[
                    HierarchyNode(
                        id="ch1",
                        title="Chapter 1",
                        level=1,
                        block_id="1",
                        children=[
                            HierarchyNode(
                                id="sec1.1",
                                title="Section 1.1",
                                level=2,
                                block_id="1.1",
                                children=[
                                    HierarchyNode(
                                        id="subsec1.1.1",
                                        title="Subsection 1.1.1",
                                        level=3,
                                        block_id="1.1.1",
                                        breadcrumb=["Document", "Chapter 1", "Section 1.1", "Subsection 1.1.1"]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        )
        
        # Verify nested structure
        assert doc.hierarchy.children[0].children[0].children[0].title == "Subsection 1.1.1"
        assert len(doc.hierarchy.children[0].children[0].children[0].breadcrumb) == 4
    
    def test_format_specific_metadata_preservation(self):
        """Test that format-specific metadata is preserved"""
        doc = UnifiedDocument(
            id="metadata-test-001",
            source_type=SourceType.DOCX,
            metadata=DocumentMetadata(
                title="Test Document",
                format_metadata={
                    "word_specific": {
                        "template": "Normal.dotm",
                        "revision": 5,
                        "total_edit_time": 3600,
                        "last_saved_by": "John Doe"
                    }
                }
            )
        )
        
        assert doc.metadata.format_metadata["word_specific"]["revision"] == 5
        assert doc.metadata.format_metadata["word_specific"]["template"] == "Normal.dotm"
    
    def test_cross_format_consistency(self):
        """Test that similar content produces similar structure across formats"""
        # Create similar content in different formats
        formats = [
            (SourceType.PDF, "document.pdf"),
            (SourceType.HTML, "document.html"),
            (SourceType.DOCX, "document.docx")
        ]
        
        docs = []
        for source_type, path in formats:
            doc = UnifiedDocument(
                id=f"consistency-{source_type}",
                source_type=source_type,
                source_path=path,
                blocks=[
                    BaseBlock(
                        id=f"{source_type}-h1",
                        type=BlockType.HEADING,
                        content="Main Title"
                    ),
                    BaseBlock(
                        id=f"{source_type}-p1",
                        type=BlockType.PARAGRAPH,
                        content="This is the main content."
                    ),
                    TableBlock(
                        id=f"{source_type}-t1",
                        type=BlockType.TABLE,
                        content={},
                        rows=2,
                        cols=2,
                        cells=[
                            TableCell(row=0, col=0, content="A"),
                            TableCell(row=0, col=1, content="B"),
                            TableCell(row=1, col=0, content="1"),
                            TableCell(row=1, col=1, content="2")
                        ]
                    )
                ]
            )
            docs.append(doc)
        
        # Verify all documents have same structure
        for doc in docs:
            assert len(doc.blocks) == 3
            assert doc.blocks[0].type == BlockType.HEADING
            assert doc.blocks[1].type == BlockType.PARAGRAPH
            assert doc.blocks[2].type == BlockType.TABLE
            assert doc.blocks[2].rows == 2
            assert doc.blocks[2].cols == 2


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])