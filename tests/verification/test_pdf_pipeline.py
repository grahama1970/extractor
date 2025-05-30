#!/usr/bin/env python3
"""
Test PDF processing pipeline functionality.
"""

import os
import time
import json
import tempfile
from pathlib import Path

from marker.core.converters.pdf import PdfConverter
from marker.core.config.parser import ConfigParser
from marker.core.schema.document import Document
from marker.core.renderers.markdown import MarkdownRenderer
from marker.core.renderers.json import JSONRenderer


def test_pdf_extraction():
    """Test basic PDF extraction functionality."""
    start_time = time.time()
    
    # Find a test PDF file
    test_pdf = None
    project_root = Path(__file__).parent.parent.parent
    test_data_dir = project_root / "data" / "input_test"
    
    if test_data_dir.exists():
        pdf_files = list(test_data_dir.glob("*.pdf"))
        if pdf_files:
            test_pdf = pdf_files[0]
    
    if not test_pdf:
        # Try another location
        test_data_dir = project_root / "test_results"
        if test_data_dir.exists():
            pdf_files = list(test_data_dir.rglob("*.pdf"))
            if pdf_files:
                test_pdf = pdf_files[0]
    
    # Skip test if no PDF found
    if not test_pdf:
        print("⚠️  No test PDF found, skipping PDF extraction test")
        return
    
    print(f"\nTesting PDF extraction with: {test_pdf.name}")
    
    # Test PDF conversion
    # Create a simple config dictionary
    config = {
        'max_pages': None,
        'start_page': 0,
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    converter = PdfConverter(config=config)
    document = converter.convert(str(test_pdf))
    
    # Verify document structure
    assert isinstance(document, Document), "Converter should return a Document instance"
    assert hasattr(document, 'pages'), "Document should have pages"
    assert len(document.pages) > 0, "Document should have at least one page"
    
    # Check first page
    first_page = document.pages[0]
    assert hasattr(first_page, 'blocks'), "Page should have blocks"
    assert len(first_page.blocks) > 0, "Page should have at least one block"
    
    print(f"✓ Extracted {len(document.pages)} pages")
    print(f"✓ First page has {len(first_page.blocks)} blocks")
    
    duration = time.time() - start_time
    assert duration > 0.5, f"PDF extraction too fast ({duration:.3f}s), possibly mocked"
    assert duration < 30.0, f"PDF extraction too slow ({duration:.3f}s)"
    
    print(f"✓ PDF extraction completed in {duration:.3f}s")


def test_renderer_pipeline():
    """Test document rendering to different formats."""
    start_time = time.time()
    
    # Create a simple test document
    from marker.core.schema.document import Document
    from marker.core.schema.groups.page import PageGroup
    from marker.core.schema.blocks.text import Text
    from marker.core.schema.blocks.sectionheader import SectionHeader
    
    # Create document
    document = Document()
    
    # Create a page
    page = PageGroup(
        page_num=0,
        bbox=[0, 0, 612, 792]
    )
    
    # Add blocks to page
    header = SectionHeader(
        text="Test Section",
        level=1,
        bbox=[0, 0, 200, 50]
    )
    page.blocks.append(header)
    
    text = Text(
        text="This is a test paragraph with some content.",
        bbox=[0, 60, 200, 100]
    )
    page.blocks.append(text)
    
    # Add page to document
    document.pages.append(page)
    
    # Test Markdown rendering
    md_renderer = MarkdownRenderer()
    markdown_output = md_renderer.render(document)
    
    assert isinstance(markdown_output, str), "Markdown output should be a string"
    assert "# Test Section" in markdown_output, "Should contain the section header"
    assert "This is a test paragraph" in markdown_output, "Should contain the text"
    
    print("✓ Markdown rendering successful")
    
    # Test JSON rendering
    json_renderer = JSONRenderer()
    json_output = json_renderer.render(document)
    
    assert isinstance(json_output, str), "JSON output should be a string"
    json_data = json.loads(json_output)  # Should be valid JSON
    assert "document" in json_data, "JSON should have document key"
    assert "pages" in json_data["document"], "Document should have pages"
    
    print("✓ JSON rendering successful")
    
    duration = time.time() - start_time
    assert duration > 0.01, f"Rendering too fast ({duration:.3f}s), possibly mocked"
    assert duration < 5.0, f"Rendering too slow ({duration:.3f}s)"
    
    print(f"✓ Rendering pipeline completed in {duration:.3f}s")


def test_end_to_end_conversion():
    """Test end-to-end PDF to markdown conversion."""
    start_time = time.time()
    
    # Find a test PDF
    test_pdf = None
    project_root = Path(__file__).parent.parent.parent
    test_data_dir = project_root / "data" / "input_test"
    
    if test_data_dir.exists():
        pdf_files = list(test_data_dir.glob("*.pdf"))
        if pdf_files:
            test_pdf = pdf_files[0]
    
    if not test_pdf:
        print("⚠️  No test PDF found, skipping end-to-end test")
        return
    
    print(f"\nTesting end-to-end conversion with: {test_pdf.name}")
    
    # Convert PDF
    # Create a simple config dictionary
    config = {
        'max_pages': None,
        'start_page': 0,
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    converter = PdfConverter(config=config)
    document = converter.convert(str(test_pdf))
    
    # Render to markdown
    md_renderer = MarkdownRenderer()
    markdown_output = md_renderer.render(document)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(markdown_output)
        output_path = f.name
    
    print(f"✓ Saved markdown to: {output_path}")
    
    # Verify output
    assert os.path.exists(output_path), "Output file should exist"
    assert os.path.getsize(output_path) > 0, "Output file should not be empty"
    
    # Read and verify content
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert len(content) > 100, "Output should have substantial content"
    
    # Clean up
    os.unlink(output_path)
    
    duration = time.time() - start_time
    assert duration > 0.5, f"End-to-end conversion too fast ({duration:.3f}s)"
    assert duration < 60.0, f"End-to-end conversion too slow ({duration:.3f}s)"
    
    print(f"✓ End-to-end conversion completed in {duration:.3f}s")
    print(f"✓ Generated {len(content)} characters of markdown")


if __name__ == "__main__":
    print("Running PDF pipeline verification tests...")
    
    try:
        test_pdf_extraction()
        print("\n✅ PDF extraction test passed")
    except AssertionError as e:
        print(f"\n❌ PDF extraction test failed: {e}")
    except Exception as e:
        print(f"\n❌ PDF extraction test error: {e}")
    
    try:
        test_renderer_pipeline()
        print("\n✅ Renderer pipeline test passed")
    except AssertionError as e:
        print(f"\n❌ Renderer pipeline test failed: {e}")
    except Exception as e:
        print(f"\n❌ Renderer pipeline test error: {e}")
    
    try:
        test_end_to_end_conversion()
        print("\n✅ End-to-end conversion test passed")
    except AssertionError as e:
        print(f"\n❌ End-to-end conversion test failed: {e}")
    except Exception as e:
        print(f"\n❌ End-to-end conversion test error: {e}")