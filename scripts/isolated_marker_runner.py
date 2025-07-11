#!/usr/bin/env python3
"""
Module: isolated_marker_runner.py
Description: Run original marker in complete isolation using subprocess to avoid any import conflicts

External Dependencies:
- None (uses subprocess isolation)

Sample Input:
>>> pdf_path = "document.pdf"

Expected Output:
>>> {"pages": [...], "metadata": {...}}

Example Usage:
>>> from isolated_marker_runner import run_original_marker_isolated
>>> result = run_original_marker_isolated("document.pdf")
"""

import subprocess
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import os


def create_marker_runner_script() -> str:
    """Create a temporary Python script that runs original marker"""
    script_content = '''#!/usr/bin/env python3
import sys
import json
import os

# Force original marker path
sys.path.insert(0, "/home/graham/workspace/experiments/extractor/repos/marker")

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import load_all_models
    from marker.output import output_as_json
    
    def main():
        if len(sys.argv) != 2:
            print(json.dumps({"error": "Usage: script.py <pdf_path>"}))
            sys.exit(1)
        
        pdf_path = sys.argv[1]
        
        try:
            # Load models
            models = load_all_models()
            
            # Create converter
            converter = PdfConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            
            # Process PDF
            rendered = converter(pdf_path)
            result = rendered.output
            
            # Output as JSON
            print(json.dumps(result))
            
        except Exception as e:
            print(json.dumps({"error": f"Processing failed: {str(e)}"}))
            sys.exit(1)
    
    if __name__ == "__main__":
        main()
        
except Exception as e:
    print(json.dumps({"error": f"Import failed: {str(e)}"}))
    sys.exit(1)
'''
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        return f.name


