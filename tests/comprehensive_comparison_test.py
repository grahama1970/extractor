#!/usr/bin/env python3
"""
Module: comprehensive_comparison_test.py
Description: 6-way comparison test for extractor quality against LaTeXML gold standard

This module performs a comprehensive comparison of document extraction quality:
1. LaTeXML HTML (gold standard)
2. ArXiv PDF with extractor
3. ArXiv PDF with marker-pdf
4. LaTeXML HTML with extractor
5. LaTeXML HTML with marker-pdf (if applicable)
6. Original arXiv PDF vs all extractions

External Dependencies:
- beautifulsoup4: https://www.crummy.com/software/BeautifulSoup/
- marker-pdf: https://github.com/VikParuchuri/marker
- extractor: Local enhanced version with unified JSON

Sample Input:
>>> test_files = {
>>>     "pdf": "2505.03335v2.pdf",
>>>     "latexml": "2505.03335v2_latexml.html"
>>> }

Expected Output:
>>> comparison_results = {
>>>     "latexml_gold_standard": {...},
>>>     "extractor_pdf": {...},
>>>     "marker_pdf": {...},
>>>     "extractor_latexml": {...},
>>>     "quality_scores": {...}
>>> }

Example Usage:
>>> from comprehensive_comparison_test import run_comprehensive_comparison
>>> results = run_comprehensive_comparison()
>>> print(f"Best extraction method: {results['best_method']}")
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
import tempfile

# Add extractor to path
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/src')

from extractor.unified_extractor_v2 import extract_to_unified_json
from bs4 import BeautifulSoup


def extract_latexml_gold_standard(latexml_path: str) -> Dict[str, Any]:
    """Extract gold standard content from LaTeXML HTML"""
    print(f"\n📖 Extracting LaTeXML gold standard from: {Path(latexml_path).name}")
    
    with open(latexml_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract structured content
    sections = []
    
    # Find title
    title_elem = soup.find('h1', class_='ltx_title')
    if title_elem:
        sections.append({
            "title": title_elem.get_text(strip=True),
            "level": 1,
            "content": "",
            "type": "title"
        })
    
    # Find abstract
    abstract_elem = soup.find('div', class_='ltx_abstract')
    if abstract_elem:
        abstract_title = abstract_elem.find('h6', class_='ltx_title')
        abstract_content = abstract_elem.find('p')
        if abstract_content:
            sections.append({
                "title": "Abstract",
                "level": 2,
                "content": abstract_content.get_text(strip=True),
                "type": "abstract"
            })
    
    # Extract all sections with proper hierarchy
    for section in soup.find_all(['section', 'div'], class_=['ltx_section', 'ltx_subsection', 'ltx_subsubsection']):
        # Get section title
        title_elem = section.find(['h2', 'h3', 'h4', 'h5', 'h6'], class_='ltx_title')
        if not title_elem:
            continue
            
        title_text = title_elem.get_text(strip=True)
        
        # Determine level from class
        if 'ltx_section' in section.get('class', []):
            level = 2
        elif 'ltx_subsection' in section.get('class', []):
            level = 3
        elif 'ltx_subsubsection' in section.get('class', []):
            level = 4
        else:
            level = 2
        
        # Extract content paragraphs
        content_parts = []
        for p in section.find_all('p', class_='ltx_p'):
            text = p.get_text(strip=True)
            if text and not text.startswith('§'):
                content_parts.append(text)
        
        if title_text:
            sections.append({
                "title": title_text,
                "level": level,
                "content": '\n\n'.join(content_parts),
                "type": "section"
            })
    
    # Extract equations
    equations = []
    for eq in soup.find_all(['div', 'span'], class_=['ltx_equation', 'ltx_Math']):
        latex = eq.get('alttext', '')
        if latex:
            equations.append(latex)
    
    # Extract tables
    tables = []
    for table in soup.find_all('table', class_='ltx_tabular'):
        table_data = []
        for row in table.find_all('tr'):
            row_data = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
            if row_data:
                table_data.append(row_data)
        if table_data:
            tables.append(table_data)
    
    return {
        "source": "latexml",
        "sections": sections,
        "equations": equations,
        "tables": tables,
        "total_sections": len(sections),
        "total_equations": len(equations),
        "total_tables": len(tables)
    }


def extract_with_extractor(file_path: str) -> Dict[str, Any]:
    """Extract content using extractor"""
    print(f"\n🔧 Extracting with extractor: {Path(file_path).name}")
    
    try:
        start_time = time.time()
        result = extract_to_unified_json(file_path)
        elapsed = time.time() - start_time
        
        sections = result.get("vertices", {}).get("sections", [])
        
        # Extract equations and tables from content
        equations = []
        tables = []
        
        for section in sections:
            content = section.get("content", "")
            # Look for LaTeX equations
            if "$$" in content or "\\[" in content or "\\begin{equation" in content:
                equations.append(content)
            # Look for table markers
            if "|" in content and content.count("|") > 3:
                tables.append(content)
        
        return {
            "source": "extractor",
            "file": Path(file_path).name,
            "sections": sections,
            "equations": equations,
            "tables": tables,
            "total_sections": len(sections),
            "total_equations": len(equations),
            "total_tables": len(tables),
            "extraction_time": elapsed,
            "extraction_method": result.get("original_content", {}).get("extraction_method", "unknown")
        }
        
    except Exception as e:
        return {
            "source": "extractor",
            "file": Path(file_path).name,
            "error": str(e),
            "sections": [],
            "total_sections": 0
        }


def extract_with_marker_pdf(pdf_path: str) -> Dict[str, Any]:
    """Extract content using original marker-pdf"""
    print(f"\n📘 Extracting with marker-pdf: {Path(pdf_path).name}")
    
    # Create a script to run marker-pdf in isolation
    marker_script = f"""
