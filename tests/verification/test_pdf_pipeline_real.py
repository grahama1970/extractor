#!/usr/bin/env python3
"""
Test PDF processing pipeline functionality with real PDF conversion.
"""

import os
import time
import json
import tempfile
from pathlib import Path

from marker.core.models import create_model_dict
from marker.core.converters.pdf import PdfConverter
from marker.core.schema.document import Document
from marker.core.renderers.markdown import MarkdownRenderer
from marker.core.renderers.json import JSONRenderer
from marker.core.output import save_output


def test_pdf_conversion_real():
    """Test real PDF conversion using the actual pipeline."""
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
        test_data_dir = project_root / "data" / "input"
        if test_data_dir.exists():
            pdf_files = list(test_data_dir.glob("*.pdf"))
            if pdf_files:
                test_pdf = pdf_files[0]
    
    # Skip test if no PDF found
    if not test_pdf:
        print("⚠️  No test PDF found, skipping PDF conversion test")
        return
    
    print(f"\nTesting PDF conversion with: {test_pdf.name}")
    print(f"PDF file size: {test_pdf.stat().st_size} bytes")
    
    # Create models (this may take time on first run)
    model_start = time.time()
    models = create_model_dict()
    model_time = time.time() - model_start
    print(f"✓ Models loaded in {model_time:.3f}s")
    
    # Create converter
    config = {
        'output_format': 'markdown',
        'use_llm': False,  # Disable LLM for faster testing
        'max_pages': 3,    # Limit pages for faster testing
        'start_page': 0,
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        processor_list=None,  # Use default processors
        renderer='marker.core.renderers.markdown.MarkdownRenderer',
        llm_service=None
    )
    
    # Convert PDF
    convert_start = time.time()
    rendered_output = converter(str(test_pdf))
    convert_time = time.time() - convert_start
    
    print(f"✓ PDF converted in {convert_time:.3f}s")
    
    # Verify output
    # The output might be a MarkdownOutput object or a string
    if hasattr(rendered_output, 'markdown'):
        markdown_content = rendered_output.markdown
    else:
        markdown_content = rendered_output
    
    assert isinstance(markdown_content, str), "Output should contain markdown string"
    assert len(markdown_content) > 100, "Output should have substantial content"
    
    # Save output
    with tempfile.TemporaryDirectory() as temp_dir:
        # save_output expects the rendered object, not just the string
        save_output(rendered_output, temp_dir, "test_output")
        output_file = Path(temp_dir) / "test_output.md"
        assert output_file.exists(), "Output file should be created"
        print(f"✓ Output saved to temporary file")
    
    print(f"\nOutput statistics:")
    print(f"  - Length: {len(markdown_content)} characters")
    print(f"  - Lines: {len(markdown_content.splitlines())}")
    print(f"  - Words: {len(markdown_content.split())}")
    
    duration = time.time() - start_time
    assert duration > 1.0, f"PDF conversion too fast ({duration:.3f}s), possibly mocked"
    assert duration < 60.0, f"PDF conversion too slow ({duration:.3f}s)"
    
    print(f"\n✓ Total test duration: {duration:.3f}s")
    return True


def test_table_extraction():
    """Test table extraction from PDF."""
    start_time = time.time()
    
    # Find a test PDF with tables
    test_pdf = None
    project_root = Path(__file__).parent.parent.parent
    
    # Look for Arango PDF which likely has tables
    test_candidates = [
        project_root / "data" / "input" / "Arango_AQL_Example.pdf",
        project_root / "data" / "input_test" / "2505.03335v2.pdf",
    ]
    
    for candidate in test_candidates:
        if candidate.exists():
            test_pdf = candidate
            break
    
    if not test_pdf:
        print("⚠️  No test PDF found for table extraction")
        return
    
    print(f"\nTesting table extraction with: {test_pdf.name}")
    
    # Create models
    models = create_model_dict()
    
    # Create converter with table processors
    config = {
        'output_format': 'json',  # JSON format shows structure better
        'use_llm': False,
        'max_pages': 5,  # Check first 5 pages
        'start_page': 0,
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        processor_list=None,  # Use default processors including table processor
        renderer='marker.core.renderers.json.JSONRenderer',
        llm_service=None
    )
    
    # Convert PDF
    json_output = converter(str(test_pdf))
    
    # Parse JSON to check for tables
    # The output might be a JSONOutput object
    if hasattr(json_output, 'model_dump_json'):
        json_str = json_output.model_dump_json(exclude=["metadata"], indent=2)
    else:
        json_str = json_output
    
    doc_data = json.loads(json_str)
    
    # Count tables
    table_count = 0
    # The JSON output has a children array with blocks
    if 'children' in doc_data:
        for child in doc_data['children']:
            if child.get('block_type') == 'Table':
                table_count += 1
            # Check nested children too
            if 'children' in child:
                for subchild in child['children']:
                    if subchild.get('block_type') == 'Table':
                        table_count += 1
    
    print(f"✓ Found {table_count} tables in the document")
    
    duration = time.time() - start_time
    assert duration > 1.0, f"Table extraction too fast ({duration:.3f}s)"
    assert duration < 60.0, f"Table extraction too slow ({duration:.3f}s)"
    
    print(f"✓ Table extraction completed in {duration:.3f}s")
    return True


