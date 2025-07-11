#!/usr/bin/env python3
"""
Module: compare_marker_extractor.py
Description: Comprehensive comparison tool for testing extractor vs original marker-pdf
             on PDF, HTML, and DOCX versions of the same document

External Dependencies:
- marker-pdf: https://github.com/VikParuchuri/marker
- beautifulsoup4: https://pypi.org/project/beautifulsoup4/
- python-docx: https://pypi.org/project/python-docx/
- loguru: https://pypi.org/project/loguru/

Sample Input:
>>> test_files = {
...     "pdf": "/path/to/document.pdf",
...     "html": "/path/to/document.html",
...     "docx": "/path/to/document.docx"
... }

Expected Output:
>>> comparison_report = {
...     "pdf": {"marker": {...}, "extractor": {...}, "similarity": 0.95},
...     "html": {"marker": None, "extractor": {...}, "similarity": None},
...     "docx": {"marker": None, "extractor": {...}, "similarity": None}
... }

Example Usage:
>>> from compare_marker_extractor import compare_extraction
>>> results = compare_extraction("test_doc.pdf", "test_doc.html", "test_doc.docx")
"""

import sys
import os
import json
import hashlib
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import subprocess
import importlib.util
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


def setup_marker_isolation():
    """Set up isolated environment to run original marker-pdf"""
    marker_path = Path("/home/graham/workspace/experiments/extractor/repos/marker")
    
    if not marker_path.exists():
        raise FileNotFoundError(f"Original marker source not found at {marker_path}")
    
    # Create a temporary isolated environment
    temp_dir = tempfile.mkdtemp(prefix="marker_isolated_")
    
    # Create a script that will run marker in isolation
    runner_script = Path(temp_dir) / "run_marker.py"
    runner_content = f'''#!/usr/bin/env python3
import sys
import json
import os

# Force the original marker path to be first in sys.path
sys.path.insert(0, "{marker_path}")

# Now import the original marker
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import load_all_models
    from marker.output import output_as_json
    
    def process_pdf(pdf_path):
        """Process PDF with original marker"""
        # Load models
        models = load_all_models()
        
        # Convert PDF
        converter = PdfConverter(
            artifact_dict=models,
            processor_list=None,
            renderer=output_as_json
        )
        
        rendered = converter(pdf_path)
        return rendered.output  # Get the result object
        
except Exception as e:
    print(json.dumps({{"error": f"Failed to import marker: {{e}}"}}))
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({{"error": "Usage: run_marker.py <pdf_path>"}}))
        sys.exit(1)
    
    try:
        result = process_pdf(sys.argv[1])
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({{"error": f"Processing failed: {{e}}"}}))
        sys.exit(1)
'''
    
    runner_script.write_text(runner_content)
    runner_script.chmod(0o755)
    
    return temp_dir, runner_script


