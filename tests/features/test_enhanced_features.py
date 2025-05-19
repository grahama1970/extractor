#!/usr/bin/env python3
"""
Test script to validate the enhanced features implementation on a sample PDF.
Tests:
- Camelot table extraction with lattice mode and custom line width
- Async batch image description 
- Tree-sitter code language detection
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import json

# Load environment variables from .env files
load_dotenv()

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser

# Import table-related modules to check Camelot availability
try:
    from marker.processors.table import CAMELOT_AVAILABLE
    if CAMELOT_AVAILABLE:
        import camelot
except ImportError:
    CAMELOT_AVAILABLE = False

# Check tree-sitter availability
try:
    from marker.services.utils.tree_sitter_utils import get_language_info
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

def test_enhanced_features(
    pdf_path="data/input/2505.03335v2.pdf",
    page_range="0-9",  # 0-based indexing, so this is pages 1-10
    model="openai/gpt-4o-mini",
    use_camelot=True,
    use_async_batch=True,
    use_tree_sitter=True,
    detail_level="standard",
    camelot_line_width=15
):
    """
    Test the enhanced features implementation on a sample PDF.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return False
    
    # Create output directory
    output_dir = "test_results"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nTesting enhanced features on: {pdf_path}")
    print(f"Pages: {page_range}")
    print(f"Using LiteLLM model: {model}")
    
    # Setup configuration 
    config = {
        "output_dir": output_dir,
        "output_format": "markdown",
        "use_llm": True,
        "litellm_model": model,
        "disable_image_extraction": False,
        "disable_tqdm": False,
        "debug": True,
        "page_range": page_range,
        
        # Config for camelot table extraction (only if available)
        "use_camelot_fallback": use_camelot and CAMELOT_AVAILABLE,
        "camelot_min_cell_threshold": 4,
        "camelot_flavor": "lattice",
        "camelot_line_width": camelot_line_width,  # Custom line width for camelot
        
        # Config for async image description
        "use_async_batch": use_async_batch,
        "max_batch_size": 5,
        "detail_level": detail_level,
        
        # Config for tree-sitter code language detection
        "use_tree_sitter": use_tree_sitter and TREE_SITTER_AVAILABLE,
    }
    
    # Create configuration parser
    config_parser = ConfigParser(config)
    
    # Create the converter with configuration
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Record table metrics if Camelot is used
    table_metrics = []
    
    # Convert the PDF
    try:
        print("\nStarting conversion process...")
        start_time = time.time()
        
        # Perform the conversion
        rendered = converter(pdf_path)
        
        # Extract text and images from the rendered output
        text_content, _, images = text_from_rendered(rendered)
        
        end_time = time.time()
        conversion_time = end_time - start_time
        
        # Save the markdown output
        name = Path(pdf_path).stem
        output_path = os.path.join(output_dir, f"{name}_pages_{page_range.replace('-', 'to')}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        
        # Get metadata about the document
        metadata = {
            "filename": os.path.basename(pdf_path),
            "page_range": page_range,
            "conversion_time": f"{conversion_time:.2f} seconds",
            "num_images": len(images),
            "output_path": output_path,
            "features_used": {
                "camelot_table_extraction": use_camelot and CAMELOT_AVAILABLE,
                "async_batch_image_description": use_async_batch,
                "tree_sitter_code_detection": use_tree_sitter and TREE_SITTER_AVAILABLE,
            },
            "table_metrics": table_metrics
        }
        
        # If Camelot is available and was used, try to extract tables directly with Camelot for metrics
        if CAMELOT_AVAILABLE and use_camelot:
            try:
                print("\nExtracting table metrics with Camelot...")
                # Convert the page range string to actual page numbers for Camelot (1-indexed)
                pages = []
                for part in page_range.split(','):
                    if '-' in part:
                        start, end = part.split('-')
                        # Add 1 because Camelot is 1-indexed (our page_range is 0-indexed)
                        pages.extend([str(i+1) for i in range(int(start), int(end)+1)])
                    else:
                        # Add 1 because Camelot is 1-indexed
                        pages.append(str(int(part)+1))
                
                pages_str = ','.join(pages)
                tables = camelot.read_pdf(
                    pdf_path,
                    pages=pages_str,
                    flavor='lattice',
                    line_scale=camelot_line_width
                )
                
                print(f"Found {len(tables)} tables with Camelot")
                
                # Record metrics for each table
                for i, table in enumerate(tables):
                    table_data = {
                        "table_number": i+1,
                        "page": table.page,
                        "accuracy": f"{table.parsing_report['accuracy']:.2f}%",
                        "whitespace": f"{table.parsing_report['whitespace']:.2f}%",
                        "num_rows": len(table.df),
                        "num_cols": len(table.df.columns) if not table.df.empty else 0
                    }
                    table_metrics.append(table_data)
            except Exception as e:
                print(f"Error extracting table metrics with Camelot: {e}")
        
        # Save metadata to JSON
        metadata_path = os.path.join(output_dir, f"{name}_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\nSuccessfully converted to Markdown: {output_path}")
        print(f"Metadata saved to: {metadata_path}")
        print(f"Number of images extracted: {len(images)}")
        print(f"Conversion time: {conversion_time:.2f} seconds")
        
        # Print which enhanced features were used
        print("\nEnhanced Features Used:")
        print(f"- Camelot Table Extraction: {'Enabled' if use_camelot and CAMELOT_AVAILABLE else 'Disabled'}")
        if not CAMELOT_AVAILABLE and use_camelot:
            print("  (Camelot is not available. Install with: pip install camelot-py opencv-python-headless ghostscript)")
            
        print(f"- Async Batch Image Description: {'Enabled' if use_async_batch else 'Disabled'}")
        print(f"- Tree-sitter Code Language Detection: {'Enabled' if use_tree_sitter and TREE_SITTER_AVAILABLE else 'Disabled'}")
        print(f"- Image Description Detail Level: {detail_level}")
        
        # Report table metrics if available
        if table_metrics:
            print("\nTable Metrics:")
            for i, metrics in enumerate(table_metrics):
                print(f"  Table {i+1} (Page {metrics['page']}):")
                print(f"    - Accuracy: {metrics['accuracy']}")
                print(f"    - Whitespace: {metrics['whitespace']}")
                print(f"    - Size: {metrics['num_rows']} rows × {metrics['num_cols']} columns")
        
        return True
    
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to run the test"""
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "data/input/2505.03335v2.pdf"
    
    if len(sys.argv) > 2:
        page_range = sys.argv[2]
    else:
        page_range = "0-9"  # Pages 1-10 in 0-based indexing
    
    if len(sys.argv) > 3:
        model = sys.argv[3]
    else:
        model = "openai/gpt-4o-mini"
    
    # Display feature availability
    print("\nFeature Availability:")
    print(f"- Camelot: {'Available' if CAMELOT_AVAILABLE else 'Not Available'}")
    print(f"- Tree-sitter: {'Available' if TREE_SITTER_AVAILABLE else 'Not Available'}")
    
    if TREE_SITTER_AVAILABLE:
        try:
            language_info = get_language_info()
            num_languages = len(language_info)
            print(f"  - {num_languages} languages supported for code detection")
        except Exception as e:
            print(f"  - Error getting language info: {e}")
    
    # Run the test
    result = test_enhanced_features(
        pdf_path=pdf_path,
        page_range=page_range,
        model=model,
        use_camelot=True,
        use_async_batch=True,
        use_tree_sitter=True,
        detail_level="standard",
        camelot_line_width=15
    )
    
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main())