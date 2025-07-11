"""
Module: minimal_table_test.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



import os
import sys
import time
from pathlib import Path

from marker.models import create_model_dict
from marker.config.table import TableConfig, PRESET_HIGH_ACCURACY
from marker.builders.document import DocumentBuilder
from marker.processors.enhanced_camelot import EnhancedTableProcessor
from marker.schema import BlockTypes

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        fpath = sys.argv[1]
    else:
        # Use default test PDF
        fpath = "data/input/2505.03335v2.pdf"
    
    # Set page range (start with only first few pages for faster testing)
    page_range = [0, 1, 2]
    
    # Create configuration
    config = {
        "page_range": page_range,
        "table": PRESET_HIGH_ACCURACY.model_dump(),
        "debug_pdf_images": True,
        "debug_layout_images": True,
        "debug_data_folder": os.path.join("test_results", Path(fpath).stem)
    }
    
    # Create models dictionary
    models = create_model_dict()
    
    # Start timing
    start = time.time()
    
    print(f"Running table extraction test on {fpath} with page range {page_range}")
    
    # Create document builder
    builder = DocumentBuilder(
        artifact_dict=models,
        config=config
    )
    
    # Build the document
    document = builder.build(fpath)
    
    # Create and run the enhanced table processor
    processor = EnhancedTableProcessor(
        detection_model=models.get("detection_model"),
        recognition_model=models.get("recognition_model"),
        table_rec_model=models.get("table_rec_model"),
        config=config
    )
    
    # Process the document
    processor(document)
    
    # Count tables in the document
    tables = []
    for page in document.pages:
        tables.extend(page.contained_blocks(document, (BlockTypes.Table,)))
    
    # Print results
    print(f"Found {len(tables)} tables in {len(document.pages)} pages")
    
    # Print information about each table
    for i, table in enumerate(tables):
        print(f"Table {i+1}:")
        print(f"  Page: {table.page_id}")
        print(f"  Position: {table.polygon.bbox}")
        
        # Get cells if available
        cells = table.contained_blocks(document, (BlockTypes.TableCell,))
        print(f"  Cells: {len(cells)}")
        
        # Check for extraction metadata
        if table.metadata:
            metadata_dict = {key: getattr(table.metadata, key, None) for key in dir(table.metadata) if not key.startswith('_')}
            for key, value in metadata_dict.items():
                if key not in ['llm_request_count', 'llm_error_count', 'llm_tokens_used']:
                    print(f"  {key}: {value}")
    
    print(f"Total processing time: {time.time() - start:.2f} seconds")

if __name__ == "__main__":
    main()