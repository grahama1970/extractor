#!/usr/bin/env python3
"""
Module: test_original_marker.py
Description: Import and use the original marker-pdf from repos/marker directory

External Dependencies:
- None (uses system path manipulation)

Sample Input:
>>> pdf_path = "/path/to/document.pdf"

Expected Output:
>>> markdown_content, metadata = convert_pdf_to_markdown(pdf_path)
>>> print(f"Converted {len(markdown_content)} characters")
"Converted 12345 characters"

Example Usage:
>>> from test_original_marker import convert_pdf_to_markdown
>>> result, meta = convert_pdf_to_markdown("test.pdf")
"""

import sys
import os
from pathlib import Path

def setup_original_marker_import():
    """
    Set up the import path to use the original marker-pdf package.
    This must be called before any marker imports.
    """
    # Get the absolute path to the original marker directory
    original_marker_path = Path("/home/graham/workspace/experiments/extractor/repos/marker").resolve()
    
    # Remove any existing 'marker' or 'extractor' paths from sys.path
    # to avoid conflicts
    sys.path = [p for p in sys.path if 'marker' not in p and 'extractor' not in p]
    
    # Insert the original marker path at the beginning of sys.path
    # This ensures it takes precedence over any installed packages
    sys.path.insert(0, str(original_marker_path))
    
    # Also set PYTHONPATH environment variable for subprocesses
    os.environ['PYTHONPATH'] = str(original_marker_path)
    
    print(f"✅ Set up import path for original marker at: {original_marker_path}")
    print(f"📍 Current sys.path[0]: {sys.path[0]}")

def convert_pdf_to_markdown(pdf_path: str, output_dir: str = None) -> tuple[str, dict]:
    """
    Convert a PDF to markdown using the original marker-pdf package.
    
    Args:
        pdf_path: Path to the PDF file to convert
        output_dir: Optional output directory for the markdown file
        
    Returns:
        tuple: (markdown_content, metadata)
    """
    # Ensure we're using the original marker
    setup_original_marker_import()
    
    # Now import from the original marker
    try:
        # Import the conversion function from the original marker
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser
        from marker.output import text_from_rendered
        
        print("✅ Successfully imported from original marker-pdf")
        
        # Create configuration
        config = ConfigParser()
        
        # Create model dictionary
        model_dict = create_model_dict()
        
        # Initialize converter
        converter = PdfConverter(
            config=config.generate_config_dict(),
            artifact_dict=model_dict,
            processor_list=config.get_processors(),
            renderer=config.get_renderer()
        )
        
        # Convert the PDF
        rendered = converter(pdf_path)
        
        # Extract text and metadata
        markdown_text = text_from_rendered(rendered)
        metadata = rendered.metadata if hasattr(rendered, 'metadata') else {}
        
        # Optionally save to file
        if output_dir:
            output_path = Path(output_dir) / f"{Path(pdf_path).stem}.md"
            output_path.write_text(markdown_text)
            print(f"📝 Saved markdown to: {output_path}")
        
        return markdown_text, metadata
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Trying alternative import method...")
        
        # Alternative: Use the convert_single.py script directly
        return use_convert_single_script(pdf_path, output_dir)

def use_convert_single_script(pdf_path: str, output_dir: str = None) -> tuple[str, dict]:
    """
    Alternative method: Use the convert_single.py script from original marker.
    """
    setup_original_marker_import()
    
    # Change to the marker directory
    original_dir = os.getcwd()
    marker_dir = "/home/graham/workspace/experiments/extractor/repos/marker"
    
    try:
        os.chdir(marker_dir)
        
        # Import and use convert_single
        import convert_single
        
        # Prepare arguments
        class Args:
            def __init__(self):
                self.input_path = pdf_path
                self.output_dir = output_dir or "."
                self.output_format = "markdown"
                self.skip_extract_images = False
                self.flatten_pdf = False
                self.debug = False
                
        args = Args()
        
        # Run conversion
        output_path = convert_single.main(args)
        
        # Read the output
        if output_path:
            markdown_path = Path(output_path) / f"{Path(pdf_path).stem}.md"
            if markdown_path.exists():
                markdown_content = markdown_path.read_text()
                
                # Try to read metadata
                metadata_path = Path(output_path) / f"{Path(pdf_path).stem}_meta.json"
                metadata = {}
                if metadata_path.exists():
                    import json
                    metadata = json.loads(metadata_path.read_text())
                
                return markdown_content, metadata
        
        return "", {}
        
    finally:
        os.chdir(original_dir)