def run_original_marker_isolated(pdf_path: str, timeout: int = 300) -> Dict[str, Any]:
    """Run original marker in complete isolation"""
    script_path = create_marker_runner_script()
    
    try:
        # Create a clean environment
        env = os.environ.copy()
        # Remove any PYTHONPATH that might interfere
        env.pop('PYTHONPATH', None)
        
        # Add only the marker repo path
        env['PYTHONPATH'] = "/home/graham/workspace/experiments/extractor/repos/marker"
        
        # Run the script in isolation
        result = subprocess.run(
            [sys.executable, script_path, pdf_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout
        )
        
        if result.returncode != 0:
            return {"error": f"Marker failed with code {result.returncode}: {result.stderr}"}
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse marker output: {e}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
    finally:
        # Clean up temporary script
        Path(script_path).unlink(missing_ok=True)


def run_extractor_on_multiple_formats(base_path: str) -> Dict[str, Dict[str, Any]]:
    """Run extractor on PDF, HTML, and DOCX versions of a document"""
    from extractor.models import load_all_models
    from extractor.output import output_as_json
    
    results = {}
    base = Path(base_path).stem
    
    # Load models once
    models = load_all_models()
    
    # Try PDF
    pdf_path = Path(base_path).with_suffix('.pdf')
    if pdf_path.exists():
        try:
            from extractor.converters.pdf import PdfConverter
            converter = PdfConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(str(pdf_path))
            results['pdf'] = rendered.output
        except Exception as e:
            results['pdf'] = {"error": str(e)}
    
    # Try HTML
    html_path = Path(base_path).with_suffix('.html')
    if html_path.exists():
        try:
            from extractor.providers.html import HTMLProvider
            from extractor.converters.extraction import ExtractorConverter
            
            provider = HTMLProvider()
            document = provider.load(str(html_path))
            converter = ExtractorConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(document)
            results['html'] = rendered.output
        except Exception as e:
            results['html'] = {"error": str(e)}
    
    # Try DOCX
    docx_path = Path(base_path).with_suffix('.docx')
    if docx_path.exists():
        try:
            from extractor.providers.word import WordProvider
            from extractor.converters.extraction import ExtractorConverter
            
            provider = WordProvider()
            document = provider.load(str(docx_path))
            converter = ExtractorConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(document)
            results['docx'] = rendered.output
        except Exception as e:
            results['docx'] = {"error": str(e)}
    
    return results


def comprehensive_comparison(base_document: str) -> Dict[str, Any]:
    """Run comprehensive comparison between marker and extractor"""
    base_path = Path(base_document)
    pdf_path = base_path.with_suffix('.pdf')
    
    comparison = {
        "document": str(base_path),
        "marker_baseline": None,
        "extractor_results": {},
        "analysis": {}
    }
    
    # Step 1: Get marker baseline (PDF only)
    if pdf_path.exists():
        print(f"Running original marker on {pdf_path}...")
        comparison["marker_baseline"] = run_original_marker_isolated(str(pdf_path))
        
        if "error" not in comparison["marker_baseline"]:
            print("✅ Marker baseline established")
        else:
            print(f"❌ Marker failed: {comparison['marker_baseline']['error']}")
    
    # Step 2: Run extractor on all formats
    print("\nRunning extractor on all available formats...")
    comparison["extractor_results"] = run_extractor_on_multiple_formats(str(base_path))
    
    # Step 3: Analyze results
    for fmt, result in comparison["extractor_results"].items():
        if "error" not in result:
            print(f"✅ Extractor succeeded on {fmt.upper()}")
        else:
            print(f"❌ Extractor failed on {fmt.upper()}: {result['error']}")
    
    # Step 4: Compare with baseline if available
    if comparison["marker_baseline"] and "error" not in comparison["marker_baseline"]:
        if "pdf" in comparison["extractor_results"] and "error" not in comparison["extractor_results"]["pdf"]:
            # Compare PDF results
            marker_text_len = sum(
                len(block.get("text", ""))
                for page in comparison["marker_baseline"].get("pages", [])
                for block in page.get("blocks", [])
            )
            
            extractor_text_len = sum(
                len(block.get("text", ""))
                for page in comparison["extractor_results"]["pdf"].get("pages", [])
                for block in page.get("blocks", [])
            )
            
            comparison["analysis"]["pdf_comparison"] = {
                "marker_text_length": marker_text_len,
                "extractor_text_length": extractor_text_len,
                "ratio": extractor_text_len / marker_text_len if marker_text_len > 0 else 0
            }
            
            print(f"\nPDF Comparison:")
            print(f"  Marker text: {marker_text_len:,} chars")
            print(f"  Extractor text: {extractor_text_len:,} chars")
            print(f"  Ratio: {comparison['analysis']['pdf_comparison']['ratio']:.2f}")
    
    return comparison


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare marker and extractor in isolation")
    parser.add_argument("document", help="Base document path (without extension)")
    parser.add_argument("--save", help="Save comparison to JSON file", action="store_true")
    
    args = parser.parse_args()
    
    # Run comprehensive comparison
    print("="*60)
    print("ISOLATED MARKER VS EXTRACTOR COMPARISON")
    print("="*60)
    
    comparison = comprehensive_comparison(args.document)
    
    if args.save:
        output_file = f"isolated_comparison_{Path(args.document).stem}.json"
        with open(output_file, 'w') as f:
            # Save a summary version
            summary = {
                "document": comparison["document"],
                "marker_success": "error" not in comparison["marker_baseline"] if comparison["marker_baseline"] else False,
                "extractor_formats": {
                    fmt: "error" not in result
                    for fmt, result in comparison["extractor_results"].items()
                },
                "analysis": comparison["analysis"]
            }
            json.dump(summary, f, indent=2)
        print(f"\nComparison saved to: {output_file}")
    
    # Determine overall success
    extractor_pdf_success = (
        "pdf" in comparison["extractor_results"] and 
        "error" not in comparison["extractor_results"]["pdf"]
    )
    
    if extractor_pdf_success:
        if comparison.get("analysis", {}).get("pdf_comparison", {}).get("ratio", 0) >= 0.8:
            print("\n✅ SUCCESS: Extractor is compatible with marker baseline")
            sys.exit(0)
        else:
            print("\n⚠️  WARNING: Extractor output differs from marker baseline")
            sys.exit(1)
    else:
        print("\n❌ FAILURE: Extractor failed to process PDF")
        sys.exit(1)