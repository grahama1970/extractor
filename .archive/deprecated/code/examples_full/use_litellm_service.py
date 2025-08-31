"""
Module: use_litellm_service.py
Description: Large Language Model integration and management

External Dependencies:
- litellm: https://docs.litellm.ai/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Example demonstrating how to use the LiteLLM service with marker
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env files
load_dotenv()

# Import the cache initialization from the module
try:
    from marker.services.utils.litellm_cache import initialize_litellm_cache, test_litellm_cache
    CACHE_AVAILABLE = True
except ImportError:
    print("Warning: Couldn't import litellm_cache module")
    CACHE_AVAILABLE = False

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser


def convert_with_litellm(pdf_path, model="openai/gpt-4o-mini", explicit_service=True):
    """
    Convert a PDF to markdown using the LiteLLM service

    Args:
        pdf_path: Path to the PDF file to convert
        model: LiteLLM model to use in provider/model format (e.g., "openai/gpt-4o-mini", "vertex/gemini-pro-vision")
        explicit_service: Whether to explicitly specify LiteLLMService (True) or use it as the default (False)

    Returns:
        bool: True if conversion was successful, False otherwise
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return False
    
    # Get the API key from environment variable - crucial for the LiteLLM service to work
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY=your_api_key")
        return False
    
    # Get the output directory and filename
    name = Path(pdf_path).stem
    output_dir = f"conversion_results/{name}"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nConverting PDF with LiteLLM ({model}): {pdf_path}")
    
    # Setup configuration
    config = {
        "output_dir": output_dir,
        "output_format": "markdown",
        "use_llm": True,  # Enable LLM usage
        "litellm_api_key": api_key,  # Pass API key
        "litellm_model": model,  # Specify model in provider/model format
        "enable_cache": True,  # Enable caching to reduce API costs and improve performance
        "disable_image_extraction": False,  # Extract images
        "debug": True,  # Enable debug output for tracking the process
    }

    # If explicitly specifying the service, add it to the config
    if explicit_service:
        config["llm_service"] = "marker.services.litellm.LiteLLMService"  # Explicitly specify LiteLLM service
        print("Using explicitly specified LiteLLMService")
    else:
        print("Using LiteLLMService as the default service (no explicit specification)")
    
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
        # Perform the conversion
        rendered = converter(pdf_path)
        
        # Extract text and images from the rendered output
        text, _, images = text_from_rendered(rendered)
        
        # Save the markdown output
        output_path = os.path.join(output_dir, f"{name}.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"Successfully converted to Markdown: {output_path}")
        print(f"Number of images extracted: {len(images)}")
        return True
    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


def main():
    """
    Main function to demonstrate usage and validate functionality
    """
    # Track validation failures
    validation_failures = []
    total_tests = 0

    # Test 1: Check for API key
    total_tests += 1
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        validation_failures.append("API key not found in environment variables")
        print("✗ API key test failed: OPENAI_API_KEY environment variable not set")
        print("  Set it with: export OPENAI_API_KEY=your_api_key")
    else:
        print("✓ API key test passed: OPENAI_API_KEY environment variable is set")

    # Test 2: Initialize LiteLLM cache if available
    total_tests += 1
    if CACHE_AVAILABLE:
        try:
            print("\nInitializing LiteLLM cache...")
            initialize_litellm_cache()
            print("✓ Cache initialization test passed")
        except Exception as e:
            validation_failures.append(f"Cache initialization failed: {e}")
            print(f"✗ Cache initialization test failed: {e}")
    else:
        print("\nSkipping cache initialization (initialize_litellm_cache.py not found)")
        print("HINT: Run the initialize_litellm_cache.py script directly to test cache setup")
    
    # Test 2: Convert a PDF
    total_tests += 1
    
    # Check if a PDF path is provided as an argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Try to find a default sample PDF
        default_files = [
            "data/examples/markdown/multicolcnn/multicolcnn.pdf",
            "data/examples/markdown/switch_transformers/switch_trans.pdf",
            "data/examples/markdown/thinkpython/thinkpython.pdf",
        ]
        
        # Try to find one of the default files
        pdf_path = None
        for file_path in default_files:
            if os.path.exists(file_path):
                pdf_path = file_path
                break
        
        if pdf_path is None:
            validation_failures.append("No test PDF file found")
            print("✗ PDF test failed: No test PDF file found")
            print("  Usage: python use_litellm_service.py /path/to/your.pdf")
            
            # Final validation results
            print(f"\n❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
            for failure in validation_failures:
                print(f"  - {failure}")
            return 1
    
    # Try to convert the PDF using both explicit and default service methods
    if api_key:
        # Test with explicit service specification
        print("\nTest 3a: Using explicit LiteLLMService specification")
        total_tests += 1
        success_explicit = convert_with_litellm(pdf_path, explicit_service=True)
        if success_explicit:
            print("✓ PDF conversion with explicit LiteLLMService passed")
        else:
            validation_failures.append("PDF conversion with explicit LiteLLMService failed")
            print("✗ PDF conversion with explicit LiteLLMService failed")

        # Test using LiteLLMService as the default service
        print("\nTest 3b: Using LiteLLMService as default (no explicit specification)")
        total_tests += 1
        success_default = convert_with_litellm(pdf_path, explicit_service=False)
        if success_default:
            print("✓ PDF conversion with default LiteLLMService passed")
        else:
            validation_failures.append("PDF conversion with default LiteLLMService failed")
            print("✗ PDF conversion with default LiteLLMService failed")
    
    # Final validation results
    if validation_failures:
        print(f"\n❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
        for failure in validation_failures:
            print(f"  - {failure}")
        return 1
    else:
        print(f"\n✅ VALIDATION PASSED - All {total_tests} tests passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())