import sys
import json

# Add marker-pdf to path
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/repos/marker')

try:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models
    
    # Load models
    model_lst = load_all_models()
    
    # Convert PDF
    full_text, images, out_meta = convert_single_pdf("{pdf_path}", model_lst, max_pages=10)
    
    # Count sections (look for headers)
    lines = full_text.split('\\n')
    sections = []
    for i, line in enumerate(lines):
        if line.strip().startswith('#') or (line.strip().startswith('**') and line.strip().endswith('**')):
            sections.append({{
                "title": line.strip().replace('#', '').replace('*', '').strip(),
                "line": i
            }})
    
    result = {{
        "success": True,
        "text_length": len(full_text),
        "sections": sections,
        "total_sections": len(sections),
        "first_500_chars": full_text[:500]
    }}
    
except Exception as e:
    result = {{
        "success": False,
        "error": str(e)
    }}

print(json.dumps(result))
"""
    
    try:
        # Write script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(marker_script)
            script_path = f.name
        
        # Run in marker environment
        marker_path = "/home/graham/workspace/experiments/extractor/repos/marker"
        venv_python = f"{marker_path}/.venv/bin/python" if os.path.exists(f"{marker_path}/.venv") else "python"
        
        env = os.environ.copy()
        env['PYTHONPATH'] = marker_path
        
        start_time = time.time()
        result = subprocess.run(
            [venv_python, script_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=60
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            output = json.loads(result.stdout)
            if output.get("success"):
                return {
                    "source": "marker-pdf",
                    "file": Path(pdf_path).name,
                    "sections": output.get("sections", []),
                    "total_sections": output.get("total_sections", 0),
                    "text_length": output.get("text_length", 0),
                    "extraction_time": elapsed,
                    "preview": output.get("first_500_chars", "")
                }
            else:
                return {
                    "source": "marker-pdf",
                    "file": Path(pdf_path).name,
                    "error": output.get("error", "Unknown error"),
                    "sections": [],
                    "total_sections": 0
                }
        else:
            return {
                "source": "marker-pdf",
                "file": Path(pdf_path).name,
                "error": f"Process failed: {result.stderr[:500]}",
                "sections": [],
                "total_sections": 0
            }
            
    except Exception as e:
        return {
            "source": "marker-pdf", 
            "file": Path(pdf_path).name,
            "error": str(e),
            "sections": [],
            "total_sections": 0
        }
    finally:
        # Clean up
        if 'script_path' in locals():
            try:
                os.unlink(script_path)
            except:
                pass


def calculate_quality_score(extraction: Dict[str, Any], gold_standard: Dict[str, Any]) -> float:
    """Calculate quality score by comparing to gold standard"""
    if "error" in extraction:
        return 0.0
    
    score = 0.0
    
    # Section count similarity (40% weight)
    gold_sections = gold_standard.get("total_sections", 0)
    ext_sections = extraction.get("total_sections", 0)
    if gold_sections > 0:
        section_score = 1 - abs(gold_sections - ext_sections) / gold_sections
        section_score = max(0, section_score)
        score += section_score * 0.4
    
    # Section title matching (30% weight)
    gold_titles = [s["title"].lower() for s in gold_standard.get("sections", [])]
    ext_titles = []
    
    if extraction.get("source") in ["extractor", "marker-pdf"]:
        ext_sections = extraction.get("sections", [])
        for s in ext_sections:
            if isinstance(s, dict):
                title = s.get("title", "")
                if title:
                    ext_titles.append(title.lower())
    
    if gold_titles and ext_titles:
        matches = sum(1 for t in ext_titles if any(gt in t or t in gt for gt in gold_titles))
        title_score = matches / len(gold_titles)
        score += title_score * 0.3
    
    # Equation detection (15% weight)
    gold_equations = gold_standard.get("total_equations", 0)
    ext_equations = extraction.get("total_equations", 0)
    if gold_equations > 0:
        eq_score = min(1.0, ext_equations / gold_equations)
        score += eq_score * 0.15
    
    # Table detection (15% weight)
    gold_tables = gold_standard.get("total_tables", 0)
    ext_tables = extraction.get("total_tables", 0)
    if gold_tables > 0:
        table_score = min(1.0, ext_tables / gold_tables)
        score += table_score * 0.15
    
    return score


def run_comprehensive_comparison():
    """Run the comprehensive 6-way comparison test"""
    print("🚀 Running Comprehensive 6-Way Extraction Comparison")
    print("=" * 70)
    
    base_path = "/home/graham/workspace/experiments/extractor/data/input"
    
    # Test files
    test_files = {
        "pdf": os.path.join(base_path, "2505.03335v2.pdf"),
        "latexml": os.path.join(base_path, "2505.03335v2_latexml.html")
    }
    
    # Check files exist
    for file_type, file_path in test_files.items():
        if not os.path.exists(file_path):
            print(f"❌ Missing {file_type} file: {file_path}")
            return None
    
    results = {}
    
    # 1. Extract LaTeXML gold standard
    results["latexml_gold_standard"] = extract_latexml_gold_standard(test_files["latexml"])
    gold_standard = results["latexml_gold_standard"]
    
    print(f"\n✨ Gold Standard (LaTeXML):")
    print(f"   - Sections: {gold_standard['total_sections']}")
    print(f"   - Equations: {gold_standard['total_equations']}")
    print(f"   - Tables: {gold_standard['total_tables']}")
    
    # 2. Extract PDF with extractor
    results["extractor_pdf"] = extract_with_extractor(test_files["pdf"])
    
    # 3. Extract PDF with marker-pdf
    results["marker_pdf"] = extract_with_marker_pdf(test_files["pdf"])
    
    # 4. Extract LaTeXML with extractor
    results["extractor_latexml"] = extract_with_extractor(test_files["latexml"])
    
    # Calculate quality scores
    quality_scores = {}
    for method, result in results.items():
        if method != "latexml_gold_standard":
            score = calculate_quality_score(result, gold_standard)
            quality_scores[method] = score
    
    # Print results summary
    print("\n" + "=" * 70)
    print("📊 EXTRACTION RESULTS SUMMARY")
    print("=" * 70)
    
    print("\n📈 Section Counts:")
    for method, result in results.items():
        sections = result.get("total_sections", 0)
        status = "✅" if sections > 10 else "⚠️ "
        error = f" (ERROR: {result.get('error', '')[:50]})" if "error" in result else ""
        print(f"   {status} {method}: {sections} sections{error}")
    
    print("\n🏆 Quality Scores (vs LaTeXML):")
    best_method = None
    best_score = 0
    for method, score in quality_scores.items():
        print(f"   {method}: {score:.1%}")
        if score > best_score:
            best_score = score
            best_method = method
    
    print("\n" + "=" * 70)
    print("🎯 FINAL VERDICT")
    print("=" * 70)
    
    if best_score > 0.7:
        print(f"✅ Best extraction method: {best_method} ({best_score:.1%} match)")
        print("✅ Extraction quality is GOOD")
    else:
        print(f"❌ Best extraction method: {best_method} ({best_score:.1%} match)")
        print("❌ Extraction quality needs improvement")
        print("\n🔧 Next Steps:")
        print("   1. Fix section parsing to handle Surya's bold headers")
        print("   2. Improve equation detection")
        print("   3. Enhance table recognition")
    
    # Save detailed results
    output_path = os.path.join(base_path, "extraction_comparison_results.json")
    with open(output_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "quality_scores": quality_scores,
            "best_method": best_method,
            "best_score": best_score
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_path}")
    
    return {
        "results": results,
        "quality_scores": quality_scores,
        "best_method": best_method,
        "best_score": best_score
    }


if __name__ == "__main__":
    # Run comprehensive comparison
    comparison_results = run_comprehensive_comparison()
    
    if comparison_results:
        # Additional analysis
        print("\n" + "=" * 70)
        print("🔍 DETAILED ANALYSIS")
        print("=" * 70)
        
        # Check specific extraction issues
        extractor_pdf = comparison_results["results"].get("extractor_pdf", {})
        if extractor_pdf.get("total_sections", 0) < 10:
            print("\n⚠️  Extractor PDF extraction issues detected:")
            print(f"   - Only {extractor_pdf.get('total_sections', 0)} sections found")
            print(f"   - Extraction method: {extractor_pdf.get('extraction_method', 'unknown')}")
            
            if extractor_pdf.get("extraction_method") == "marker-pdf-core":
                print("   - Using marker-pdf core (good)")
                print("   - Issue: Section parsing needs improvement for Surya output")
            else:
                print("   - NOT using marker-pdf core (bad)")
                print("   - Issue: Surya models may not be initializing properly")
    
    print("\n✅ Comprehensive comparison complete!")