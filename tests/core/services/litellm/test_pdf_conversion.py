#!/usr/bin/env python3
"""
Test the LiteLLM service by converting a PDF to markdown with page range

This test validates that the LiteLLM service can properly convert a PDF
with a specific page range setting.
"""

import os
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import required modules directly
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser
from marker.services.utils.litellm_cache import initialize_litellm_cache
from marker.services.utils.log_utils import log_api_request, log_api_response, log_api_error
from marker.services.utils.json_utils import clean_json_string


def convert_pdf_with_litellm(
        pdf_path="data/input/2505.03335v2.pdf",
        output_dir="data/output",
        page_range="0-5",
        model="openai/gpt-4o-mini",
    ):
    """
    Test converting a PDF to markdown with LiteLLM service and page range.

    Args:
        pdf_path: Path to PDF file to convert
        output_dir: Directory to save output files
        page_range: Range of pages to convert, e.g. "0-5"
        model: LiteLLM model to use, in provider/model format

    Returns:
        bool: True if conversion was successful
    """

    # Check if PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return False

    # Check if API key is set
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY=your_api_key")
        return False

    # Initialize cache
    try:
        print("Initializing LiteLLM cache...")
        initialize_litellm_cache()
        print("Cache initialized")
    except Exception as e:
        print(f"Warning: Failed to initialize cache: {e}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get base filename without extension
    filename = Path(pdf_path).stem

    print(f"\nConverting PDF with LiteLLM")
    print(f"  PDF: {pdf_path}")
    print(f"  Page range: {page_range}")
    print(f"  Model: {model}")
    print(f"  Output directory: {output_dir}")

    try:
        # Setup configuration
        config = {
            "output_dir": output_dir,
            "output_format": "markdown",
            "use_llm": True,  # Enable LLM usage
            "llm_service": "marker.services.litellm.LiteLLMService",  # Specify LiteLLM service
            "litellm_api_key": api_key,  # Specify API key
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
        print("\nStarting conversion...")
        rendered = converter(pdf_path)

        # Extract text and images
        text, metadata, images = text_from_rendered(rendered)

        # Save the markdown output
        output_path = os.path.join(output_dir, f"{filename}_litellm_test.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        # Verify the results
        if not text or len(text) < 100:
            print("Error: Converted text is too short or empty")
            return False

        print(f"\nConversion successful!")
        print(f"Output saved to: {output_path}")
        print(f"Pages processed: {page_range}")
        print(f"Number of images extracted: {len(images)}")

        return True
    except Exception as e:
        print(f"\nError during conversion: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    """Run the test directly when the script is executed."""
    success = convert_pdf_with_litellm()
    sys.exit(0 if success else 1)