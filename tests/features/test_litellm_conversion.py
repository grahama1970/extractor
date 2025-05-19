#!/usr/bin/env python3
"""
Test script to convert a PDF to markdown using LiteLLM service
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser


def convert_pdf_with_litellm(
    pdf_path="data/input/2505.03335v2.pdf",
    output_dir="data/output",
    page_range="0-5",
    model="openai/gpt-4o-mini"
):
    """
    Convert a PDF to markdown using LiteLLM with specified page range
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save output
        page_range: Range of pages to convert (e.g., "0-5")
        model: LiteLLM model to use
    
    Returns:
        bool: True if conversion was successful
    """
    # Ensure PDF file exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get base filename without extension
    filename = Path(pdf_path).stem
    
    print(f"\nConverting PDF with LiteLLM: {pdf_path}")
    print(f"Page range: {page_range}")
    print(f"Using model: {model}")
    
    # Setup configuration
    config = {
        "output_dir": output_dir,
        "output_format": "markdown",
        "use_llm": True,  # Enable LLM usage
        "llm_service": "marker.services.litellm.LiteLLMService",  # Specify LiteLLM service
        "litellm_model": model,  # Specify model
        "enable_cache": True,  # Enable caching
        "page_range": page_range,  # Set page range
        "debug": True,  # Enable debug output
    }
    
    # Create configuration parser
    config_parser = ConfigParser(config)
    
    # Get the final config including any default values
    full_config = config_parser.generate_config_dict()
    
    # Create the converter
    converter = PdfConverter(
        config=full_config,
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Convert the PDF
    try:
        print("\nStarting conversion...")
        rendered = converter(pdf_path)
        
        # Extract text and images
        text, metadata, images = text_from_rendered(rendered)
        
        # Save the markdown output
        output_path = os.path.join(output_dir, f"{filename}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"\nConversion successful!")
        print(f"Output saved to: {output_path}")
        print(f"Pages processed: {page_range}")
        print(f"Number of images extracted: {len(images)}")
        
        return True
    except Exception as e:
        print(f"\nError during conversion: {e}")
        return False


if __name__ == "__main__":
    # Get API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY=your_api_key")
        sys.exit(1)
    
    # If first argument is provided, use it as PDF path
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/input/2505.03335v2.pdf"
    
    # Convert the PDF
    success = convert_pdf_with_litellm(pdf_path=pdf_path)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)