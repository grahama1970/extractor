#!/usr/bin/env python3
"""
Module: original_marker_isolated.py
Description: Isolated environment for using original marker-pdf

External Dependencies:
- None (uses isolated Python environment)

Sample Input:
>>> pdf_path = "/path/to/document.pdf"

Expected Output:
>>> markdown = use_original_marker_isolated(pdf_path)
>>> print(f"Extracted {len(markdown)} characters")
"Extracted 12345 characters"

Example Usage:
>>> from original_marker_isolated import use_original_marker_isolated
>>> content = use_original_marker_isolated("test.pdf")
"""

import sys
import os
import subprocess
import json
from pathlib import Path
import tempfile

def create_isolated_marker_script(pdf_path: str, output_dir: str) -> str:
    """
    Create a standalone Python script that uses the original marker.
    This script will be run in an isolated subprocess.
    """
    script_content = f'''#!/usr/bin/env python3
import sys
import os

# Force the use of the original marker by manipulating sys.path
marker_path = "/home/graham/workspace/experiments/extractor/repos/marker"
sys.path.insert(0, marker_path)

# Change to marker directory to ensure relative imports work
os.chdir(marker_path)

# Now we can safely import from the original marker
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import save_output

def main():
    pdf_path = "{pdf_path}"
    output_dir = "{output_dir}"
    
    print(f"Processing: {{pdf_path}}")
    print(f"Output to: {{output_dir}}")
    
    # Create models and config
    config_parser = ConfigParser()
    models = create_model_dict()
    
    # Create converter
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer()
    )
    
    # Convert PDF
    rendered = converter(pdf_path)
    
    # Save output
    save_output(rendered, output_dir)
    
    print("✅ Conversion complete!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {{e}}")
        sys.exit(1)
'''
    
    # Write script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        return f.name

def use_original_marker_isolated(pdf_path: str, output_dir: str = None) -> str:
    """
    Use the original marker in a completely isolated subprocess.
    This guarantees no import conflicts.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Output directory (optional)
        
    Returns:
        str: The extracted markdown content
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="marker_output_")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # Create isolated script
    script_path = create_isolated_marker_script(pdf_path, output_dir)
    
    try:
        # Run script in isolated subprocess
        env = os.environ.copy()
        # Clear PYTHONPATH to ensure clean environment
        env['PYTHONPATH'] = ""
        
        result = subprocess.run(
            [sys.executable, script_path],
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Original marker conversion successful!")
        if result.stdout:
            print(result.stdout)
        
        # Read the output markdown
        pdf_name = Path(pdf_path).stem
        markdown_path = Path(output_dir) / f"{pdf_name}.md"
        
        if markdown_path.exists():
            return markdown_path.read_text()
        else:
            raise FileNotFoundError(f"Expected output not found: {markdown_path}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Conversion failed: {e}")
        print(f"Error output: {e.stderr}")
        raise
    finally:
        # Clean up temporary script
        if os.path.exists(script_path):
            os.unlink(script_path)

def use_original_marker_cli(pdf_path: str, output_dir: str = None) -> str:
    """
    Alternative: Use the marker CLI directly via subprocess.
    This is the simplest and most reliable method.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Output directory
        
    Returns:
        str: Path to the generated markdown file
    """
    marker_dir = "/home/graham/workspace/experiments/extractor/repos/marker"
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="marker_cli_output_")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # Use the marker CLI
    cmd = [
        sys.executable,
        "-m", "marker.scripts.convert_single",
        pdf_path,
        output_dir,
        "--output_format", "markdown"
    ]
    
    # Run with clean environment
    env = os.environ.copy()
    env['PYTHONPATH'] = marker_dir
    
    print(f"🚀 Running marker CLI...")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=marker_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ CLI conversion successful!")
        
        # Find output file
        pdf_name = Path(pdf_path).stem
        markdown_path = Path(output_dir) / f"{pdf_name}.md"
        
        if markdown_path.exists():
            return str(markdown_path)
        else:
            # List directory contents for debugging
            print(f"Directory contents: {list(Path(output_dir).iterdir())}")
            raise FileNotFoundError(f"Output not found: {markdown_path}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ CLI conversion failed: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise

def quick_test():
    """
    Quick test function to verify the original marker works.
    """
    test_pdf = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"❌ Test PDF not found: {test_pdf}")
        return
    
    print("=" * 80)
    print("🧪 ORIGINAL MARKER ISOLATED TEST")
    print("=" * 80)
    
    # Method 1: Isolated script
    print("\n1️⃣ Testing isolated script method...")
    try:
        markdown_content = use_original_marker_isolated(test_pdf)
        print(f"✅ Success! Extracted {len(markdown_content)} characters")
        print(f"Preview: {markdown_content[:200]}...")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Method 2: CLI method
    print("\n2️⃣ Testing CLI method...")
    try:
        output_path = use_original_marker_cli(test_pdf)
        markdown_content = Path(output_path).read_text()
        print(f"✅ Success! Extracted {len(markdown_content)} characters")
        print(f"Output saved to: {output_path}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    quick_test()