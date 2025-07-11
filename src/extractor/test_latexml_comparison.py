#!/usr/bin/env python3
"""
Module: test_latexml_comparison.py
Description: 3-way comparison test using LaTeXML HTML as gold standard

External Dependencies:
- beautifulsoup4: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- lxml: https://lxml.de/
- marker-pdf: https://github.com/VikParuchuri/marker

Sample Input:
>>> latexml_html = "/path/to/paper_latexml.html"
>>> pdf_path = "/path/to/paper.pdf"

Expected Output:
>>> Comparison results showing structure similarity, content accuracy, and format consistency

Example Usage:
>>> python test_latexml_comparison.py
>>> # Generates detailed comparison report
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple
from bs4 import BeautifulSoup
import re

def extract_latexml_structure(html_path: str) -> Dict[str, Any]:
    """Extract structured content from LaTeXML HTML (gold standard)"""
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    
    # Extract title
    title = soup.find('h1', class_='ltx_title')
    if not title:
        title = soup.find('title')
    title_text = title.get_text(strip=True) if title else "Unknown Title"
    
    # Extract abstract
    abstract = soup.find('div', class_='ltx_abstract')
    if not abstract:
        abstract = soup.find(text=re.compile(r'Abstract', re.I))
        if abstract:
            abstract = abstract.find_parent()
    abstract_text = abstract.get_text(strip=True) if abstract else ""
    
    # Extract sections with hierarchy
    sections = []
    section_elements = soup.find_all(['section', 'div'], class_=re.compile(r'ltx_section|ltx_subsection'))
    
    for elem in section_elements:
        # Find section title
        heading = elem.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if heading:
            section_title = heading.get_text(strip=True)
            # Get section content (first paragraph or so)
            content_elem = elem.find(['p', 'div'], class_='ltx_para')
            content = content_elem.get_text(strip=True)[:500] if content_elem else ""
            
            sections.append({
                "title": section_title,
                "level": int(heading.name[1]),  # h1 -> 1, h2 -> 2, etc.
                "content_preview": content
            })
    
    # Extract equations
    equations = []
    math_elements = soup.find_all(['math', 'span'], class_=re.compile(r'ltx_Math|MathJax'))
    for math in math_elements[:10]:  # First 10 equations
        equations.append(math.get_text(strip=True))
    
    # Extract tables
    tables = []
    table_elements = soup.find_all('table')
    for table in table_elements[:5]:  # First 5 tables
        caption = table.find('caption')
        tables.append({
            "caption": caption.get_text(strip=True) if caption else "No caption",
            "rows": len(table.find_all('tr'))
        })
    
    return {
        "title": title_text,
        "abstract": abstract_text,
        "sections": sections,
        "equations": equations,
        "tables": tables,
        "total_sections": len(sections)
    }

def extract_with_marker_pdf(pdf_path: str) -> Dict[str, Any]:
    """Extract using original marker-pdf package"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
import sys
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/repos/marker')
from marker.convert import convert_single_pdf
from marker.models import load_all_models

# Load models
model_lst = load_all_models()

