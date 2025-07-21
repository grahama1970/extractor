#!/usr/bin/env python3
"""
Module: marker_extractor_comparison.py
Description: Complete solution for using original marker vs extractor

External Dependencies:
- subprocess: For isolated execution
- pathlib: For file operations

Sample Input:
>>> pdf_path = "/path/to/document.pdf"

Expected Output:
>>> original, extractor = compare_extractions(pdf_path)
>>> print(f"Original: {len(original)} chars, Extractor: {len(extractor)} chars")
"Original: 12345 chars, Extractor: 12456 chars"

Example Usage:
>>> from marker_extractor_comparison import compare_extractions
>>> orig, ext = compare_extractions("test.pdf")
"""

import sys
import os
import subprocess
import json
from pathlib import Path
import tempfile
from typing import Tuple, Dict, Any

# =============================================================================
# ORIGINAL MARKER FUNCTIONS
# =============================================================================

def use_original_marker_subprocess(pdf_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Use the original marker via subprocess to avoid ALL import conflicts.
    This is the MOST RELIABLE method.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Where to save the output (optional)
        
    Returns:
        dict: Contains 'markdown', 'metadata', and 'output_path' keys
    """
    marker_repo = "/home/graham/workspace/experiments/extractor/repos/marker"
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="original_marker_")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # Create a Python script that uses the original marker
    script_content = f"""
import sys
sys.path.insert(0, '{marker_repo}')
import os
os.chdir('{marker_repo}')

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import save_output

# Setup
config_parser = ConfigParser()
models = create_model_dict()

# Create converter
converter = PdfConverter(
    config=config_parser.generate_config_dict(),
    artifact_dict=models,
    processor_list=config_parser.get_processors(),
    renderer=config_parser.get_renderer()
)

# Convert
rendered = converter('{pdf_path}')

# Save
save_output(rendered, '{output_dir}')
print("Done")
"""
    
    # Write and execute script
    script_path = Path(output_dir) / "run_marker.py"
    script_path.write_text(script_content)
    
    # Run in clean environment
    env = {'PYTHONPATH': marker_repo}
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=marker_repo,
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Marker conversion failed: {result.stderr}")
    
    # Read results
    pdf_name = Path(pdf_path).stem
    markdown_path = Path(output_dir) / f"{pdf_name}.md"
    metadata_path = Path(output_dir) / f"{pdf_name}_meta.json"
    
    results = {
        'markdown': '',
        'metadata': {},
        'output_path': str(markdown_path)
    }
    
    if markdown_path.exists():
        results['markdown'] = markdown_path.read_text()
    
    if metadata_path.exists():
        results['metadata'] = json.loads(metadata_path.read_text())
    
    # Clean up script
    script_path.unlink()
    
    return results

def use_original_marker_direct_import(pdf_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Use original marker via direct import manipulation.
    Less reliable than subprocess but faster.
    
    Args:
        pdf_path: Path to PDF
        output_dir: Output directory
        
    Returns:
        dict: Results dictionary
    """
    # Save current sys.path
    original_path = sys.path.copy()
    
    try:
        # Clear any existing marker/extractor from path
        sys.path = [p for p in sys.path if 'marker' not in p and 'extractor' not in p]
        
        # Add original marker to path
        marker_repo = "/home/graham/workspace/experiments/extractor/repos/marker"
        sys.path.insert(0, marker_repo)
        
        # Import from original marker
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser
        from marker.output import save_output, text_from_rendered
        
        # Convert
        config_parser = ConfigParser()
        models = create_model_dict()
        
        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=models,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer()
        )
        
        rendered = converter(pdf_path)
        
        # Get text
        markdown_text = text_from_rendered(rendered)
        
        # Save if requested
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            save_output(rendered, output_dir)
        
        return {
            'markdown': markdown_text,
            'metadata': rendered.metadata if hasattr(rendered, 'metadata') else {},
            'output_path': output_dir
        }
        
    finally:
        # Restore original sys.path
        sys.path = original_path

# =============================================================================
# EXTRACTOR FUNCTIONS
# =============================================================================