def run_original_marker(pdf_path: str) -> Dict[str, Any]:
    """Run original marker-pdf in isolation"""
    temp_dir, runner_script = setup_marker_isolation()
    
    try:
        # Run the isolated marker script
        env = os.environ.copy()
        env["PYTHONPATH"] = f"/home/graham/workspace/experiments/extractor/repos/marker:{env.get('PYTHONPATH', '')}"
        
        result = subprocess.run(
            [sys.executable, str(runner_script), pdf_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Marker failed: {result.stderr}")
            return {"error": f"Marker failed: {result.stderr}"}
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse marker output: {e}")
            logger.debug(f"Raw output: {result.stdout}")
            return {"error": f"Failed to parse output: {e}", "raw_output": result.stdout}
            
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_extractor(file_path: str, file_type: str = "pdf") -> Dict[str, Any]:
    """Run extractor (forked marker) on various file types"""
    try:
        # Import extractor (this will work because it's installed as 'extractor')
        from extractor.converters.extraction import ExtractorConverter
        from extractor.models import load_all_models
        from extractor.output import output_as_json
        
        # Load models
        models = load_all_models()
        
        # Create converter based on file type
        if file_type.lower() == "pdf":
            from extractor.converters.pdf import PdfConverter
            converter = PdfConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
        elif file_type.lower() in ["html", "htm"]:
            from extractor.providers.html import HTMLProvider
            provider = HTMLProvider()
            document = provider.load(file_path)
            converter = ExtractorConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(document)
            return rendered.output
        elif file_type.lower() in ["docx", "doc"]:
            from extractor.providers.word import WordProvider
            provider = WordProvider()
            document = provider.load(file_path)
            converter = ExtractorConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(document)
            return rendered.output
        else:
            return {"error": f"Unsupported file type: {file_type}"}
        
        # Process file
        rendered = converter(file_path)
        return rendered.output
        
    except Exception as e:
        logger.error(f"Extractor failed on {file_path}: {e}")
        return {"error": f"Extractor failed: {e}"}


def calculate_similarity(result1: Dict[str, Any], result2: Dict[str, Any]) -> float:
    """Calculate similarity between two extraction results"""
    if "error" in result1 or "error" in result2:
        return 0.0
    
    # Extract text content from both results
    text1 = extract_text_content(result1)
    text2 = extract_text_content(result2)
    
    if not text1 or not text2:
        return 0.0
    
    # Simple similarity based on common words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0


def extract_text_content(result: Dict[str, Any]) -> str:
    """Extract all text content from a result dictionary"""
    if isinstance(result, str):
        return result
    
    text_parts = []
    
    if isinstance(result, dict):
        # Handle marker/extractor JSON output structure
        if "pages" in result:
            for page in result["pages"]:
                if "blocks" in page:
                    for block in page["blocks"]:
                        if "text" in block:
                            text_parts.append(block["text"])
        elif "text" in result:
            text_parts.append(result["text"])
        
        # Recursively extract text from nested structures
        for value in result.values():
            if isinstance(value, (dict, list)):
                text_parts.append(extract_text_content(value))
            elif isinstance(value, str):
                text_parts.append(value)
    
    elif isinstance(result, list):
        for item in result:
            text_parts.append(extract_text_content(item))
    
    return " ".join(filter(None, text_parts))


def compare_extraction(pdf_path: str, html_path: Optional[str] = None, 
                      docx_path: Optional[str] = None) -> Dict[str, Any]:
    """Compare extraction results across different formats"""
    logger.info("Starting extraction comparison...")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "files": {
            "pdf": pdf_path,
            "html": html_path,
            "docx": docx_path
        },
        "comparisons": {}
    }
    
    # Process PDF with both marker and extractor
    if pdf_path and Path(pdf_path).exists():
        logger.info(f"Processing PDF: {pdf_path}")
        
        # Run original marker
        logger.info("Running original marker...")
        marker_result = run_original_marker(pdf_path)
        
        # Run extractor
        logger.info("Running extractor on PDF...")
        extractor_result = run_extractor(pdf_path, "pdf")
        
        # Calculate similarity
        similarity = calculate_similarity(marker_result, extractor_result)
        
        results["comparisons"]["pdf"] = {
            "marker": marker_result,
            "extractor": extractor_result,
            "similarity": similarity,
            "marker_success": "error" not in marker_result,
            "extractor_success": "error" not in extractor_result
        }
        
        logger.info(f"PDF similarity: {similarity:.2%}")
    
    # Process HTML (extractor only, marker doesn't support HTML)
    if html_path and Path(html_path).exists():
        logger.info(f"Processing HTML: {html_path}")
        extractor_result = run_extractor(html_path, "html")
        
        results["comparisons"]["html"] = {
            "marker": {"error": "Marker does not support HTML"},
            "extractor": extractor_result,
            "similarity": None,
            "marker_success": False,
            "extractor_success": "error" not in extractor_result
        }
    
    # Process DOCX (extractor only, marker doesn't support DOCX)
    if docx_path and Path(docx_path).exists():
        logger.info(f"Processing DOCX: {docx_path}")
        extractor_result = run_extractor(docx_path, "docx")
        
        results["comparisons"]["docx"] = {
            "marker": {"error": "Marker does not support DOCX"},
            "extractor": extractor_result,
            "similarity": None,
            "marker_success": False,
            "extractor_success": "error" not in extractor_result
        }
    
    # Cross-format comparison for extractor
    if len([x for x in results["comparisons"].values() if x["extractor_success"]]) >= 2:
        logger.info("Performing cross-format comparison...")
        
        formats = []
        for fmt, data in results["comparisons"].items():
            if data["extractor_success"]:
                formats.append((fmt, data["extractor"]))
        
        if len(formats) >= 2:
            cross_similarities = {}
            for i in range(len(formats)):
                for j in range(i + 1, len(formats)):
                    fmt1, result1 = formats[i]
                    fmt2, result2 = formats[j]
                    sim = calculate_similarity(result1, result2)
                    cross_similarities[f"{fmt1}_vs_{fmt2}"] = sim
                    logger.info(f"Cross-format similarity {fmt1} vs {fmt2}: {sim:.2%}")
            
            results["cross_format_similarities"] = cross_similarities
    
    return results


def save_comparison_report(results: Dict[str, Any], output_path: str = None) -> str:
    """Save comparison results to a JSON file"""
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"marker_extractor_comparison_{timestamp}.json"
    
    # Create a summary for easier reading
    summary = {
        "timestamp": results["timestamp"],
        "files": results["files"],
        "summary": {}
    }
    
    for fmt, data in results["comparisons"].items():
        summary["summary"][fmt] = {
            "marker_success": data.get("marker_success", False),
            "extractor_success": data.get("extractor_success", False),
            "similarity": data.get("similarity", None),
            "marker_error": data["marker"].get("error") if "error" in data["marker"] else None,
            "extractor_error": data["extractor"].get("error") if "error" in data["extractor"] else None
        }
    
    if "cross_format_similarities" in results:
        summary["cross_format_similarities"] = results["cross_format_similarities"]
    
    # Save full results
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save summary
    summary_path = output_path.replace('.json', '_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Full results saved to: {output_path}")
    logger.info(f"Summary saved to: {summary_path}")
    
    return output_path


def print_comparison_summary(results: Dict[str, Any]):
    """Print a human-readable summary of the comparison"""
    print("\n" + "="*80)
    print("EXTRACTION COMPARISON SUMMARY")
    print("="*80)
    
    for fmt, data in results["comparisons"].items():
        print(f"\n{fmt.upper()} Format:")
        print("-" * 40)
        
        # Marker status
        if data["marker_success"]:
            print(f"✅ Marker: SUCCESS")
        else:
            error = data["marker"].get("error", "Unknown error")
            print(f"❌ Marker: FAILED - {error}")
        
        # Extractor status
        if data["extractor_success"]:
            print(f"✅ Extractor: SUCCESS")
        else:
            error = data["extractor"].get("error", "Unknown error")
            print(f"❌ Extractor: FAILED - {error}")
        
        # Similarity
        if data["similarity"] is not None:
            sim_percent = data["similarity"] * 100
            if sim_percent >= 90:
                print(f"🟢 Similarity: {sim_percent:.1f}% - EXCELLENT")
            elif sim_percent >= 70:
                print(f"🟡 Similarity: {sim_percent:.1f}% - GOOD")
            else:
                print(f"🔴 Similarity: {sim_percent:.1f}% - POOR")
    
    # Cross-format similarities
    if "cross_format_similarities" in results:
        print(f"\nCross-Format Similarities (Extractor):")
        print("-" * 40)
        for comparison, similarity in results["cross_format_similarities"].items():
            sim_percent = similarity * 100
            if sim_percent >= 90:
                status = "🟢 CONSISTENT"
            elif sim_percent >= 70:
                status = "🟡 MOSTLY CONSISTENT"
            else:
                status = "🔴 INCONSISTENT"
            print(f"{comparison}: {sim_percent:.1f}% - {status}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    # Example usage with test files
    test_pdf = "/home/graham/workspace/experiments/extractor/test_files/sample.pdf"
    test_html = "/home/graham/workspace/experiments/extractor/test_files/sample.html"
    test_docx = "/home/graham/workspace/experiments/extractor/test_files/sample.docx"
    
    # You can modify these paths to point to your actual test files
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
        test_html = sys.argv[2] if len(sys.argv) > 2 else None
        test_docx = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Check if at least PDF exists
    if not Path(test_pdf).exists():
        logger.error(f"PDF file not found: {test_pdf}")
        print(f"\nUsage: {sys.argv[0]} <pdf_path> [html_path] [docx_path]")
        print("\nExample:")
        print(f"  {sys.argv[0]} test.pdf test.html test.docx")
        sys.exit(1)
    
    # Run comparison
    results = compare_extraction(test_pdf, test_html, test_docx)
    
    # Print summary
    print_comparison_summary(results)
    
    # Save results
    report_path = save_comparison_report(results)
    
    # Check if extractor meets the baseline
    pdf_comparison = results["comparisons"].get("pdf", {})
    if pdf_comparison.get("extractor_success") and pdf_comparison.get("marker_success"):
        similarity = pdf_comparison.get("similarity", 0)
        if similarity >= 0.7:  # 70% similarity threshold
            print(f"\n✅ PASS: Extractor achieves {similarity:.1%} similarity with original marker")
            exit_code = 0
        else:
            print(f"\n❌ FAIL: Extractor only achieves {similarity:.1%} similarity with original marker")
            exit_code = 1
    elif pdf_comparison.get("extractor_success") and not pdf_comparison.get("marker_success"):
        print(f"\n✅ PASS: Extractor succeeds where marker fails")
        exit_code = 0
    else:
        print(f"\n❌ FAIL: Extractor failed to process PDF")
        exit_code = 1
    
    sys.exit(exit_code)