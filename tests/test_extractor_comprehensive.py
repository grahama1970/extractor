#!/usr/bin/env python3
"""
Module: test_extractor_comprehensive.py
Description: Comprehensive test to ensure extractor adds features on top of marker-pdf without changing core

This test ensures:
1. Original marker-pdf functionality is preserved for PDFs
2. Unified JSON is added on top (not replacing) marker's output
3. HTML/DOCX extraction produces compatible JSON structure
4. All formats produce reasonably similar outputs

External Dependencies:
- marker-pdf: Original PDF extraction (repos/marker)
- extractor: Enhanced version with unified JSON
- subprocess: For isolated marker-pdf execution

Sample Input:
>>> test_file = "2505.03335v2"  # Scientific paper in multiple formats

Expected Output:
>>> # All formats should produce similar unified JSON structure
>>> # PDF extraction should match original marker-pdf quality

Example Usage:
>>> python test_extractor_comprehensive.py
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import tempfile
import hashlib


def run_original_marker_pdf(pdf_path: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Run original marker-pdf in isolated subprocess to extract PDF.
    Returns: (markdown_content, metadata)
    """
    print(f"\n📘 Running ORIGINAL marker-pdf on: {Path(pdf_path).name}")
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Path to original marker
            marker_path = "/home/graham/workspace/experiments/extractor/repos/marker"
            
            # Create isolated Python script to run marker
            runner_script = os.path.join(temp_dir, "run_marker.py")
            with open(runner_script, 'w') as f:
                f.write(f"""
import sys
sys.path.insert(0, '{marker_path}')

# Now import from original marker
from marker.convert import convert_single_pdf
from marker.schema import Page
from marker.models import load_all_models

# Load models
model_lst = load_all_models()

# Convert PDF
full_text, images, out_meta = convert_single_pdf(
    '{pdf_path}',
    model_lst,
    max_pages=10,
    langs=['English']
)

# Save output
import json
with open('{temp_dir}/output.md', 'w') as f:
    f.write(full_text)
with open('{temp_dir}/metadata.json', 'w') as f:
    json.dump(out_meta, f, default=str)

print("SUCCESS")
""")
            
            # Run the script in subprocess
            env = os.environ.copy()
            env['PYTHONPATH'] = marker_path
            
            start_time = time.time()
            result = subprocess.run(
                [sys.executable, runner_script],
                capture_output=True,
                text=True,
                env=env,
                timeout=60
            )
            elapsed = time.time() - start_time
            
            if "SUCCESS" in result.stdout:
                # Read outputs
                md_path = os.path.join(temp_dir, "output.md")
                meta_path = os.path.join(temp_dir, "metadata.json")
                
                markdown = ""
                metadata = {}
                
                if os.path.exists(md_path):
                    with open(md_path, 'r') as f:
                        markdown = f.read()
                
                if os.path.exists(meta_path):
                    with open(meta_path, 'r') as f:
                        metadata = json.load(f)
                
                print(f"   ✅ Success: {len(markdown)} chars extracted in {elapsed:.2f}s")
                return markdown, metadata
            else:
                print(f"   ❌ Failed: {result.stderr}")
                return None, None
                
        except subprocess.TimeoutExpired:
            print("   ❌ Timeout: marker-pdf took too long")
            return None, None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None, None


