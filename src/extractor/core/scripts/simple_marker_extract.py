#!/usr/bin/env python3
"""
Simple marker extraction without LLM processors
"""

import sys
import json
from pathlib import Path

# Try marker imports with fallback
try:
    from marker.converters.pdf import PdfConverter
    from marker.config.parser import ConfigParser
    from marker.models import create_model_dict
    MARKER_AVAILABLE = True
except ImportError:
    # Fallback to extractor imports
    try:
        from extractor.core.converters.pdf import PdfConverter
        from extractor.core.config.parser import ConfigParser
        from extractor.core.models import create_model_dict
        MARKER_AVAILABLE = False
    except ImportError as e:
        print(f"ERROR: Could not import marker modules: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print("Usage: simple_marker_extract.py <pdf_path> <output_json>")
        sys.exit(1)
        
    pdf_path = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)
        
    print(f"Extracting {pdf_path} -> {output_json}")
    
    try:
        # Create minimal config
        config = {
            'disable_multiprocessing': True,
            'output_format': 'json',
            'disable_image_extraction': True,
            'disable_ocr': False,
            'paginate_output': False,
        }
        
        # Create models - let it auto-detect device
        print("Loading models...")
        models = create_model_dict()
        
        # Define minimal processors without LLM ones
        processors = [
            'text',
            'table', 
            'sectionheader',
            'list',
            'code',
            'blockquote',
            'footnote',
            'equation',
            'page_header',
            'debug'
        ]
        
        # Create converter
        print("Creating converter...")
        converter = PdfConverter(
            config=config,
            artifact_dict=models,
            processor_list=processors,
            renderer=None
        )
        
        # Convert PDF
        print("Converting PDF...")
        result, images, metadata = converter(str(pdf_path))
        
        # Save output
        output_data = {
            'blocks': result.blocks if hasattr(result, 'blocks') else [],
            'metadata': metadata
        }
        
        with open(output_json, 'w') as f:
            json.dump(output_data, f, indent=2)
            
        print(f"Success! Output saved to {output_json}")
        return 0
        
    except Exception as e:
        print(f"ERROR: Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())