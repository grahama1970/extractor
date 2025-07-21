"""
Module: enhanced_features.py
Description: Implementation of enhanced features functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Example demonstrating how to use the enhanced features of Marker:
- Camelot for table extraction fallback
- Async batch processing for image descriptions
- Tree-sitter for code language detection
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import time

# Load environment variables from .env files
load_dotenv()

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser
from marker.processors.table import TableProcessor, CAMELOT_AVAILABLE
from marker.processors.llm.llm_image_description import LLMImageDescriptionProcessor

# Check tree-sitter availability
try:
    from marker.services.utils.tree_sitter_utils import get_language_info
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

def convert_with_enhanced_features(
    pdf_path, 
    model="openai/gpt-4o-mini",
    use_camelot=True,
    use_async_batch=True,
    use_tree_sitter=True,
    detail_level="standard"
):
    """
    Convert a PDF to markdown using enhanced features
    
    Args:
        pdf_path: Path to the PDF file to convert
        model: LiteLLM model to use in provider/model format
        use_camelot: Whether to use Camelot for table extraction fallback
        use_async_batch: Whether to use async batch processing for image descriptions
        use_tree_sitter: Whether to use tree-sitter for code language detection
        detail_level: Level of detail for image descriptions: 'brief', 'standard', or 'detailed'
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return False
    
    # Get the output directory and filename
    name = Path(pdf_path).stem
    output_dir = f"conversion_results/{name}"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nConverting PDF with enhanced features: {pdf_path}")
    print(f"Using LiteLLM model: {model}")
    
    # Setup configuration 
    config = {
        "output_dir": output_dir,
        "output_format": "markdown",
        "use_llm": True,
        "litellm_model": model,
        "disable_image_extraction": False,
        "debug": True,
        
        # Config for camelot table extraction (only if available)
        "use_camelot_fallback": use_camelot and CAMELOT_AVAILABLE,
        "camelot_min_cell_threshold": 4,
        "camelot_flavor": "lattice",
        
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
    converter = DocumentConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Convert the PDF
    try:
        start_time = time.time()
        
        # Perform the conversion
        rendered = converter(pdf_path)
        
        # Extract text and images from the rendered output
        text, _, images = text_from_rendered(rendered)
        
        end_time = time.time()
        conversion_time = end_time - start_time
        
        # Save the markdown output
        output_path = os.path.join(output_dir, f"{name}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"Successfully converted to Markdown: {output_path}")
        print(f"Number of images extracted: {len(images)}")
        print(f"Conversion time: {conversion_time:.2f} seconds")
        
        # Print which enhanced features were used
        print("\nEnhanced Features Used:")
        print(f"- Camelot Table Extraction: {'Enabled' if use_camelot and CAMELOT_AVAILABLE else 'Disabled'}")
        if not CAMELOT_AVAILABLE and use_camelot:
            print("  (Camelot is not available. Install with: pip install camelot-py cv2-tools)")
            
        print(f"- Async Batch Image Description: {'Enabled' if use_async_batch else 'Disabled'}")
        print(f"- Tree-sitter Code Language Detection: {'Enabled' if use_tree_sitter and TREE_SITTER_AVAILABLE else 'Disabled'}")
        if not TREE_SITTER_AVAILABLE and use_tree_sitter:
            print("  (Tree-sitter is not available. Marker is using tree-sitter-language-pack.)")
            
        print(f"- Image Description Detail Level: {detail_level}")
        
        return True
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False

def main():
    """Main function to demonstrate usage"""
    # Check if a PDF path is provided as an argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        # You can provide additional parameters if desired
        model = sys.argv[2] if len(sys.argv) > 2 else "openai/gpt-4o-mini"
    else:
        # Try to find a default sample PDF
        default_files = [
            "data/input/2505.03335v2.pdf",
            # Add more default files here
        ]
        
        # Try to find one of the default files
        pdf_path = None
        for file_path in default_files:
            if os.path.exists(file_path):
                pdf_path = file_path
                break
        
        if pdf_path is None:
            print("No test PDF file found")
            print("Usage: python enhanced_features.py /path/to/your.pdf [model]")
            return 1
        
        model = "openai/gpt-4o-mini"  # Default model
    
    # Display available language support with tree-sitter if available
    if TREE_SITTER_AVAILABLE:
        try:
            language_info = get_language_info()
            num_languages = len(language_info)
            print(f"\nTree-sitter support: {num_languages} languages available for code detection")
        except Exception:
            print("\nTree-sitter is available but couldn't retrieve language info")
    
    # Run the conversion with enhanced features
    result = convert_with_enhanced_features(
        pdf_path=pdf_path,
        model=model,
        use_camelot=True,
        use_async_batch=True,
        use_tree_sitter=True,
        detail_level="standard"
    )
    
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main())