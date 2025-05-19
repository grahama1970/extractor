"""
Test script for enhanced Camelot table extraction.

This script tests the enhanced Camelot table extraction functionality in Marker.
"""

import os
import sys
import time
from pathlib import Path

from marker.config.table import TableConfig, PRESET_HIGH_ACCURACY
from marker.models import create_model_dict
from marker.converters.pdf import PdfConverter
from marker.output import save_output

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        fpath = sys.argv[1]
    else:
        # Use default test PDF
        fpath = "data/input/2505.03335v2.pdf"
    
    # Set page range (start with only first few pages for faster testing)
    page_range = [0, 1]
    
    # Create configuration
    config = {
        "page_range": page_range,
        "table": PRESET_HIGH_ACCURACY.model_dump(),
        "debug_json": True,
        "debug_layout_images": True,
        "debug_pdf_images": True,
        "debug_data_folder": os.path.join("test_results", Path(fpath).stem)
    }
    
    # Create models dictionary
    models = create_model_dict()
    
    # Start timing
    start = time.time()
    
    # Create the converter
    converter = PdfConverter(
        config=config,
        artifact_dict=models,
        renderer="marker.renderers.markdown.MarkdownRenderer",
        llm_service=None
    )
    
    print(f"Running conversion on {fpath} with page range {page_range}")
    
    # Run the conversion
    try:
        rendered = converter(fpath)
        
        # Save the output
        output_dir = os.path.join("test_results")
        os.makedirs(output_dir, exist_ok=True)
        output_file = f"{Path(fpath).stem}_pages_{page_range[0]}to{page_range[-1]}"
        save_output(rendered, output_dir, output_file)
        
        print(f"Saved output to {output_dir}")
        print(f"Total time: {time.time() - start:.2f} seconds")
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()