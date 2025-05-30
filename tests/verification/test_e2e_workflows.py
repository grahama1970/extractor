#!/usr/bin/env python3
"""
End-to-end workflow verification tests for marker.
"""

import os
import sys
import time
import json
import subprocess
import tempfile
from pathlib import Path

# Import what we need for direct API testing
from marker.core.models import create_model_dict
from marker.core.converters.pdf import PdfConverter


def test_pdf_to_json_workflow():
    """Test complete PDF to JSON conversion workflow."""
    start_time = time.time()
    
    # Find test PDF
    test_pdf = Path(".")
    if not test_pdf.exists():
        test_pdf = Path(".")
    
    assert test_pdf.exists(), f"Test PDF not found: {test_pdf}"
    
    # Test via command line
    with tempfile.TemporaryDirectory() as temp_dir:
        # Run the script directly
        convert_script = Path(".")
        
        cmd = [
            sys.executable,
            str(convert_script),
            str(test_pdf),
            "--output_dir", str(temp_dir),
            "--output_format", "json"
        ]
        
        # Run conversion
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd="."
        )
        
        # Check result
        print(f"Command exit code: {result.returncode}")
        print(f"STDOUT: {result.stdout[:500]}...")  # First 500 chars
        print(f"STDERR: {result.stderr[:500]}...")  # First 500 chars
        
        if result.returncode != 0:
            assert False, f"PDF conversion failed with exit code {result.returncode}: {result.stderr}"
        
        # Find output file (output is in a subdirectory named after the input file)
        output_dirs = list(Path(temp_dir).iterdir())
        print(f"Directories in {temp_dir}: {output_dirs}")
        
        # Look for JSON files in subdirectories
        output_files = []
        for subdir in output_dirs:
            if subdir.is_dir():
                json_files = list(subdir.glob("*.json"))
                output_files.extend(json_files)
        
        print(f"JSON files found: {output_files}")
        assert len(output_files) > 0, f"No output JSON files found in {temp_dir} subdirectories"
        output_path = output_files[0]
        
        # Validate JSON
        with open(output_path) as f:
            data = json.load(f)
        
        assert isinstance(data, dict), "Output should be a dictionary"
        
        # Check file size is reasonable
        file_size = output_path.stat().st_size
        assert file_size > 1000, f"Output file too small: {file_size} bytes"
        
    duration = time.time() - start_time
    assert duration > 5.0, f"Conversion too fast ({duration:.3f}s), possibly mocked"
    assert duration < 120.0, f"Conversion too slow ({duration:.3f}s)"
    
    print(f"✓ PDF to JSON workflow completed in {duration:.3f}s")
    return True


def test_pdf_to_json_api():
    """Test PDF to JSON conversion via API."""
    start_time = time.time()
    
    # Find test PDF
    test_pdf = Path(".")
    if not test_pdf.exists():
        test_pdf = Path(".")
    
    assert test_pdf.exists(), f"Test PDF not found: {test_pdf}"
    
    # Create models
    models = create_model_dict()
    
    # Create converter
    config = {
        'output_format': 'json',
        'use_llm': False,
        'max_pages': 2,  # Limit for speed
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        processor_list=None,
        renderer='marker.core.renderers.json.JSONRenderer',
        llm_service=None
    )
    
    # Convert
    json_output = converter(str(test_pdf))
    
    # Validate output
    if hasattr(json_output, 'model_dump_json'):
        json_str = json_output.model_dump_json(exclude=["metadata"], indent=2)
    else:
        json_str = json_output
    
    data = json.loads(json_str)
    assert isinstance(data, dict), "Output should be a dictionary"
    assert len(json_str) > 1000, "Output too small"
    
    duration = time.time() - start_time
    assert duration > 2.0, f"API conversion too fast ({duration:.3f}s)"
    assert duration < 60.0, f"API conversion too slow ({duration:.3f}s)"
    
    print(f"✓ PDF to JSON API workflow completed in {duration:.3f}s")
    return True


