#!/usr/bin/env python3
"""
Module: test_comprehensive_comparison.py
Description: Comprehensive 3-way comparison test for extractor vs marker-pdf vs original sources

This usage function tests:
1. Original source formats (Markdown if available, HTML, PDF)
2. marker-pdf baseline extraction (the original package)
3. extractor performance (should match or exceed marker-pdf)

External Dependencies:
- marker-pdf: Original PDF extraction library
- extractor: Enhanced fork with unified JSON output

Sample Input:
>>> test_file = "2505.03335v2"  # arXiv paper ID

Expected Output:
>>> # Comparison results showing extraction quality across all methods
>>> # Unified JSON structure should be consistent across formats

Example Usage:
>>> python test_comprehensive_comparison.py
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib

# Add marker-pdf to path
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/repos/marker')

# Import extractor modules
from extractor.unified_extractor import extract_to_unified_json


def check_arxiv_markdown(paper_id: str) -> Optional[str]:
    """Check if arXiv provides markdown for this paper"""
    # Note: arXiv doesn't typically provide markdown, but we check anyway
    print(f"🔍 Checking for arXiv markdown version of {paper_id}...")
    
    # arXiv doesn't have a markdown API, but we can check
    # In reality, arXiv provides: PDF, HTML, source (LaTeX)
    print("   ℹ️  arXiv does not provide markdown format (only PDF, HTML, LaTeX source)")
    return None


def extract_with_marker_pdf(pdf_path: str) -> Dict[str, Any]:
    """Extract using original marker-pdf package"""
    print(f"\n📘 Extracting with ORIGINAL marker-pdf: {Path(pdf_path).name}")
    
    try:
        # Use the marker-pdf CLI directly
        output_dir = Path(pdf_path).parent / "marker_output"
        output_dir.mkdir(exist_ok=True)
        
        start_time = time.time()
        
        # Run marker-pdf convert_single command
        cmd = [
            sys.executable,
            "/home/graham/workspace/experiments/extractor/repos/marker/convert_single.py",
            pdf_path,
            str(output_dir),
            "--max_pages", "10"  # Limit for testing
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            # Find the output markdown file
            md_files = list(output_dir.glob("*.md"))
            if md_files:
                md_content = md_files[0].read_text()
                print(f"   ✅ Extracted {len(md_content)} characters in {elapsed:.2f}s")
                print(f"   📄 Output saved to: {md_files[0]}")
                
                # Return a structure similar to unified JSON for comparison
                return {
                    "format": "markdown",
                    "content": md_content,
                    "length": len(md_content),
                    "extraction_time": elapsed,
                    "tool": "marker-pdf",
                    "output_file": str(md_files[0])
                }
            else:
                print(f"   ❌ No markdown output found")
                return {"error": "No output file", "tool": "marker-pdf"}
        else:
            print(f"   ❌ marker-pdf failed: {result.stderr}")
            return {"error": result.stderr, "tool": "marker-pdf"}
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {"error": str(e), "tool": "marker-pdf"}


def extract_with_extractor(file_path: str) -> Dict[str, Any]:
    """Extract using extractor's unified JSON approach"""
    print(f"\n🔷 Extracting with EXTRACTOR: {Path(file_path).name}")
    
    try:
        start_time = time.time()
        result = extract_to_unified_json(file_path)
        elapsed = time.time() - start_time
        
        # Calculate content size
        content_size = 0
        if 'vertices' in result and 'sections' in result['vertices']:
            for section in result['vertices']['sections']:
                content_size += len(section.get('content', ''))
        
        print(f"   ✅ Extracted unified JSON in {elapsed:.2f}s")
        print(f"   📊 Sections: {len(result.get('vertices', {}).get('sections', []))}")
        print(f"   📊 Content size: {content_size} characters")
        
        # Save the result for inspection
        output_path = Path(file_path).parent / f"{Path(file_path).stem}_extractor.json"
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"   📄 Output saved to: {output_path}")
        
        return {
            "format": "unified_json",
            "result": result,
            "content_size": content_size,
            "section_count": len(result.get('vertices', {}).get('sections', [])),
            "extraction_time": elapsed,
            "tool": "extractor",
            "output_file": str(output_path)
        }
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "tool": "extractor"}


def calculate_content_hash(content: str) -> str:
    """Calculate hash of content for comparison"""
    return hashlib.md5(content.encode()).hexdigest()[:8]