def test_renderer_outputs():
    """Test different output renderers."""
    start_time = time.time()
    
    # Since creating proper document structure is complex, 
    # let's test renderers with a real converted document
    test_pdf = None
    project_root = Path(__file__).parent.parent.parent
    test_data_dir = project_root / "data" / "input_test"
    
    if test_data_dir.exists():
        pdf_files = list(test_data_dir.glob("*.pdf"))
        if pdf_files:
            test_pdf = pdf_files[0]
    
    if not test_pdf:
        # Try another location
        test_data_dir = project_root / "data" / "input"
        if test_data_dir.exists():
            pdf_files = list(test_data_dir.glob("*.pdf"))
            if pdf_files:
                test_pdf = pdf_files[0]
    
    # Skip test if no PDF found
    if not test_pdf:
        print("⚠️  No test PDF found, skipping renderer test")
        return True
    
    print(f"\nTesting renderers with: {test_pdf.name}")
    
    # Create models and converter
    models = create_model_dict()
    config = {
        'output_format': 'json',
        'use_llm': False,
        'max_pages': 1,  # Just one page for speed
        'start_page': 0,
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    
    # First get the document object
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        processor_list=None,
        renderer=None,  # No renderer yet
        llm_service=None
    )
    
    # Build the document without rendering
    document = converter.build_document(str(test_pdf))
    
    # Test Markdown renderer
    md_renderer = MarkdownRenderer()
    md_output = md_renderer(document)
    
    # Check the output
    if hasattr(md_output, 'markdown'):
        md_str = md_output.markdown
    else:
        md_str = md_output
    
    assert isinstance(md_str, str), "Markdown output should be a string"
    assert len(md_str) > 10, "Markdown output should have content"
    
    print("✓ Markdown renderer working")
    
    # Test JSON renderer
    json_renderer = JSONRenderer()
    json_output = json_renderer(document)
    
    # Handle JSONOutput object
    if hasattr(json_output, 'model_dump_json'):
        json_str = json_output.model_dump_json(exclude=["metadata"], indent=2)
    else:
        json_str = json_output
    
    json_data = json.loads(json_str)
    assert 'children' in json_data  # JSONOutput has children
    assert isinstance(json_data['children'], list)
    
    print("✓ JSON renderer working")
    
    # Test ArangoDB renderer
    try:
        from marker.core.renderers.arangodb_json import ArangoDBRenderer
        arango_renderer = ArangoDBRenderer()
        arango_output = arango_renderer(document)
        
        # Handle ArangoDBOutput object
        if hasattr(arango_output, 'model_dump'):
            arango_data = arango_output.model_dump()
        else:
            arango_data = json.loads(arango_output)
            
        assert 'document' in arango_data
        # ArangoDB documents should have either _key or id field
        assert '_key' in arango_data['document'] or 'id' in arango_data['document']
        
        print("✓ ArangoDB renderer working")
    except ImportError:
        print("⚠️  ArangoDB renderer not available")
    
    duration = time.time() - start_time
    assert duration > 0.5, f"Rendering too fast ({duration:.3f}s)"
    assert duration < 120.0, f"Rendering too slow ({duration:.3f}s)"  # Allow 2 minutes for model loading
    
    print(f"✓ Renderer tests completed in {duration:.3f}s")
    return True


if __name__ == "__main__":
    print("Running PDF pipeline verification tests...")
    
    all_passed = True
    
    # Test 1: Real PDF conversion
    try:
        if test_pdf_conversion_real():
            print("\n✅ PDF conversion test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ PDF conversion test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 2: Table extraction
    try:
        if test_table_extraction():
            print("\n✅ Table extraction test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ Table extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 3: Renderer outputs
    try:
        if test_renderer_outputs():
            print("\n✅ Renderer output test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ Renderer output test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    if all_passed:
        print("\n🎉 All PDF pipeline tests passed!")
    else:
        print("\n⚠️  Some tests failed")
        exit(1)