def test_pdf_to_arangodb_workflow():
    """Test PDF to ArangoDB export workflow."""
    start_time = time.time()
    
    # Find test PDF
    test_pdf = Path(".")
    if not test_pdf.exists():
        test_pdf = Path(".")
    
    assert test_pdf.exists(), f"Test PDF not found: {test_pdf}"
    
    # Create models
    models = create_model_dict()
    
    # Create converter with ArangoDB renderer
    config = {
        'output_format': 'arangodb',
        'use_llm': False,
        'max_pages': 1,  # Just one page for speed
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        processor_list=None,
        renderer='marker.core.renderers.arangodb_json.ArangoDBRenderer',
        llm_service=None
    )
    
    # Convert
    arango_output = converter(str(test_pdf))
    
    # Validate output
    if hasattr(arango_output, 'model_dump'):
        arango_data = arango_output.model_dump()
    else:
        arango_data = json.loads(arango_output)
    
    # Check basic structure
    assert isinstance(arango_data, dict), "ArangoDB output should be a dictionary"
    
    # The ArangoDB renderer returns: document, metadata, validation, raw_corpus
    print(f"ArangoDB output keys: {list(arango_data.keys())}")
    
    # Check for expected keys based on actual output
    assert 'document' in arango_data, f"Missing document key, got keys: {list(arango_data.keys())}"
    assert 'metadata' in arango_data, f"Missing metadata key, got keys: {list(arango_data.keys())}"
    
    # Check document structure
    doc = arango_data['document']
    assert isinstance(doc, dict), "Document should be a dictionary"
    assert 'pages' in doc, f"Document missing pages field: {list(doc.keys())}"
    assert isinstance(doc['pages'], list), "Pages should be a list"
    assert len(doc['pages']) > 0, "Document has no pages"
    
    # Check that document has content
    assert len(str(arango_data['document'])) > 100, "Document seems empty"
    
    duration = time.time() - start_time
    assert duration > 1.0, f"ArangoDB export too fast ({duration:.3f}s)"
    assert duration < 120.0, f"ArangoDB export too slow ({duration:.3f}s)"
    
    print(f"✓ PDF to ArangoDB workflow completed in {duration:.3f}s")
    return True


def test_table_extraction_workflow():
    """Test table extraction in the workflow."""
    start_time = time.time()
    
    # Use a PDF known to have tables
    test_pdf = Path(".")
    assert test_pdf.exists(), f"Test PDF not found: {test_pdf}"
    
    # Create models
    models = create_model_dict()
    
    # Create converter
    config = {
        'output_format': 'json',
        'use_llm': False,
        'max_pages': 5,
        'ocr_all_pages': False,
        'parallel_factor': 1
    }
    
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        processor_list=None,
        renderer='marker.core.renderers.json.JSONRenderer',
        llm_service=None
    )
    
    # Convert
    json_output = converter(str(test_pdf))
    
    # Parse output
    if hasattr(json_output, 'model_dump_json'):
        json_str = json_output.model_dump_json(exclude=["metadata"], indent=2)
    else:
        json_str = json_output
    
    data = json.loads(json_str)
    
    # Count tables
    def count_tables(obj):
        count = 0
        if isinstance(obj, dict):
            if obj.get('block_type') == 'Table':
                count += 1
            for value in obj.values():
                count += count_tables(value)
        elif isinstance(obj, list):
            for item in obj:
                count += count_tables(item)
        return count
    
    table_count = count_tables(data)
    print(f"Found {table_count} tables in the document")
    assert table_count > 0, "No tables found in document"
    
    duration = time.time() - start_time
    assert duration > 2.0, f"Table extraction too fast ({duration:.3f}s)"
    assert duration < 60.0, f"Table extraction too slow ({duration:.3f}s)"
    
    print(f"✓ Table extraction workflow completed in {duration:.3f}s")
    return True


if __name__ == "__main__":
    print("Running end-to-end workflow verification tests...")
    
    all_passed = True
    
    # Test 1: PDF to JSON via command line
    try:
        if test_pdf_to_json_workflow():
            print("\n✅ PDF to JSON workflow test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ PDF to JSON workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 2: PDF to JSON via API
    try:
        if test_pdf_to_json_api():
            print("\n✅ PDF to JSON API test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ PDF to JSON API test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 3: PDF to ArangoDB
    try:
        if test_pdf_to_arangodb_workflow():
            print("\n✅ PDF to ArangoDB workflow test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ PDF to ArangoDB workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Test 4: Table extraction
    try:
        if test_table_extraction_workflow():
            print("\n✅ Table extraction workflow test passed")
        else:
            all_passed = False
    except Exception as e:
        print(f"\n❌ Table extraction workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    if all_passed:
        print("\n🎉 All end-to-end workflow tests passed!")
    else:
        print("\n⚠️  Some tests failed")
        sys.exit(1)