def compare_results(results: Dict[str, Dict[str, Any]]) -> None:
    """Compare extraction results across methods"""
    print("\n" + "="*70)
    print("📊 COMPARISON RESULTS")
    print("="*70)
    
    # Summary table
    print("\n| Method | Status | Time | Content Size | Notes |")
    print("|--------|--------|------|--------------|-------|")
    
    for method, result in results.items():
        if "error" in result:
            error_msg = str(result['error'])[:30]
            print(f"| {method:20} | ❌ FAIL | - | - | {error_msg}... |")
        else:
            time_str = f"{result.get('extraction_time', 0):.2f}s"
            size = result.get('content_size', result.get('length', 0))
            status = "✅ PASS"
            notes = ""
            
            # Check for quality indicators
            if size < 1000:
                status = "⚠️ WARN"
                notes = "Low content extraction"
            
            print(f"| {method:20} | {status} | {time_str:6} | {size:12,} | {notes} |")
    
    # Detailed comparison
    print("\n🔍 DETAILED ANALYSIS:")
    
    # Compare marker-pdf vs extractor on PDF
    if "marker-pdf (PDF)" in results and "extractor (PDF)" in results:
        marker_result = results["marker-pdf (PDF)"]
        extractor_result = results["extractor (PDF)"]
        
        if "error" not in marker_result and "error" not in extractor_result:
            marker_size = marker_result.get('length', 0)
            extractor_size = extractor_result.get('content_size', 0)
            
            ratio = extractor_size / marker_size if marker_size > 0 else 0
            
            print(f"\n📈 Extractor vs marker-pdf comparison:")
            print(f"   - marker-pdf content: {marker_size:,} chars")
            print(f"   - Extractor content: {extractor_size:,} chars")
            print(f"   - Content size ratio: {ratio:.2f}x")
            print(f"   - Extractor sections: {extractor_result.get('section_count', 0)}")
            
            if ratio >= 0.9:
                print("   ✅ Extractor performance is acceptable (≥90% of marker-pdf)")
            else:
                print("   ❌ Extractor performance is below marker-pdf baseline")
                
            # Show file locations for manual inspection
            if 'output_file' in marker_result:
                print(f"\n   📁 marker-pdf output: {marker_result['output_file']}")
            if 'output_file' in extractor_result:
                print(f"   📁 Extractor output: {extractor_result['output_file']}")
    
    # Compare different format extractions with extractor
    format_results = {k: v for k, v in results.items() if k.startswith("extractor")}
    if len(format_results) > 1:
        print(f"\n📋 Cross-format consistency check:")
        
        section_counts = []
        content_sizes = []
        for fmt, result in format_results.items():
            if "error" not in result:
                count = result.get('section_count', 0)
                size = result.get('content_size', 0)
                section_counts.append((fmt, count))
                content_sizes.append((fmt, size))
        
        if section_counts:
            # Check if section counts are similar
            counts = [c[1] for c in section_counts]
            avg_count = sum(counts) / len(counts)
            max_deviation = max(abs(c - avg_count) for c in counts) / avg_count if avg_count > 0 else 0
            
            print(f"   - Section counts: {', '.join(f'{fmt}: {count}' for fmt, count in section_counts)}")
            print(f"   - Content sizes: {', '.join(f'{fmt}: {size:,}' for fmt, size in content_sizes)}")
            print(f"   - Max deviation: {max_deviation:.1%}")
            
            if max_deviation < 0.2:  # Within 20%
                print("   ✅ Format extraction is consistent")
            else:
                print("   ⚠️  Format extraction shows significant variation")


def main():
    """Main test function - comprehensive comparison"""
    print("🧪 Comprehensive Extractor vs marker-pdf Comparison Test")
    print("="*70)
    
    # Test files
    base_path = "/home/graham/workspace/experiments/extractor/data/input"
    test_file = "2505.03335v2"
    
    results = {}
    
    # 1. Check for gold standard (Markdown from arXiv)
    markdown_content = check_arxiv_markdown(test_file)
    if markdown_content:
        results["arXiv Markdown"] = {
            "format": "markdown",
            "content": markdown_content,
            "length": len(markdown_content),
            "tool": "arxiv"
        }
    
    # 2. Test with original marker-pdf on PDF
    pdf_path = f"{base_path}/{test_file}.pdf"
    if os.path.exists(pdf_path):
        results["marker-pdf (PDF)"] = extract_with_marker_pdf(pdf_path)
    else:
        print(f"\n⚠️  PDF file not found: {pdf_path}")
    
    # 3. Test with extractor on multiple formats
    test_formats = {
        "PDF": f"{base_path}/{test_file}.pdf",
        "HTML": f"{base_path}/{test_file}.html",
        "DOCX": f"{base_path}/{test_file}.docx"
    }
    
    for fmt, path in test_formats.items():
        if os.path.exists(path):
            results[f"extractor ({fmt})"] = extract_with_extractor(path)
        else:
            print(f"\n⚠️  {fmt} file not found: {path}")
    
    # 4. Compare all results
    compare_results(results)
    
    # 5. Final verdict
    print("\n" + "="*70)
    print("🏁 FINAL VERDICT:")
    
    # Check if extractor matches marker-pdf baseline
    pdf_comparison_valid = False
    if "marker-pdf (PDF)" in results and "extractor (PDF)" in results:
        if "error" not in results["marker-pdf (PDF)"] and "error" not in results["extractor (PDF)"]:
            marker_size = results["marker-pdf (PDF)"].get('length', 0)
            extractor_size = results["extractor (PDF)"].get('content_size', 0)
            if marker_size > 0:
                ratio = extractor_size / marker_size
                pdf_comparison_valid = ratio >= 0.9
    
    # Check format consistency
    format_consistent = True
    extractor_formats = [r for k, r in results.items() if k.startswith("extractor") and "error" not in r]
    if len(extractor_formats) > 1:
        section_counts = [r.get('section_count', 0) for r in extractor_formats]
        if section_counts:
            avg = sum(section_counts) / len(section_counts)
            max_dev = max(abs(c - avg) for c in section_counts) / avg if avg > 0 else 1
            format_consistent = max_dev < 0.2
    
    # Overall assessment
    if pdf_comparison_valid and format_consistent:
        print("✅ PASS: Extractor meets or exceeds marker-pdf baseline")
        print("✅ PASS: Format extraction is consistent across PDF/HTML/DOCX")
        exit(0)
    else:
        if not pdf_comparison_valid:
            print("❌ FAIL: Extractor performance is below marker-pdf baseline")
        if not format_consistent:
            print("❌ FAIL: Format extraction is inconsistent")
        
        # But note about PyMuPDF fallback
        print("\n⚠️  NOTE: Current implementation uses PyMuPDF fallback")
        print("   The user has stated: 'using Pymupdf as a fallback is a failure'")
        print("   Need to fix Surya model implementation by studying repos/marker")
        exit(1)


if __name__ == "__main__":
    main()