#!/usr/bin/env python3
"""
Command-line script to run the LiteLLM PDF conversion test
"""

import os
import sys
import argparse
import traceback
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import required modules directly
from marker.config.parser import ConfigParser
from test_pdf_conversion import convert_pdf_with_litellm
from marker.services.utils.log_utils import log_api_request, log_api_response, log_api_error
from marker.services.utils.json_utils import clean_json_string


def main():
    """Parse arguments and run the test."""
    parser = argparse.ArgumentParser(description="Test LiteLLM PDF conversion")
    parser.add_argument(
        "--pdf", 
        default="data/input/2505.03335v2.pdf",
        help="Path to the PDF file to convert"
    )
    parser.add_argument(
        "--pages", 
        default="0-5",
        help="Page range to convert (e.g., '0-5')"
    )
    parser.add_argument(
        "--model", 
        default="openai/gpt-4o-mini",
        help="LiteLLM model to use (e.g., 'openai/gpt-4o-mini')"
    )
    parser.add_argument(
        "--output-dir", 
        default="data/output",
        help="Directory to save output"
    )
    
    args = parser.parse_args()
    
    # Check if API key is set
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY=your_api_key")
        sys.exit(1)
    
    # Print test parameters
    print(f"Running LiteLLM PDF conversion test...")
    print(f"PDF: {args.pdf}")
    print(f"Page range: {args.pages}")
    print(f"Model: {args.model}")
    print(f"Output directory: {args.output_dir}")

    try:
        # Run the test with the given parameters
        success = convert_pdf_with_litellm(
            pdf_path=args.pdf,
            output_dir=args.output_dir,
            page_range=args.pages,
            model=args.model
        )
        
        if success:
            print("\nTest passed! PDF was successfully converted.")
            print(f"Check the output file in {args.output_dir}/ directory.")
            sys.exit(0)
        else:
            print("\nTest failed - conversion did not complete successfully.")
            sys.exit(1)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()