def convert_marker_to_unified_json(markdown: str, metadata: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    """
    Convert marker-pdf output to unified JSON structure.
    This ADDS structure on top of marker's output without changing it.
    """
    # Initialize unified structure
    doc_key = hashlib.md5(source_file.encode()).hexdigest()[:8]
    
    result = {
        "vertices": {
            "documents": [{
                "_key": f"doc_{doc_key}",
                "_id": f"documents/doc_{doc_key}",
                "title": metadata.get("title", Path(source_file).stem),
                "source_file": source_file,
                "format": "pdf",
                "page_count": metadata.get("pages", 0),
                "created_at": metadata.get("timestamp", ""),
                "marker_metadata": metadata  # Preserve original marker metadata
            }],
            "sections": [],
            "entities": [],
            "topics": []
        },
        "edges": {
            "document_sections": [],
            "section_hierarchy": [],
            "entity_mentions": [],
            "topic_assignments": []
        },
        "original_markdown": markdown  # Preserve original marker output
    }
    
    # Parse markdown to extract sections
    import re
    lines = markdown.split('\n')
    current_section = None
    section_content = []
    section_stack = []
    
    for line in lines:
        # Check for markdown headers
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            # Save previous section
            if current_section and section_content:
                current_section["content"] = '\n'.join(section_content).strip()
                result["vertices"]["sections"].append(current_section)
                section_content = []
            
            # Create new section
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            
            # Manage hierarchy
            while section_stack and section_stack[-1][1] >= level:
                section_stack.pop()
            
            sec_key = hashlib.md5(f"{title}{len(result['vertices']['sections'])}".encode()).hexdigest()[:8]
            parent_key = section_stack[-1][0] if section_stack else None
            
            current_section = {
                "_key": f"sec_{sec_key}",
                "_id": f"sections/sec_{sec_key}",
                "title": title,
                "level": level,
                "content": "",
                "parent": f"sec_{parent_key}" if parent_key else None
            }
            
            section_stack.append((sec_key, level))
            
            # Add edges
            result["edges"]["document_sections"].append({
                "_from": f"documents/doc_{doc_key}",
                "_to": f"sections/sec_{sec_key}"
            })
            
            if parent_key:
                result["edges"]["section_hierarchy"].append({
                    "_from": f"sections/sec_{parent_key}",
                    "_to": f"sections/sec_{sec_key}"
                })
        else:
            # Regular content
            if line.strip():
                section_content.append(line)
    
    # Save last section
    if current_section and section_content:
        current_section["content"] = '\n'.join(section_content).strip()
        result["vertices"]["sections"].append(current_section)
    
    return result


def test_extractor_on_format(file_path: str) -> Optional[Dict[str, Any]]:
    """Test extractor on any format"""
    print(f"\n🔷 Testing EXTRACTOR on: {Path(file_path).name}")
    
    try:
        from extractor.unified_extractor import extract_to_unified_json
        
        start_time = time.time()
        result = extract_to_unified_json(file_path)
        elapsed = time.time() - start_time
        
        # Calculate metrics
        section_count = len(result.get('vertices', {}).get('sections', []))
        content_size = sum(len(s.get('content', '')) for s in result.get('vertices', {}).get('sections', []))
        
        print(f"   ✅ Success: {section_count} sections, {content_size:,} chars in {elapsed:.2f}s")
        
        return {
            'result': result,
            'section_count': section_count,
            'content_size': content_size,
            'extraction_time': elapsed
        }
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_results(results: Dict[str, Any]) -> bool:
    """Compare extraction results across methods and formats"""
    print("\n" + "="*70)
    print("📊 COMPREHENSIVE COMPARISON")
    print("="*70)
    
    # Summary table
    print("\n| Method/Format | Sections | Content | Time | Status |")
    print("|---------------|----------|---------|------|--------|")
    
    for key, data in results.items():
        if data and 'error' not in data:
            sections = data.get('section_count', 0)
            content = data.get('content_size', 0)
            time_str = f"{data.get('extraction_time', 0):.2f}s"
            print(f"| {key:13} | {sections:8} | {content:7,} | {time_str:4} | ✅ |")
        else:
            print(f"| {key:13} | -        | -       | -    | ❌ |")
    
    # Analyze marker vs extractor on PDF
    print("\n📈 MARKER vs EXTRACTOR (PDF) COMPARISON:")
    
    if 'marker_pdf' in results and 'extractor_pdf' in results:
        marker = results['marker_pdf']
        extractor = results['extractor_pdf']
        
        if marker and extractor:
            # Content comparison
            marker_content = marker['content_size']
            extractor_content = extractor['content_size']
            ratio = extractor_content / marker_content if marker_content > 0 else 0
            
            print(f"   Content extraction ratio: {ratio:.2f}x")
            print(f"   Marker sections: {marker['section_count']}")
            print(f"   Extractor sections: {extractor['section_count']}")
            
            if ratio >= 0.9:
                print("   ✅ Extractor preserves marker-pdf quality")
            else:
                print("   ❌ Extractor extracts less content than marker-pdf")
                print("   This suggests core marker functionality may be broken!")
    
    # Analyze format consistency
    print("\n📋 FORMAT CONSISTENCY (Extractor):")
    
    format_results = {k: v for k, v in results.items() if k.startswith('extractor_') and v}
    if len(format_results) > 1:
        sections = [r['section_count'] for r in format_results.values()]
        contents = [r['content_size'] for r in format_results.values()]
        
        avg_sections = sum(sections) / len(sections)
        avg_content = sum(contents) / len(contents)
        
        max_section_dev = max(abs(s - avg_sections) / avg_sections for s in sections) if avg_sections > 0 else 1
        max_content_dev = max(abs(c - avg_content) / avg_content for c in contents) if avg_content > 0 else 1
        
        print(f"   Section count deviation: {max_section_dev:.1%}")
        print(f"   Content size deviation: {max_content_dev:.1%}")
        
        if max_section_dev < 0.3 and max_content_dev < 0.3:
            print("   ✅ Formats produce reasonably similar outputs")
            return True
        else:
            print("   ❌ Formats produce inconsistent outputs")
            return False
    
    return False


def main():
    """Main comprehensive test function"""
    print("🧪 EXTRACTOR COMPREHENSIVE TEST")
    print("="*70)
    print("Testing principle: Extractor adds features ON TOP of marker-pdf")
    print("NOT changing core marker-pdf internals!")
    print("="*70)
    
    # Test files
    base_path = "/home/graham/workspace/experiments/extractor/data/input"
    test_name = "2505.03335v2"
    
    results = {}
    
    # 1. Test original marker-pdf on PDF
    pdf_path = os.path.join(base_path, f"{test_name}.pdf")
    if os.path.exists(pdf_path):
        markdown, metadata = run_original_marker_pdf(pdf_path)
        if markdown:
            # Convert to unified JSON
            unified = convert_marker_to_unified_json(markdown, metadata or {}, pdf_path)
            
            results['marker_pdf'] = {
                'result': unified,
                'section_count': len(unified['vertices']['sections']),
                'content_size': len(markdown),
                'extraction_time': 0,
                'original_markdown': markdown
            }
            
            # Save for inspection
            output_path = os.path.join(base_path, f"{test_name}_marker_unified.json")
            with open(output_path, 'w') as f:
                json.dump(unified, f, indent=2)
            print(f"   💾 Saved unified JSON: {output_path}")
    
    # 2. Test extractor on all formats
    formats = {
        'pdf': os.path.join(base_path, f"{test_name}.pdf"),
        'html': os.path.join(base_path, f"{test_name}.html"),
        'docx': os.path.join(base_path, f"{test_name}.docx")
    }
    
    for fmt, path in formats.items():
        if os.path.exists(path):
            result = test_extractor_on_format(path)
            if result:
                results[f'extractor_{fmt}'] = result
                
                # Save output
                output_path = os.path.join(base_path, f"{test_name}_extractor_{fmt}.json")
                with open(output_path, 'w') as f:
                    json.dump(result['result'], f, indent=2)
    
    # 3. Compare all results
    all_good = compare_results(results)
    
    # 4. Final verdict
    print("\n" + "="*70)
    print("🏁 FINAL VERDICT")
    print("="*70)
    
    # Check if marker-pdf core is preserved
    marker_preserved = False
    if 'marker_pdf' in results and 'extractor_pdf' in results:
        if results['marker_pdf'] and results['extractor_pdf']:
            ratio = results['extractor_pdf']['content_size'] / results['marker_pdf']['content_size']
            marker_preserved = ratio >= 0.9
    
    if marker_preserved:
        print("✅ Marker-pdf core functionality is PRESERVED")
    else:
        print("❌ Marker-pdf core functionality appears BROKEN")
        print("   Extractor must use original marker code for PDF extraction!")
    
    if all_good:
        print("✅ Format consistency is ACCEPTABLE")
    else:
        print("❌ Format consistency needs improvement")
    
    # Recommendations
    print("\n📋 RECOMMENDATIONS:")
    if not marker_preserved:
        print("1. DO NOT modify marker-pdf's core PDF extraction")
        print("2. Import and use marker's convert_single_pdf directly")
        print("3. Only ADD unified JSON structure AFTER marker extracts content")
    
    print("\n🔧 Implementation pattern:")
    print("```python")
    print("# For PDFs: Use original marker-pdf")
    print("from marker.convert import convert_single_pdf")
    print("markdown, images, metadata = convert_single_pdf(pdf_path, models)")
    print("")
    print("# Then ADD unified JSON on top")
    print("unified_json = convert_to_unified_format(markdown, metadata)")
    print("```")
    
    exit(0 if marker_preserved and all_good else 1)


if __name__ == "__main__":
    main()