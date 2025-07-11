#!/usr/bin/env python3
"""
Module: use_original_marker_simple.py
Description: Simple wrapper to use original marker's convert_single.py

External Dependencies:
- None (uses subprocess to avoid import conflicts)

Sample Input:
>>> pdf_path = "/path/to/document.pdf"

Expected Output:
>>> output_path = convert_with_original_marker(pdf_path)
>>> print(f"Converted to: {output_path}")
"Converted to: /path/to/output/document.md"

Example Usage:
>>> from use_original_marker_simple import convert_with_original_marker
>>> result = convert_with_original_marker("test.pdf", "/tmp/output")
"""

import subprocess
import sys
import os
from pathlib import Path
import json

def convert_with_original_marker(pdf_path: str, output_dir: str = None) -> str:
    """
    Convert PDF using the original marker's convert_single.py script.
    This avoids all import conflicts by running in a subprocess.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Output directory (defaults to current directory)
        
    Returns:
        str: Path to the output markdown file
    """
    marker_dir = "/home/graham/workspace/experiments/extractor/repos/marker"
    convert_script = os.path.join(marker_dir, "convert_single.py")
    
    if not os.path.exists(convert_script):
        raise FileNotFoundError(f"convert_single.py not found at {convert_script}")
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Prepare output directory
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), "marker_baseline_output")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the conversion in a subprocess with clean environment
    env = os.environ.copy()
    env['PYTHONPATH'] = marker_dir  # Ensure it uses the local marker package
    
    cmd = [
        sys.executable,  # Use the same Python interpreter
        convert_script,
        pdf_path,
        output_dir,
        "--output_format", "markdown"
    ]
    
    print(f"🚀 Running: {' '.join(cmd)}")
    print(f"📁 Working directory: {marker_dir}")
    
    try:
        # Run the command
        result = subprocess.run(
            cmd,
            cwd=marker_dir,  # Run from marker directory
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Conversion successful!")
        if result.stdout:
            print(f"📝 Output: {result.stdout}")
        
        # Find the output file
        pdf_name = Path(pdf_path).stem
        markdown_path = Path(output_dir) / f"{pdf_name}.md"
        
        if markdown_path.exists():
            print(f"✅ Markdown saved to: {markdown_path}")
            return str(markdown_path)
        else:
            print("⚠️  Markdown file not found at expected location")
            return ""
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Conversion failed with exit code {e.returncode}")
        print(f"❌ Error output: {e.stderr}")
        raise

def read_conversion_results(markdown_path: str) -> dict:
    """
    Read the conversion results including markdown and metadata.
    
    Args:
        markdown_path: Path to the markdown file
        
    Returns:
        dict: Contains 'markdown' and 'metadata' keys
    """
    markdown_path = Path(markdown_path)
    
    results = {
        'markdown': '',
        'metadata': {},
        'images': []
    }
    
    # Read markdown
    if markdown_path.exists():
        results['markdown'] = markdown_path.read_text()
    
    # Read metadata (if exists)
    meta_path = markdown_path.parent / f"{markdown_path.stem}_meta.json"
    if meta_path.exists():
        results['metadata'] = json.loads(meta_path.read_text())
    
    # Check for images
    parent_dir = markdown_path.parent
    image_pattern = f"{markdown_path.stem}_*.{'{png,jpg,jpeg}'}"
    results['images'] = list(parent_dir.glob(image_pattern))
    
    return results

def compare_extraction_methods(pdf_path: str):
    """
    Compare original marker with extractor on the same PDF.
    """
    print("=" * 80)
    print("🔬 EXTRACTION COMPARISON TEST")
    print("=" * 80)
    
    # Test 1: Original Marker
    print("\n1️⃣ Testing Original Marker...")
    original_output = convert_with_original_marker(
        pdf_path, 
        "/home/graham/workspace/experiments/extractor/baseline_test/baseline_output"
    )
    original_results = read_conversion_results(original_output)
    
    print(f"\n📊 Original Marker Results:")
    print(f"   - Markdown length: {len(original_results['markdown'])} characters")
    print(f"   - Images found: {len(original_results['images'])}")
    print(f"   - Metadata keys: {list(original_results['metadata'].keys())}")
    
    # Test 2: Extractor (using Python import)
    print("\n2️⃣ Testing Extractor Package...")
    try:
        # Import extractor modules
        from extractor.converters.pdf import PdfConverter
        from extractor.models import create_model_dict
        from extractor.config.parser import ConfigParser
        from extractor.output import save_output
        
        # Convert with extractor
        config_parser = ConfigParser()
        models = create_model_dict()
        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=models,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer()
        )
        
        rendered = converter(pdf_path)
        
        # Save output
        extractor_output_dir = "/home/graham/workspace/experiments/extractor/baseline_test/extractor_output"
        os.makedirs(extractor_output_dir, exist_ok=True)
        save_output(rendered, extractor_output_dir)
        
        # Read results
        extractor_markdown_path = Path(extractor_output_dir) / f"{Path(pdf_path).stem}.md"
        extractor_results = read_conversion_results(str(extractor_markdown_path))
        
        print(f"\n📊 Extractor Results:")
        print(f"   - Markdown length: {len(extractor_results['markdown'])} characters")
        print(f"   - Images found: {len(extractor_results['images'])}")
        
        # Compare
        print("\n" + "=" * 80)
        print("📊 COMPARISON RESULTS")
        print("=" * 80)
        
        len_diff = abs(len(original_results['markdown']) - len(extractor_results['markdown']))
        len_ratio = len(extractor_results['markdown']) / len(original_results['markdown']) if len(original_results['markdown']) > 0 else 0
        
        print(f"Original Marker: {len(original_results['markdown'])} chars")
        print(f"Extractor:       {len(extractor_results['markdown'])} chars")
        print(f"Difference:      {len_diff} chars ({len_ratio:.2%} of original)")
        print(f"Images:          Original={len(original_results['images'])}, Extractor={len(extractor_results['images'])}")
        
        if len_diff == 0:
            print("\n✅ Outputs are IDENTICAL in length!")
        elif len_diff < 100:
            print("\n✅ Outputs are very similar (< 100 char difference)")
        else:
            print(f"\n⚠️  Significant difference detected: {len_diff} characters")
            
            # Show first difference
            for i, (c1, c2) in enumerate(zip(original_results['markdown'], extractor_results['markdown'])):
                if c1 != c2:
                    start = max(0, i - 50)
                    end = min(len(original_results['markdown']), i + 50)
                    print(f"\nFirst difference at position {i}:")
                    print(f"Original: ...{original_results['markdown'][start:end]}...")
                    print(f"Extractor: ...{extractor_results['markdown'][start:end]}...")
                    break
                    
    except Exception as e:
        print(f"❌ Error testing extractor: {e}")

if __name__ == "__main__":
    # Test with a sample PDF
    test_pdf = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    if os.path.exists(test_pdf):
        # Simple conversion
        print("🚀 Converting PDF with original marker...")
        output_path = convert_with_original_marker(test_pdf)
        
        # Read and display results
        results = read_conversion_results(output_path)
        print(f"\n📄 Markdown preview (first 1000 chars):")
        print("-" * 80)
        print(results['markdown'][:1000])
        print("-" * 80)
        
        # Uncomment to run comparison
        # compare_extraction_methods(test_pdf)
    else:
        print(f"❌ Test PDF not found: {test_pdf}")
        print("Please update the path to a valid PDF file")