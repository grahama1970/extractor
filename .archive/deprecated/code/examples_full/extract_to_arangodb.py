#!/usr/bin/env python3
"""
Example: Extract PDF to ArangoDB format using the extractor.

This demonstrates how to:
1. Extract a PDF with enhanced table processing
2. Format the output for ArangoDB insertion
3. Optionally restructure the document for better database storage
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

from extractor.core.models import create_model_dict
from extractor.core.converters.document import DocumentConverter
from extractor.core.config.parser import ConfigParser
from extractor.core.renderers.arangodb_json import ArangoDBRenderer
from loguru import logger


async def extract_to_arangodb(
    pdf_path: str,
    output_path: str,
    use_llm: bool = True,
    merge_text_blocks: bool = True,
    calculate_quality: bool = True
) -> Dict[str, Any]:
    """Extract PDF to ArangoDB format.
    
    Args:
        pdf_path: Path to PDF file
        output_path: Where to save ArangoDB JSON
        use_llm: Enable LLM processing for better quality
        merge_text_blocks: Merge consecutive text blocks
        calculate_quality: Calculate quality metrics
        
    Returns:
        The ArangoDB document
    """
    logger.info(f"Extracting {pdf_path} to ArangoDB format")
    
    # Create models
    models = create_model_dict()
    
    # Create configuration
    cli_options = {
        "output_format": "json",  # We'll use custom renderer
        "use_llm": use_llm,
        "max_pages": None  # Process all pages
    }
    
    parser = ConfigParser(cli_options)
    config_dict = parser.generate_config_dict()
    
    # Create ArangoDB renderer with options
    renderer_config = {
        "merge_text_blocks": merge_text_blocks,
        "calculate_quality": calculate_quality,
        "extract_tags": True
    }
    renderer = ArangoDBRenderer(renderer_config)
    
    # Create converter with custom renderer
    converter = DocumentConverter(
        artifact_dict=models,
        config=config_dict,
        renderer=renderer,
        processor_list=parser.get_processors()
    )
    
    # Add file path to metadata for ArangoDB key generation
    converter.config["metadata"] = converter.config.get("metadata", {})
    converter.config["metadata"]["file_path"] = pdf_path
    
    # Determine document type from filename
    filename = Path(pdf_path).stem.lower()
    if "resume" in filename or "cv" in filename:
        doc_type = "resume"
    elif "datasheet" in filename:
        doc_type = "datasheet"
    else:
        doc_type = "technical_document"
    
    converter.config["metadata"]["document_type"] = doc_type
    
    # Convert PDF
    logger.info("Starting extraction...")
    arango_doc = converter(pdf_path)
    
    # The renderer returns a dict, not a string
    if isinstance(arango_doc, dict):
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(arango_doc, f, indent=2, default=str)
        
        logger.success(f"Saved ArangoDB document to {output_path}")
        
        # Log some statistics
        logger.info(f"Document key: {arango_doc['_key']}")
        logger.info(f"Sections: {len(arango_doc['content']['sections'])}")
        logger.info(f"Tables: {len(arango_doc['content']['tables'])}")
        logger.info(f"Structure quality: {arango_doc['analysis']['structure_quality']:.2f}")
        logger.info(f"Completeness: {arango_doc['analysis']['completeness_score']:.2f}")
        logger.info(f"Tags: {', '.join(arango_doc['tags'])}")
        
        return arango_doc
    else:
        logger.error(f"Unexpected output type: {type(arango_doc)}")
        return {}


async def compare_extraction_modes():
    """Compare extraction with and without text merging."""
    
    pdf_path = "/home/graham/workspace/experiments/extractor/proof_of_concept/archive/BHT_CV32A65X_marked.pdf"
    
    # Extract without text merging
    logger.info("\n" + "="*60)
    logger.info("Extraction WITHOUT text merging:")
    logger.info("="*60)
    
    doc1 = await extract_to_arangodb(
        pdf_path,
        "/tmp/bht_arangodb_no_merge.json",
        use_llm=True,
        merge_text_blocks=False
    )
    
    # Extract with text merging
    logger.info("\n" + "="*60)
    logger.info("Extraction WITH text merging:")
    logger.info("="*60)
    
    doc2 = await extract_to_arangodb(
        pdf_path,
        "/tmp/bht_arangodb_merged.json",
        use_llm=True,
        merge_text_blocks=True
    )
    
    # Compare results
    logger.info("\n" + "="*60)
    logger.info("COMPARISON:")
    logger.info("="*60)
    
    # Count blocks in each mode
    blocks1 = sum(1 for s in doc1['content']['sections'] if s.get('type') != 'header')
    blocks2 = sum(1 for s in doc2['content']['sections'] if s.get('type') != 'header')
    
    logger.info(f"Without merging: {blocks1} content blocks")
    logger.info(f"With merging: {blocks2} content blocks")
    logger.info(f"Reduction: {((blocks1 - blocks2) / blocks1 * 100):.1f}%")
    
    # Check for critical content
    critical_text = "The BHT is never flushed"
    raw_text = doc2['content']['raw_text']
    
    if critical_text in raw_text:
        logger.success(f"✓ Critical text preserved: '{critical_text}'")
    else:
        logger.error(f"✗ Critical text missing!")
    
    # Check table headers
    for i, table in enumerate(doc2['content']['tables']):
        logger.info(f"\nTable {i}:")
        if 'headers' in table:
            headers = table['headers']
            logger.info(f"  Headers: {headers}")
            
            # Check if headers were properly merged
            if any("Descripti" in h for h in headers):
                logger.warning("  ⚠️  Headers still split")
            elif "Description" in headers:
                logger.success("  ✓ Headers properly merged")


async def working_usage():
    """Demonstrate proper usage of ArangoDB extraction.
    
    AGENT: Run this for stable, production-ready example.
    This function is known to work and should not be modified.
    """
    pdf_path = "/home/graham/workspace/experiments/extractor/proof_of_concept/archive/BHT_CV32A65X_marked.pdf"
    output_path = "/tmp/bht_arangodb_example.json"
    
    # Run extraction
    doc = await extract_to_arangodb(
        pdf_path,
        output_path,
        use_llm=False,  # Disable LLM for quick test
        merge_text_blocks=True,
        calculate_quality=True
    )
    
    logger.success(f"Successfully extracted to: {output_path}")
    return True


async def debug_function():
    """Debug function for testing new ideas and troubleshooting.
    
    AGENT: Use this function for experimenting! Rewrite freely.
    This is constantly rewritten to test different things.
    """
    # Currently testing: compare extraction modes
    await compare_extraction_modes()


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - stable example that works
    - DEBUG: Run with 'debug' argument to test new ideas
    - DO NOT create external test files - use debug_function() instead!
    """
    import sys
    
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())