def compare_with_extractor(pdf_path: str):
    """
    Compare outputs between original marker and the renamed extractor package.
    """
    print("=" * 80)
    print("🔍 BASELINE TEST: Original Marker-PDF")
    print("=" * 80)
    
    # Test with original marker
    setup_original_marker_import()
    
    # Get output from original marker
    original_markdown, original_metadata = convert_pdf_to_markdown(
        pdf_path, 
        output_dir="/home/graham/workspace/experiments/extractor/marker_baseline_output"
    )
    
    print(f"\n📊 Original Marker Results:")
    print(f"   - Markdown length: {len(original_markdown)} characters")
    print(f"   - Metadata keys: {list(original_metadata.keys())}")
    print(f"   - First 500 chars:\n{original_markdown[:500]}...")
    
    # Now test with extractor (if you want to compare)
    print("\n" + "=" * 80)
    print("🔍 COMPARISON TEST: Extractor (Renamed Marker)")
    print("=" * 80)
    
    # Clear the import setup
    sys.path = [p for p in sys.path if 'marker' not in str(p)]
    
    try:
        # Import from the installed extractor package
        from extractor.converters.pdf import PdfConverter as ExtractorPdfConverter
        from extractor.models import create_model_dict as extractor_create_models
        from extractor.config.parser import ConfigParser as ExtractorConfigParser
        from extractor.output import text_from_rendered as extractor_text_from_rendered
        
        print("✅ Successfully imported from extractor package")
        
        # Similar conversion process but with extractor
        config = ExtractorConfigParser()
        model_dict = extractor_create_models()
        
        converter = ExtractorPdfConverter(
            config=config.generate_config_dict(),
            artifact_dict=model_dict,
            processor_list=config.get_processors(),
            renderer=config.get_renderer()
        )
        
        rendered = converter(pdf_path)
        extractor_markdown = extractor_text_from_rendered(rendered)
        
        print(f"\n📊 Extractor Results:")
        print(f"   - Markdown length: {len(extractor_markdown)} characters")
        print(f"   - First 500 chars:\n{extractor_markdown[:500]}...")
        
        # Compare
        print("\n" + "=" * 80)
        print("📊 COMPARISON SUMMARY")
        print("=" * 80)
        print(f"Original Marker length: {len(original_markdown)}")
        print(f"Extractor length: {len(extractor_markdown)}")
        print(f"Difference: {abs(len(original_markdown) - len(extractor_markdown))} characters")
        
        if original_markdown == extractor_markdown:
            print("✅ Outputs are IDENTICAL")
        else:
            print("⚠️  Outputs DIFFER")
            
    except ImportError as e:
        print(f"❌ Could not import extractor for comparison: {e}")

if __name__ == "__main__":
    # Example usage
    test_pdf = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    if os.path.exists(test_pdf):
        # Just convert with original marker
        print("Converting with original marker...")
        markdown, metadata = convert_pdf_to_markdown(test_pdf)
        print(f"\n✅ Conversion complete!")
        print(f"   - Length: {len(markdown)} characters")
        print(f"   - Metadata: {metadata}")
        
        # Or run full comparison
        # compare_with_extractor(test_pdf)
    else:
        print(f"❌ Test PDF not found: {test_pdf}")
        print("Please provide a valid PDF path")