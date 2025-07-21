#!/usr/bin/env python3
"""
Module: visual_verification_test.py
Description: Visual verification of PDF extraction by converting pages to images

This module extracts PDF pages as images and analyzes them to verify:
- Table of contents structure
- Section headers on specific pages
- Tables and equations on specific pages
- Overall document structure

External Dependencies:
- pdf2image: https://pypi.org/project/pdf2image/
- Pillow: https://pillow.readthedocs.io/
- PyMuPDF: https://pymupdf.readthedocs.io/

Sample Input:
>>> pdf_path = "2505.03335v2.pdf"
>>> verify_extraction_visually(pdf_path)

Expected Output:
>>> verification_results = {
>>>     "toc_analysis": {...},
>>>     "section_verification": {...},
>>>     "content_samples": {...}
>>> }

Example Usage:
>>> from visual_verification_test import verify_extraction_visually
>>> results = verify_extraction_visually("paper.pdf")
>>> print(f"Found {results['total_sections']} sections")
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import tempfile

# Add extractor to path
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/src')


def extract_pdf_page_as_image(pdf_path: str, page_num: int, output_dir: str) -> Optional[str]:
    """Extract a single PDF page as an image"""
    try:
        from pdf2image import convert_from_path
        
        # Convert specific page
        images = convert_from_path(
            pdf_path,
            first_page=page_num,
            last_page=page_num,
            dpi=150  # Good quality for analysis
        )
        
        if images:
            output_path = os.path.join(output_dir, f"page_{page_num:03d}.png")
            images[0].save(output_path, "PNG")
            return output_path
            
    except ImportError:
        # Fallback to PyMuPDF
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            if page_num <= len(doc):
                page = doc[page_num - 1]  # 0-indexed
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale
                output_path = os.path.join(output_dir, f"page_{page_num:03d}.png")
                pix.save(output_path)
                doc.close()
                return output_path
                
        except Exception as e:
            print(f"Failed to extract page {page_num}: {e}")
    
    return None


def analyze_toc_pages(pdf_path: str) -> Dict[str, Any]:
    """Analyze table of contents pages (usually first few pages)"""
    print("\n📚 Analyzing Table of Contents...")
    
    toc_info = {
        "found": False,
        "page_numbers": [],
        "sections": []
    }
    
    try:
        import fitz  # PyMuPDF for text extraction
        doc = fitz.open(pdf_path)
        
        # Check first 10 pages for TOC
        for page_num in range(min(10, len(doc))):
            page = doc[page_num]
            text = page.get_text()
            
            # Look for TOC indicators
            if any(indicator in text.lower() for indicator in ["contents", "table of contents", "toc"]):
                toc_info["found"] = True
                toc_info["page_numbers"].append(page_num + 1)
                
                # Extract section titles (lines with page numbers)
                lines = text.split('\n')
                for line in lines:
                    # Look for pattern: "Title ... page_number"
                    if any(char.isdigit() for char in line) and '.' in line:
                        # Clean up the line
                        clean_line = line.strip()
                        if len(clean_line) > 5 and not clean_line.startswith(('©', '®')):
                            toc_info["sections"].append(clean_line)
        
        doc.close()
        
    except Exception as e:
        print(f"TOC analysis error: {e}")
    
    return toc_info


def sample_document_structure(pdf_path: str, sample_pages: List[int] = None) -> Dict[str, Any]:
    """Sample specific pages to understand document structure"""
    print("\n🔍 Sampling document structure...")
    
    if sample_pages is None:
        # Default sampling strategy
        try:
            import fitz
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            doc.close()
            
            # Sample: first page, 25%, 50%, 75%, last page
            sample_pages = [
                1,
                total_pages // 4,
                total_pages // 2,
                (3 * total_pages) // 4,
                total_pages
            ]
        except:
            sample_pages = [1, 5, 10, 15, 20]
    
    structure_info = {
        "total_pages": 0,
        "page_samples": {}
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for page_num in sample_pages:
            print(f"   Analyzing page {page_num}...")
            
            # Extract page as image
            image_path = extract_pdf_page_as_image(pdf_path, page_num, temp_dir)
            
            if image_path and os.path.exists(image_path):
                # Read the image to verify it was created
                try:
                    from PIL import Image
                    img = Image.open(image_path)
                    
                    page_info = {
                        "page_number": page_num,
                        "image_size": img.size,
                        "image_path": image_path,
                        "extracted": True
                    }
                    
                    # Extract text from this page
                    try:
                        import fitz
                        doc = fitz.open(pdf_path)
                        if page_num <= len(doc):
                            page = doc[page_num - 1]
                            text = page.get_text()
                            
                            # Analyze content
                            page_info["has_equations"] = "$$" in text or "\\[" in text or "\\begin{" in text
                            page_info["has_table"] = "|" in text and text.count("|") > 5
                            page_info["word_count"] = len(text.split())
                            
                            # Find headers (lines that are likely section titles)
                            lines = text.split('\n')
                            headers = []
                            for line in lines:
                                line = line.strip()
                                if (len(line) > 10 and len(line) < 100 and 
                                    line[0].isupper() and 
                                    not line.endswith(('.', ',', ';'))):
                                    headers.append(line)
                            
                            page_info["potential_headers"] = headers[:3]  # First 3
                            
                        doc.close()
                        
                    except Exception as e:
                        page_info["text_extraction_error"] = str(e)
                    
                    structure_info["page_samples"][page_num] = page_info
                    
                except Exception as e:
                    print(f"   Failed to analyze page {page_num}: {e}")
    
    return structure_info


def verify_extraction_visually(pdf_path: str) -> Dict[str, Any]:
    """Main visual verification function"""
    print("🖼️  Visual Extraction Verification")
    print("=" * 70)
    print(f"PDF: {Path(pdf_path).name}")
    
    results = {
        "pdf_path": pdf_path,
        "verification_complete": False
    }
    
    # 1. Analyze TOC
    toc_analysis = analyze_toc_pages(pdf_path)
    results["toc_analysis"] = toc_analysis
    
    if toc_analysis["found"]:
        print(f"✅ Found Table of Contents on page(s): {toc_analysis['page_numbers']}")
        print(f"   Detected {len(toc_analysis['sections'])} sections")
        
        # Show first few sections
        print("\n   First 5 sections from TOC:")
        for i, section in enumerate(toc_analysis["sections"][:5]):
            print(f"   {i+1}. {section}")
    else:
        print("⚠️  No Table of Contents found in first 10 pages")
    
    # 2. Sample document structure
    structure = sample_document_structure(pdf_path)
    results["structure_analysis"] = structure
    
    print(f"\n📄 Document Structure Analysis:")
    for page_num, info in structure.get("page_samples", {}).items():
        if info.get("extracted"):
            print(f"\n   Page {page_num}:")
            print(f"   - Words: {info.get('word_count', 0)}")
            print(f"   - Has equations: {'Yes' if info.get('has_equations') else 'No'}")
            print(f"   - Has tables: {'Yes' if info.get('has_table') else 'No'}")
            
            headers = info.get("potential_headers", [])
            if headers:
                print(f"   - Potential headers: {headers[0][:50]}...")
    
    # 3. Compare with extraction results
    print("\n" + "=" * 70)
    print("🔬 Comparing with Extraction Results")
    print("=" * 70)
    
    # Load previous extraction results if available
    base_path = Path(pdf_path).parent
    comparison_file = base_path / "extraction_comparison_results.json"
    
    if comparison_file.exists():
        with open(comparison_file, 'r') as f:
            extraction_results = json.load(f)
        
        # Compare section counts
        visual_sections = len(toc_analysis.get("sections", []))
        
        print("\n📊 Section Count Comparison:")
        print(f"   Visual (TOC): {visual_sections} sections")
        
        for method in ["latexml_gold_standard", "extractor_pdf", "marker_pdf"]:
            if method in extraction_results.get("results", {}):
                count = extraction_results["results"][method].get("total_sections", 0)
                match = "✅" if abs(count - visual_sections) <= 3 else "❌"
                print(f"   {method}: {count} sections {match}")
    
    results["verification_complete"] = True
    
    # 4. Create verification report
    print("\n" + "=" * 70)
    print("📝 VISUAL VERIFICATION SUMMARY")
    print("=" * 70)
    
    if toc_analysis["found"] and len(toc_analysis["sections"]) > 10:
        print("✅ Document structure verified:")
        print(f"   - Clear table of contents found")
        print(f"   - {len(toc_analysis['sections'])} sections identified")
        print("   - Document appears well-structured")
    else:
        print("⚠️  Document structure unclear:")
        print("   - Table of contents not found or incomplete")
        print("   - Manual page inspection recommended")
    
    # Save verification results
    output_path = base_path / "visual_verification_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Visual verification results saved to: {output_path}")
    
    return results


def create_page_image_gallery(pdf_path: str, pages: List[int], output_dir: str):
    """Create a gallery of specific pages for manual inspection"""
    print(f"\n🖼️  Creating image gallery for pages: {pages}")
    
    os.makedirs(output_dir, exist_ok=True)
    extracted_images = []
    
    for page_num in pages:
        image_path = extract_pdf_page_as_image(pdf_path, page_num, output_dir)
        if image_path:
            extracted_images.append(image_path)
            print(f"   ✅ Extracted page {page_num}")
        else:
            print(f"   ❌ Failed to extract page {page_num}")
    
    # Create an HTML viewer
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>PDF Page Gallery - {Path(pdf_path).name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .page {{ margin: 20px 0; border: 1px solid #ccc; padding: 10px; }}
        img {{ max-width: 100%; height: auto; }}
        h2 {{ color: #333; }}
    </style>
</head>
<body>
    <h1>PDF Page Gallery: {Path(pdf_path).name}</h1>
    <p>Visual inspection of selected pages</p>
"""
    
    for img_path in extracted_images:
        page_num = Path(img_path).stem.replace('page_', '')
        html_content += f"""
    <div class="page">
        <h2>Page {page_num}</h2>
        <img src="{Path(img_path).name}" alt="Page {page_num}">
    </div>
"""
    
    html_content += """
</body>
</html>
"""
    
    viewer_path = os.path.join(output_dir, "page_gallery.html")
    with open(viewer_path, 'w') as f:
        f.write(html_content)
    
    print(f"\n✅ Page gallery created: {viewer_path}")
    return viewer_path


if __name__ == "__main__":
    # Test with the research paper
    pdf_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    if os.path.exists(pdf_path):
        # Run visual verification
        results = verify_extraction_visually(pdf_path)
        
        # Create page gallery for key pages
        print("\n" + "=" * 70)
        print("🎨 Creating Page Gallery for Manual Inspection")
        print("=" * 70)
        
        gallery_dir = "/home/graham/workspace/experiments/extractor/data/output/page_gallery"
        
        # Select key pages to inspect
        key_pages = [1, 2, 3]  # First few pages (usually TOC)
        
        # Add pages mentioned in the structure analysis
        if "structure_analysis" in results:
            for page_info in results["structure_analysis"].get("page_samples", {}).values():
                if page_info.get("has_table") or page_info.get("has_equations"):
                    key_pages.append(page_info["page_number"])
        
        # Remove duplicates and sort
        key_pages = sorted(list(set(key_pages)))[:10]  # Max 10 pages
        
        gallery_path = create_page_image_gallery(pdf_path, key_pages, gallery_dir)
        
        print("\n✅ Visual verification complete!")
        print(f"   Open {gallery_path} in a browser to inspect pages")
    else:
        print(f"❌ PDF not found: {pdf_path}")