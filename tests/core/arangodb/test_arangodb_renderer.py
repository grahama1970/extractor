"""
Validation script for ArangoDB JSON renderer.

This script validates the ArangoDB JSON renderer by converting a PDF to the
ArangoDB-compatible JSON format and verifying the output against the required structure.

The renderer must produce JSON in the exact format required by ArangoDB:
{
  "document": {
    "id": "unique_document_id",
    "pages": [{
      "blocks": [{
        "type": "section_header",
        "text": "Introduction to Topic",
        "level": 1
      }]
    }]
  },
  "metadata": { ... },
  "validation": { ... },
  "raw_corpus": {
    "full_text": "Complete text...",
    "pages": [{ ... }],
    "total_pages": 1
  }
}
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional

from loguru import logger

from marker.config.parser import ParserConfig
from marker.converters.pdf import PdfConverter
from marker.renderers.arangodb_json import ArangoDBRenderer


def validate_arangodb_json_structure(data: Dict[str, Any]) -> List[str]:
    """Validate ArangoDB JSON structure against requirements.
    
    Args:
        data: Parsed JSON data to validate
        
    Returns:
        List of validation errors, empty if valid
    """
    errors = []
    
    # Check top-level required fields
    required_fields = ["document", "metadata", "validation", "raw_corpus"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required top-level field: {field}")
    
    # If any top-level fields are missing, we can't validate further
    if errors:
        return errors
    
    # Check document structure
    if "id" not in data["document"]:
        errors.append("Missing required field: document.id")
        
    if "pages" not in data["document"]:
        errors.append("Missing required field: document.pages")
    elif not isinstance(data["document"]["pages"], list):
        errors.append("Field document.pages must be an array")
    else:
        # Check page structure
        for i, page in enumerate(data["document"]["pages"]):
            if "blocks" not in page:
                errors.append(f"Missing required field: document.pages[{i}].blocks")
            elif not isinstance(page["blocks"], list):
                errors.append(f"Field document.pages[{i}].blocks must be an array")
            else:
                # Check block structure
                for j, block in enumerate(page["blocks"]):
                    if "type" not in block:
                        errors.append(f"Missing required field: document.pages[{i}].blocks[{j}].type")
                    if "text" not in block:
                        errors.append(f"Missing required field: document.pages[{i}].blocks[{j}].text")
    
    # Check validation structure
    if "corpus_validation" not in data["validation"]:
        errors.append("Missing required field: validation.corpus_validation")
    else:
        validation = data["validation"]["corpus_validation"]
        if "performed" not in validation:
            errors.append("Missing required field: validation.corpus_validation.performed")
    
    # Check raw_corpus structure
    if "full_text" not in data["raw_corpus"]:
        errors.append("Missing required field: raw_corpus.full_text")
    
    if "pages" not in data["raw_corpus"]:
        errors.append("Missing required field: raw_corpus.pages")
    elif not isinstance(data["raw_corpus"]["pages"], list):
        errors.append("Field raw_corpus.pages must be an array")
    else:
        # Check page structure
        for i, page in enumerate(data["raw_corpus"]["pages"]):
            if "page_num" not in page:
                errors.append(f"Missing required field: raw_corpus.pages[{i}].page_num")
            if "text" not in page:
                errors.append(f"Missing required field: raw_corpus.pages[{i}].text")
    
    if "total_pages" not in data["raw_corpus"]:
        errors.append("Missing required field: raw_corpus.total_pages")
    
    return errors


def create_test_document() -> Dict[str, Any]:
    """Create a test document with the expected structure.
    
    Returns:
        Dictionary with expected ArangoDB JSON structure
    """
    return {
        "document": {
            "id": f"test_doc_{uuid.uuid4().hex[:8]}",
            "pages": [
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Test Section",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "This is test content."
                        }
                    ]
                }
            ]
        },
        "metadata": {
            "title": "Test Document",
            "processing_time": 0.1
        },
        "validation": {
            "corpus_validation": {
                "performed": True,
                "threshold": 97,
                "raw_corpus_length": 100
            }
        },
        "raw_corpus": {
            "full_text": "Test Section\n\nThis is test content.",
            "pages": [
                {
                    "page_num": 0,
                    "text": "Test Section\n\nThis is test content.",
                    "tables": []
                }
            ],
            "total_pages": 1
        }
    }


def convert_pdf_to_arangodb_json(pdf_path: Path) -> Optional[Dict[str, Any]]:
    """Convert a PDF to ArangoDB JSON format.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with ArangoDB JSON or None if conversion failed
    """
    try:
        # Create config
        config = ParserConfig({})
        config_dict = config.generate_config_dict()
        
        # Add start time for processing time calculation
        start_time = time.time()
        
        # Create converter with ArangoDBRenderer
        converter = PdfConverter(
            config=config_dict,
            renderer="marker.renderers.arangodb_json.ArangoDBRenderer"
        )
        
        # Set start time for processing time calculation
        converter.start_time = start_time
        
        # Convert PDF
        logger.info(f"Converting PDF to ArangoDB JSON format: {pdf_path}")
        result = converter(pdf_path)
        
        # Convert result to dictionary
        if hasattr(result, "model_dump"):
            return result.model_dump()
        else:
            return json.loads(result)
            
    except Exception as e:
        logger.error(f"Error converting PDF: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("arangodb_renderer_validation.log", rotation="10 MB")
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Structure validation with test document
    total_tests += 1
    logger.info("Test 1: Structure validation with test document")
    test_doc = create_test_document()
    structure_errors = validate_arangodb_json_structure(test_doc)
    if structure_errors:
        failure_msg = f"Structure validation failed with {len(structure_errors)} errors: {structure_errors}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
    else:
        logger.success("Structure validation passed")
    
    # Get sample PDF path
    sample_dir = Path("data/input")
    if not sample_dir.exists():
        logger.error(f"Sample directory {sample_dir} not found.")
        all_validation_failures.append(f"Sample directory {sample_dir} not found")
    else:
        # Find sample PDFs
        pdf_files = list(sample_dir.glob("*.pdf"))
        if not pdf_files:
            logger.error(f"No PDF files found in {sample_dir}.")
            all_validation_failures.append(f"No PDF files found in {sample_dir}")
        else:
            # Test 2: Convert and validate real PDF
            total_tests += 1
            sample_pdf = pdf_files[0]
            logger.info(f"Test 2: Convert and validate real PDF: {sample_pdf}")
            
            result = convert_pdf_to_arangodb_json(sample_pdf)
            if result is None:
                failure_msg = f"PDF conversion failed for {sample_pdf}"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                # Get output directory and save result
                output_dir = Path("test_results/arangodb")
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"{sample_pdf.stem}_arangodb.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Saved output to {output_file}")
                
                # Validate structure
                structure_errors = validate_arangodb_json_structure(result)
                if structure_errors:
                    failure_msg = f"Structure validation failed for {sample_pdf} with {len(structure_errors)} errors: {structure_errors}"
                    all_validation_failures.append(failure_msg)
                    logger.error(failure_msg)
                else:
                    # Check if required content is present
                    if not result["document"]["pages"]:
                        failure_msg = f"No pages found in converted document"
                        all_validation_failures.append(failure_msg)
                        logger.error(failure_msg)
                    elif not result["raw_corpus"]["full_text"]:
                        failure_msg = f"No text content found in raw_corpus"
                        all_validation_failures.append(failure_msg)
                        logger.error(failure_msg)
                    else:
                        logger.success(f"PDF conversion and validation successful for {sample_pdf}")
                        
                        # Log some stats
                        block_count = sum(len(page["blocks"]) for page in result["document"]["pages"])
                        logger.info(f"Document statistics:")
                        logger.info(f"- Document ID: {result['document']['id']}")
                        logger.info(f"- Pages: {len(result['document']['pages'])}")
                        logger.info(f"- Blocks: {block_count}")
                        logger.info(f"- Raw Corpus Length: {len(result['raw_corpus']['full_text'])}")
                        
                        # Count blocks by type
                        block_types = {}
                        for page in result["document"]["pages"]:
                            for block in page["blocks"]:
                                block_type = block["type"]
                                block_types[block_type] = block_types.get(block_type, 0) + 1
                        
                        for block_type, count in block_types.items():
                            logger.info(f"- Block type '{block_type}': {count}")
    
    # Final validation result
    if all_validation_failures:
        logger.error(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            logger.error(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        logger.success(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        logger.info("ArangoDB JSON renderer is validated and ready for use")
        sys.exit(0)  # Exit with success code