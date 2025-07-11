"""
Module: extract_table_driver.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import os
import sys
import time
import json
from pathlib import Path

# No need for PyMuPDF

from marker.models import create_model_dict
from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.builders.structure import StructureBuilder
from marker.providers.pdf import PdfProvider
from marker.processors.table import TableProcessor
from marker.processors.enhanced_camelot import EnhancedTableProcessor
from marker.config.table import TableConfig, PRESET_HIGH_ACCURACY, PRESET_PERFORMANCE, PRESET_BALANCED
from marker.schema import BlockTypes
from marker.schema.document import Document


def build_document(filepath, config):
    """Build a document from a PDF file."""
    # Create models
    models = create_model_dict()
    
    # Create provider
    # Filter config for provider attributes
    provider_config = {}
    for k, v in config.items():
        if hasattr(PdfProvider, k) and k != 'page_range':
            provider_config[k] = v
    
    provider = PdfProvider(
        filepath=filepath,
        **provider_config
    )
    
    # Create builders
    layout_builder = LayoutBuilder(
        layout_model=models.get("layout_model"),
        detection_model=models.get("detection_model"),
        recognition_model=models.get("recognition_model"),
        **{k: v for k, v in config.items() if hasattr(LayoutBuilder, k)}
    )
    
    line_builder = LineBuilder(
        **{k: v for k, v in config.items() if hasattr(LineBuilder, k)}
    )
    
    ocr_builder = OcrBuilder(
        recognition_model=models.get("recognition_model"),
        **{k: v for k, v in config.items() if hasattr(OcrBuilder, k)}
    )
    
    structure_builder = StructureBuilder(
        **{k: v for k, v in config.items() if hasattr(StructureBuilder, k)}
    )
    
    # Create document
    document = Document(filepath=filepath, pages=[])
    
    # Fill document with provider
    provider.fill_document(document)
    
    # Limit to first 3 pages for testing
    if len(document.pages) > 3:
        document.pages = document.pages[:3]
    
    # Process document with builders
    layout_builder(document, provider)
    line_builder(document, provider)
    ocr_builder(document, provider)
    structure_builder(document)
    
    return document, models


def process_with_processors(document, models, config):
    """Process a document with both standard and enhanced table processors."""
    # Create standard processor
    standard_processor = TableProcessor(
        detection_model=models.get("detection_model"),
        recognition_model=models.get("recognition_model"),
        table_rec_model=models.get("table_rec_model")
    )
    
    # Create enhanced processor
    enhanced_processor = EnhancedTableProcessor(
        detection_model=models.get("detection_model"),
        recognition_model=models.get("recognition_model"),
        table_rec_model=models.get("table_rec_model"),
        config=config
    )
    
    # Create copies of the document
    standard_doc = Document(
        filepath=document.filepath,
        pages=document.pages.copy()
    )
    
    enhanced_doc = Document(
        filepath=document.filepath,
        pages=document.pages.copy()
    )
    
    # Process with standard processor
    print("Processing with standard processor...")
    standard_start = time.time()
    standard_processor(standard_doc)
    standard_time = time.time() - standard_start
    
    # Process with enhanced processor
    print("Processing with enhanced processor...")
    enhanced_start = time.time()
    enhanced_processor(enhanced_doc)
    enhanced_time = time.time() - enhanced_start
    
    # Return results
    return {
        "standard": {
            "document": standard_doc,
            "time": standard_time
        },
        "enhanced": {
            "document": enhanced_doc,
            "time": enhanced_time
        }
    }


def count_tables(document):
    """Count tables in a document."""
    tables = []
    for page in document.pages:
        tables.extend(page.contained_blocks(document, (BlockTypes.Table,)))
    return tables


def print_table_info(tables, document, prefix=""):
    """Print information about tables."""
    print(f"{prefix}Found {len(tables)} tables")
    
    for i, table in enumerate(tables):
        print(f"{prefix}Table {i+1}:")
        print(f"{prefix}  Page: {table.page_id}")
        print(f"{prefix}  Position: {table.polygon.bbox}")
        
        # Get cells
        cells = table.contained_blocks(document, (BlockTypes.TableCell,))
        print(f"{prefix}  Cells: {len(cells)}")
        
        # Get metadata if available
        if table.metadata:
            metadata_dict = {key: getattr(table.metadata, key, None) for key in dir(table.metadata) 
                            if not key.startswith('_') and not callable(getattr(table.metadata, key))}
            print(f"{prefix}  Metadata:")
            for key, value in metadata_dict.items():
                if key not in ['llm_request_count', 'llm_error_count', 'llm_tokens_used']:
                    print(f"{prefix}    {key}: {value}")


def main():
    """Main function."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = "data/input/2505.03335v2.pdf"
    
    # Get preset from args if available
    preset_name = "high_accuracy"
    if len(sys.argv) > 2:
        preset_name = sys.argv[2]
    
    # Select preset
    preset_map = {
        "high_accuracy": PRESET_HIGH_ACCURACY,
        "performance": PRESET_PERFORMANCE,
        "balanced": PRESET_BALANCED
    }
    preset = preset_map.get(preset_name, PRESET_HIGH_ACCURACY)
    
    # Create configuration
    config = {
        "page_range": [0, 1, 2],  # First 3 pages
        "table": preset.model_dump(),
        "debug_layout_images": True,
        "debug_pdf_images": True,
        "debug_data_folder": os.path.join("test_results", Path(filepath).stem)
    }
    
    print(f"Testing table extraction on {filepath} with {preset_name} preset")
    print("-" * 80)
    
    # Build document
    print("Building document...")
    document, models = build_document(filepath, config)
    
    # Process document
    print("Processing document...")
    results = process_with_processors(document, models, config)
    
    # Compare results
    print("-" * 80)
    print("Results:")
    
    standard_tables = count_tables(results["standard"]["document"])
    enhanced_tables = count_tables(results["enhanced"]["document"])
    
    print(f"Standard processor: {len(standard_tables)} tables in {results['standard']['time']:.2f} seconds")
    print(f"Enhanced processor: {len(enhanced_tables)} tables in {results['enhanced']['time']:.2f} seconds")
    
    print("-" * 80)
    print("Standard Tables:")
    print_table_info(standard_tables, results["standard"]["document"], "  ")
    
    print("-" * 80)
    print("Enhanced Tables:")
    print_table_info(enhanced_tables, results["enhanced"]["document"], "  ")


if __name__ == "__main__":
    main()