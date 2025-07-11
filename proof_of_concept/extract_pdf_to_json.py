#!/usr/bin/env python3
"""
Simple PDF to JSON Extraction - Proof of Concept

This script demonstrates extracting a PDF to structured JSON using the extractor module.
It uses the unified extractor which provides the best structured output.
"""

import os
import sys
import json
from pathlib import Path

# Setup environment variables
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

# Add the extractor src to Python path
extractor_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(extractor_src))

# Import the unified extractor
from extractor.unified_extractor_v2 import extract_to_unified_json


def extract_pdf(pdf_path: str, output_path: str = None):
    """
    Extract a PDF file to structured JSON.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Optional path for JSON output (defaults to same name as PDF)
    
    Returns:
        The extracted data as a dictionary
    """
    print(f"📄 Extracting PDF: {pdf_path}")
    print("⏳ This may take a moment on first run as models are downloaded...")
    
    try:
        # Extract the PDF
        result = extract_to_unified_json(pdf_path)
        
        # Determine output path
        if output_path is None:
            output_path = str(Path(pdf_path).with_suffix('.json'))
        
        # Save the JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Print summary
        sections = result.get('vertices', {}).get('sections', [])
        entities = result.get('vertices', {}).get('entities', [])
        
        print(f"\n✅ Extraction complete!")
        print(f"📊 Summary:")
        print(f"   - Sections extracted: {len(sections)}")
        print(f"   - Entities found: {len(entities)}")
        print(f"   - Output saved to: {output_path}")
        
        # Show sample sections
        if sections:
            print(f"\n📑 Sample sections:")
            for i, section in enumerate(sections[:5]):
                level = section.get('level', 0)
                title = section.get('title', 'Untitled')
                indent = "  " * (level - 1)
                print(f"   {indent}[L{level}] {title[:60]}...")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function to run the extraction."""
    # Use the test PDF from the data directory
    test_pdf = Path(__file__).parent.parent / "data" / "input" / "2505.03335v2.pdf"
    
    # Check if test PDF exists, otherwise look for any PDF
    if not test_pdf.exists():
        print(f"⚠️  Test PDF not found at: {test_pdf}")
        print("🔍 Looking for other PDFs...")
        
        # Search for PDFs in parent directory
        pdf_files = list(Path(__file__).parent.parent.glob("**/*.pdf"))[:5]
        
        if pdf_files:
            test_pdf = pdf_files[0]
            print(f"📄 Found PDF: {test_pdf}")
        else:
            print("❌ No PDF files found. Please provide a PDF path as argument.")
            print(f"\nUsage: python {Path(__file__).name} [pdf_path]")
            return 1
    
    # Output path in the proof_of_concept directory
    output_json = Path(__file__).parent / "extracted_output.json"
    
    # Extract the PDF
    result = extract_pdf(str(test_pdf), str(output_json))
    
    if result:
        print(f"\n🎉 Success! Check the output at:")
        print(f"   {output_json}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    # Check for command line argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if Path(pdf_path).exists() and pdf_path.endswith('.pdf'):
            output_json = Path(__file__).parent / f"{Path(pdf_path).stem}_output.json"
            extract_pdf(pdf_path, str(output_json))
        else:
            print(f"❌ Invalid PDF path: {pdf_path}")
            sys.exit(1)
    else:
        # Run with default test PDF
        sys.exit(main())