def use_extractor_package(pdf_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Use the installed extractor package (renamed marker).
    
    Args:
        pdf_path: Path to PDF
        output_dir: Output directory
        
    Returns:
        dict: Results dictionary
    """
    from extractor.converters.pdf import PdfConverter
    from extractor.models import create_model_dict
    from extractor.config.parser import ConfigParser
    from extractor.output import save_output, text_from_rendered
    
    # Convert
    config_parser = ConfigParser()
    models = create_model_dict()
    
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer()
    )
    
    rendered = converter(pdf_path)
    
    # Get text
    markdown_text = text_from_rendered(rendered)
    
    # Save if requested
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        save_output(rendered, output_dir)
    
    return {
        'markdown': markdown_text,
        'metadata': rendered.metadata if hasattr(rendered, 'metadata') else {},
        'output_path': output_dir
    }

# =============================================================================
# COMPARISON FUNCTIONS
# =============================================================================

def compare_extractions(pdf_path: str, output_base_dir: str = None) -> Tuple[str, str]:
    """
    Compare original marker with extractor on the same PDF.
    
    Args:
        pdf_path: Path to PDF file
        output_base_dir: Base directory for outputs
        
    Returns:
        tuple: (original_markdown, extractor_markdown)
    """
    if output_base_dir is None:
        output_base_dir = tempfile.mkdtemp(prefix="marker_comparison_")
    
    print("=" * 80)
    print("🔬 MARKER vs EXTRACTOR COMPARISON")
    print("=" * 80)
    print(f"📄 PDF: {pdf_path}")
    print(f"📁 Output: {output_base_dir}")
    
    # Test 1: Original Marker (via subprocess - most reliable)
    print("\n1️⃣ Testing Original Marker (subprocess method)...")
    original_output_dir = Path(output_base_dir) / "original_marker"
    try:
        original_results = use_original_marker_subprocess(pdf_path, str(original_output_dir))
        print(f"✅ Original Marker: {len(original_results['markdown'])} characters")
    except Exception as e:
        print(f"❌ Original Marker failed: {e}")
        original_results = {'markdown': '', 'metadata': {}}
    
    # Test 2: Extractor Package
    print("\n2️⃣ Testing Extractor Package...")
    extractor_output_dir = Path(output_base_dir) / "extractor"
    try:
        extractor_results = use_extractor_package(pdf_path, str(extractor_output_dir))
        print(f"✅ Extractor: {len(extractor_results['markdown'])} characters")
    except Exception as e:
        print(f"❌ Extractor failed: {e}")
        extractor_results = {'markdown': '', 'metadata': {}}
    
    # Compare results
    print("\n" + "=" * 80)
    print("📊 COMPARISON RESULTS")
    print("=" * 80)
    
    orig_len = len(original_results['markdown'])
    ext_len = len(extractor_results['markdown'])
    
    print(f"Original Marker: {orig_len:,} characters")
    print(f"Extractor:       {ext_len:,} characters")
    print(f"Difference:      {abs(orig_len - ext_len):,} characters")
    
    if orig_len > 0:
        ratio = ext_len / orig_len
        print(f"Ratio:           {ratio:.2%}")
    
    # Check if identical
    if original_results['markdown'] == extractor_results['markdown']:
        print("\n✅ OUTPUTS ARE IDENTICAL!")
    else:
        print("\n⚠️  Outputs differ")
        
        # Find first difference
        for i, (c1, c2) in enumerate(zip(original_results['markdown'], extractor_results['markdown'])):
            if c1 != c2:
                context = 50
                start = max(0, i - context)
                end = min(len(original_results['markdown']), i + context)
                
                print(f"\nFirst difference at character {i}:")
                print(f"Original: ...{repr(original_results['markdown'][start:end])}...")
                print(f"Extractor: ...{repr(extractor_results['markdown'][start:end])}...")
                break
    
    print(f"\n📁 Outputs saved to:")
    print(f"   - Original: {original_output_dir}")
    print(f"   - Extractor: {extractor_output_dir}")
    
    return original_results['markdown'], extractor_results['markdown']

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Test PDF path
    test_pdf = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"❌ Test PDF not found: {test_pdf}")
        print("Please provide a valid PDF path")
        sys.exit(1)
    
    # Run comparison
    try:
        original, extractor = compare_extractions(test_pdf)
        
        # Show previews
        print("\n" + "=" * 80)
        print("📄 CONTENT PREVIEW")
        print("=" * 80)
        
        preview_length = 500
        print("\n🔵 Original Marker (first 500 chars):")
        print("-" * 40)
        print(original[:preview_length])
        print("-" * 40)
        
        print("\n🟢 Extractor (first 500 chars):")
        print("-" * 40) 
        print(extractor[:preview_length])
        print("-" * 40)
        
    except Exception as e:
        print(f"\n❌ Comparison failed: {e}")
        import traceback
        traceback.print_exc()