# Convert PDF
full_text, _, _ = convert_single_pdf(sys.argv[1], model_lst, max_pages=10)
print("MARKER_OUTPUT_START")
print(full_text)
print("MARKER_OUTPUT_END")
""")
        script_path = f.name
    
    try:
        # Run in subprocess to avoid import conflicts
        result = subprocess.run(
            ['/home/graham/workspace/experiments/extractor/.venv/bin/python', script_path, pdf_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"Marker-pdf error: {result.stderr}")
            return {"error": "marker-pdf failed", "stderr": result.stderr}
        
        # Extract markdown from output
        output = result.stdout
        if "MARKER_OUTPUT_START" in output and "MARKER_OUTPUT_END" in output:
            markdown = output.split("MARKER_OUTPUT_START")[1].split("MARKER_OUTPUT_END")[0].strip()
            return parse_markdown_structure(markdown)
        else:
            return {"error": "Could not parse marker-pdf output"}
            
    finally:
        os.unlink(script_path)

def extract_with_extractor(pdf_path: str) -> Dict[str, Any]:
    """Extract using our enhanced extractor"""
    try:
        from extractor.unified_extractor_v2 import extract_to_unified_json
        result = extract_to_unified_json(pdf_path)
        
        # Convert to comparable format
        sections = []
        for section in result.get("vertices", {}).get("sections", []):
            sections.append({
                "title": section.get("title", ""),
                "level": section.get("level", 1),
                "content_preview": section.get("content", "")[:500]
            })
        
        return {
            "title": result.get("vertices", {}).get("documents", [{}])[0].get("title", ""),
            "sections": sections,
            "total_sections": len(sections)
        }
    except Exception as e:
        return {"error": f"Extractor failed: {str(e)}"}

def parse_markdown_structure(markdown: str) -> Dict[str, Any]:
    """Parse markdown to extract structure"""
    lines = markdown.split('\n')
    
    # Extract title (first # heading)
    title = ""
    for line in lines:
        if line.startswith('# ') and not line.startswith('##'):
            title = line[2:].strip()
            break
    
    # Extract sections
    sections = []
    current_section = None
    
    for line in lines:
        if line.startswith('#'):
            # Count the number of # to determine level
            level = len(line) - len(line.lstrip('#'))
            section_title = line.lstrip('#').strip()
            
            if current_section:
                sections.append(current_section)
            
            current_section = {
                "title": section_title,
                "level": level,
                "content_preview": ""
            }
        elif current_section and line.strip():
            # Add to content preview
            if len(current_section["content_preview"]) < 500:
                current_section["content_preview"] += line + " "
    
    if current_section:
        sections.append(current_section)
    
    return {
        "title": title,
        "sections": sections,
        "total_sections": len(sections)
    }

def calculate_similarity(gold: Dict[str, Any], extracted: Dict[str, Any]) -> float:
    """Calculate similarity score between gold standard and extracted content"""
    if "error" in extracted:
        return 0.0
    
    score = 0.0
    total_checks = 0
    
    # Title similarity
    if gold.get("title") and extracted.get("title"):
        gold_title_lower = gold["title"].lower()
        extracted_title_lower = extracted["title"].lower()
        # Check if key words from gold title are in extracted
        title_words = set(gold_title_lower.split())
        extracted_words = set(extracted_title_lower.split())
        common_words = title_words.intersection(extracted_words)
        title_score = len(common_words) / len(title_words) if title_words else 0
        score += title_score
        total_checks += 1
    
    # Section count similarity
    if gold.get("total_sections", 0) > 0:
        section_diff = abs(gold["total_sections"] - extracted.get("total_sections", 0))
        section_score = max(0, 1 - (section_diff / gold["total_sections"]))
        score += section_score
        total_checks += 1
    
    # Section title matching
    gold_sections = gold.get("sections", [])
    extracted_sections = extracted.get("sections", [])
    
    if gold_sections and extracted_sections:
        matched_sections = 0
        for gold_sec in gold_sections[:10]:  # Check first 10 sections
            gold_title_lower = gold_sec["title"].lower()
            for ext_sec in extracted_sections:
                if gold_title_lower in ext_sec["title"].lower() or ext_sec["title"].lower() in gold_title_lower:
                    matched_sections += 1
                    break
        
        section_match_score = matched_sections / min(10, len(gold_sections))
        score += section_match_score
        total_checks += 1
    
    return (score / total_checks) if total_checks > 0 else 0.0

def main():
    """Run comprehensive 3-way comparison"""
    print("🔬 LaTeXML-based 3-Way Comparison Test")
    print("=" * 60)
    
    # File paths
    latexml_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2_latexml.html"
    pdf_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    # Step 1: Extract gold standard from LaTeXML HTML
    print("\n📊 Step 1: Extracting Gold Standard from LaTeXML HTML...")
    gold_standard = extract_latexml_structure(latexml_path)
    print(f"✅ Found: {gold_standard['title']}")
    print(f"   - Sections: {gold_standard['total_sections']}")
    print(f"   - Equations: {len(gold_standard.get('equations', []))}")
    print(f"   - Tables: {len(gold_standard.get('tables', []))}")
    
    # Step 2: Extract with marker-pdf
    print("\n📊 Step 2: Extracting with marker-pdf (baseline)...")
    marker_result = extract_with_marker_pdf(pdf_path)
    if "error" not in marker_result:
        print(f"✅ Marker extraction complete")
        print(f"   - Sections found: {marker_result.get('total_sections', 0)}")
    else:
        print(f"❌ Marker extraction failed: {marker_result['error']}")
    
    # Step 3: Extract with our extractor
    print("\n📊 Step 3: Extracting with enhanced extractor...")
    extractor_result = extract_with_extractor(pdf_path)
    if "error" not in extractor_result:
        print(f"✅ Extractor extraction complete")
        print(f"   - Sections found: {extractor_result.get('total_sections', 0)}")
    else:
        print(f"❌ Extractor extraction failed: {extractor_result['error']}")
    
    # Step 4: Calculate similarity scores
    print("\n📊 Step 4: Similarity Analysis")
    print("-" * 40)
    
    marker_similarity = calculate_similarity(gold_standard, marker_result)
    extractor_similarity = calculate_similarity(gold_standard, extractor_result)
    
    print(f"Marker-PDF similarity to LaTeXML:    {marker_similarity:.2%}")
    print(f"Extractor similarity to LaTeXML:     {extractor_similarity:.2%}")
    
    # Detailed comparison
    print("\n📊 Detailed Section Comparison (first 5 sections):")
    print("-" * 60)
    
    print("LaTeXML (Gold Standard):")
    for i, section in enumerate(gold_standard["sections"][:5]):
        print(f"  {i+1}. [{section['level']}] {section['title']}")
    
    print("\nMarker-PDF:")
    if "error" not in marker_result:
        for i, section in enumerate(marker_result.get("sections", [])[:5]):
            print(f"  {i+1}. [{section['level']}] {section['title']}")
    else:
        print(f"  Error: {marker_result['error']}")
    
    print("\nExtractor:")
    if "error" not in extractor_result:
        for i, section in enumerate(extractor_result.get("sections", [])[:5]):
            print(f"  {i+1}. [{section['level']}] {section['title']}")
    else:
        print(f"  Error: {extractor_result['error']}")
    
    # Final verdict
    print("\n" + "=" * 60)
    print("🎯 VERDICT:")
    
    if extractor_similarity > marker_similarity:
        print(f"✅ Extractor OUTPERFORMS marker-pdf by {(extractor_similarity - marker_similarity):.1%}")
    elif extractor_similarity == marker_similarity:
        print("➖ Extractor matches marker-pdf performance")
    else:
        print(f"❌ Extractor underperforms marker-pdf by {(marker_similarity - extractor_similarity):.1%}")
    
    print("\n💡 KEY INSIGHT:")
    print("LaTeXML provides the most accurate representation since it works")
    print("from the original LaTeX source, preserving semantic structure.")
    print("This makes it an ideal gold standard for benchmarking extraction quality.")
    
    # Save detailed results
    results = {
        "gold_standard": gold_standard,
        "marker_result": marker_result,
        "extractor_result": extractor_result,
        "scores": {
            "marker_similarity": marker_similarity,
            "extractor_similarity": extractor_similarity
        }
    }
    
    output_path = "/home/graham/workspace/experiments/extractor/data/output/latexml_comparison_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📝 Detailed results saved to: {output_path}")

if __name__ == "__main__":
    main()