#!/usr/bin/env python3
"""
Test script for LiteLLM integration with Marker
"""

import os
import sys
from pathlib import Path

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.services.litellm import LiteLLMService
from marker.config.parser import ConfigParser


def test_litellm_conversion(pdf_path):
    """
    Test PDF conversion with LiteLLM service
    
    Args:
        pdf_path: Path to the PDF file to convert
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    # Get the output directory and filename
    name = Path(pdf_path).stem
    output_dir = f"conversion_results/{name}"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nConverting PDF with LiteLLM: {pdf_path}")
    
    # Setup configuration
    config = {
        "output_dir": output_dir,
        "output_format": "markdown",
        "use_llm": True,
        "llm_service": "marker.services.litellm.LiteLLMService",
        "litellm_api_key": os.environ.get("OPENAI_API_KEY"),  # Use environment variable
        "litellm_model": "openai/gpt-4o-mini",  # Specify model in provider/model format
        "disable_image_extraction": False,  # Set to True to skip image extraction
        "debug": True,  # Enable debug output
    }
    
    config_parser = ConfigParser(config)
    
    # Create the converter with our configuration
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Convert the PDF
    try:
        rendered = converter(pdf_path)
        text, _, images = text_from_rendered(rendered)
        
        # Save the output
        output_path = os.path.join(output_dir, f"{name}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"Successfully converted to Markdown: {output_path}")
        print(f"Number of images extracted: {len(images)}")
        return True
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


if __name__ == "__main__":
    # Check if a PDF path is provided as an argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default PDF path - update this to a PDF in your system
        default_files = [
            "data/examples/markdown/multicolcnn/multicolcnn.pdf",
            "data/examples/markdown/switch_transformers/switch_trans.pdf",
            "data/examples/markdown/thinkpython/thinkpython.pdf"
        ]
        
        # Try to find one of the default files
        pdf_path = None
        for file_path in default_files:
            if os.path.exists(file_path):
                pdf_path = file_path
                break
                
        if pdf_path is None:
            print("Error: No PDF file specified and no default PDFs found.")
            print("Usage: python test_litellm.py /path/to/your.pdf")
            sys.exit(1)
    
    # Set API key from environment variable if not set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY environment variable not set.")
        print("Set it with: export OPENAI_API_KEY=your_api_key")
    
    # Run the test
    test_litellm_conversion(pdf_path)