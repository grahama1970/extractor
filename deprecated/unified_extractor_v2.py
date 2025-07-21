#!/usr/bin/env python3
"""
Module: unified_extractor_v2.py
Description: Unified document extraction that properly uses marker-pdf core for PDFs

This module ensures:
1. PDFs are extracted using the ORIGINAL marker-pdf functionality (now in extractor.core)
2. Unified JSON structure is ADDED on top, not replacing marker's output
3. All formats produce consistent JSON structure for ArangoDB

External Dependencies:
- extractor.core: Contains the original marker-pdf functionality
- beautifulsoup4: https://www.crummy.com/software/BeautifulSoup/
- python-docx: https://python-docx.readthedocs.io/
- chardet: https://pypi.org/project/chardet/

Sample Input:
>>> document_path = "/path/to/document.pdf"  # or .html, .docx

Expected Output:
>>> result = {
>>>     "vertices": {
>>>         "documents": [...],
>>>         "sections": [...],
>>>         "entities": [...],
>>>         "topics": [...]
>>>     },
>>>     "edges": {
>>>         "document_sections": [...],
>>>         "section_hierarchy": [...],
>>>         "entity_mentions": [...],
>>>         "topic_assignments": [...]
>>>     },
>>>     "original_content": {
>>>         "format": "markdown",  # For PDFs
>>>         "content": "..."       # Original marker-pdf output preserved
>>>     }
>>> }

Example Usage:
>>> from extractor.unified_extractor_v2 import extract_to_unified_json
>>> result = extract_to_unified_json("/path/to/document.pdf")
>>> print(f"Extracted {len(result['vertices']['sections'])} sections")
"""

import os
import re
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import tempfile

# Import the ORIGINAL marker-pdf functionality (now in extractor.core)
from extractor.core.converters.pdf import convert_single_pdf


def generate_key(content: str, prefix: str = "") -> str:
    """Generate a unique key based on content hash"""
    hash_obj = hashlib.md5((prefix + content).encode())
    return hash_obj.hexdigest()[:8]


def extract_pdf_to_markdown(pdf_path: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract PDF using the ORIGINAL marker-pdf functionality.
    This preserves the core marker-pdf behavior without modification.
    
    Returns: (markdown_content, metadata)
    """
    print(f"   🔸 Using marker-pdf core to extract: {Path(pdf_path).name}")
    
    try:
        # Use the original marker-pdf converter (now in extractor.core)
        # This is the EXACT same code as marker-pdf, just moved to extractor package
        result = convert_single_pdf(
            pdf_path,
            max_pages=None,  # Process all pages
            langs=["English"],  # Can be configured
            ocr_all_pages=False  # Use OCR only when needed
        )
        
        # Handle both string and MarkdownOutput object returns
        if isinstance(result, str):
            markdown_content = result
            page_count = 0
        else:
            # Newer versions return a MarkdownOutput object
            markdown_content = result.text_content if hasattr(result, 'text_content') else str(result)
            page_count = len(result.pages) if hasattr(result, 'pages') else 0
        
        # Extract metadata
        metadata = {
            "extraction_method": "marker-pdf-core",
            "timestamp": datetime.now().isoformat(),
            "file_size": os.path.getsize(pdf_path),
            "page_count": page_count
        }
        
        return markdown_content, metadata
        
    except Exception as e:
        # If marker-pdf core fails, we should NOT fall back to PyMuPDF
        # as the user explicitly said this is a failure
        raise RuntimeError(f"Marker-PDF core extraction failed: {e}")


def parse_surya_sections(markdown: str) -> List[Dict[str, Any]]:
    """
    Enhanced parser for Surya's markdown output format.
    Handles both markdown headers (#) and bold headers (**) with breadcrumb comments.
    """
    sections = []
    lines = markdown.split('\n')
    current_content = []
    last_section_idx = -1
    
    # Track section hierarchy
    section_stack = []  # [(title, level, index), ...]
    
    for i, line in enumerate(lines):
        # Skip empty lines for header detection
        if not line.strip():
            if last_section_idx >= 0:
                current_content.append(line)
            continue
        
        # Check for section breadcrumb (Surya's hint about section structure)
        breadcrumb_match = re.search(r'<!-- SECTION_BREADCRUMB: (\[.*?\]) -->', line)
        breadcrumb_data = None
        if breadcrumb_match:
            try:
                breadcrumb_data = json.loads(breadcrumb_match.group(1))
            except:
                pass
        
        # Check for headers
        header_found = False
        title = None
        level = None
        
        # Method 1: Standard markdown headers
        md_header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if md_header_match:
            level = len(md_header_match.group(1))
            title = md_header_match.group(2).strip()
            header_found = True
        
        # Method 2: Bold text headers (Surya format)
        if not header_found:
            # Look for bold text that could be a header
            bold_match = re.match(r'^\*\*(.+?)\*\*\s*$', line)
            if bold_match:
                title = bold_match.group(1).strip()
                
                # Use breadcrumb data to determine level if available
                if breadcrumb_data and isinstance(breadcrumb_data, list) and breadcrumb_data:
                    # Get level from the last item in breadcrumb
                    last_crumb = breadcrumb_data[-1]
                    if isinstance(last_crumb, dict) and 'level' in last_crumb:
                        level = last_crumb['level']
                    else:
                        level = 2  # Default
                else:
                    # Heuristic: Check if this looks like a main title
                    if i < 20 and (
                        len(title) > 30 or 
                        any(keyword in title.lower() for keyword in ['abstract', 'introduction', 'conclusion'])
                    ):
                        level = 1
                    else:
                        level = 2
                
                header_found = True
        
        # Method 3: Check the previous line for a header if current line is breadcrumb
        if not header_found and breadcrumb_data and i > 0:
            prev_line = lines[i-1].strip()
            bold_match = re.match(r'^\*\*(.+?)\*\*\s*$', prev_line)
            if bold_match:
                title = bold_match.group(1).strip()
                # Use breadcrumb level
                if isinstance(breadcrumb_data, list) and breadcrumb_data:
                    last_crumb = breadcrumb_data[-1]
                    if isinstance(last_crumb, dict) and 'level' in last_crumb:
                        level = last_crumb['level']
                    else:
                        level = 2
                else:
                    level = 2
                header_found = True
                # Skip the breadcrumb line
                continue
        
        if header_found and title and len(title) > 1:
            # Save content for previous section
            if last_section_idx >= 0 and current_content:
                sections[last_section_idx]["content"] = '\n'.join(current_content).strip()
                current_content = []
            
            # Update section stack for hierarchy
            while section_stack and section_stack[-1][1] >= level:
                section_stack.pop()
            
            parent_idx = section_stack[-1][2] if section_stack else None
            
            # Create new section
            section = {
                "title": title,
                "level": level,
                "content": "",
                "line_number": i + 1,
                "parent_index": parent_idx
            }
            
            sections.append(section)
            last_section_idx = len(sections) - 1
            section_stack.append((title, level, last_section_idx))
            
        else:
            # Regular content line
            if last_section_idx >= 0:
                current_content.append(line)
            elif not sections and i < 10:
                # Check if this might be a title without markers
                if line.strip() and len(line.strip()) > 10 and len(line.strip()) < 100:
                    # Could be a title at the beginning
                    sections.append({
                        "title": line.strip(),
                        "level": 1,
                        "content": "",
                        "line_number": i + 1,
                        "parent_index": None
                    })
                    last_section_idx = 0
    
    # Save content for last section
    if last_section_idx >= 0 and current_content:
        sections[last_section_idx]["content"] = '\n'.join(current_content).strip()
    
    # If no sections were found, create one from all content
    if not sections:
        sections.append({
            "title": "Document Content",
            "level": 1,
            "content": markdown,
            "line_number": 1,
            "parent_index": None
        })
    
    return sections


def markdown_to_unified_json(
    markdown: str, 
    metadata: Dict[str, Any], 
    source_file: str,
    format_type: str = "pdf"
) -> Dict[str, Any]:
    """
    Convert markdown (from marker-pdf) to unified JSON structure.
    Uses enhanced Surya-aware parsing.
    """
    doc_key = generate_key(source_file, "doc_")
    
    # Initialize unified structure
    result = {
        "vertices": {
            "documents": [{
                "_key": doc_key,
                "_id": f"documents/{doc_key}",
                "title": metadata.get("title", Path(source_file).stem),
                "source_file": source_file,
                "format": format_type,
                "created_at": datetime.now().isoformat(),
                "extraction_metadata": metadata
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
        "original_content": {
            "format": "markdown",
            "content": markdown,  # Preserve original marker-pdf output
            "extraction_method": metadata.get("extraction_method", "unknown")
        }
    }
    
    # Parse sections with enhanced parser
    parsed_sections = parse_surya_sections(markdown)
    
    # Convert to graph structure
    section_keys = []
    for section in parsed_sections:
        sec_key = generate_key(section["title"] + str(section["line_number"]), "sec_")
        section_keys.append(sec_key)
        
        parent_key = None
        if section["parent_index"] is not None:
            parent_key = section_keys[section["parent_index"]]
        
        # Create section vertex
        section_vertex = {
            "_key": sec_key,
            "_id": f"sections/{sec_key}",
            "title": section["title"],
            "level": section["level"],
            "content": section["content"],
            "parent": parent_key,
            "line_number": section["line_number"]
        }
        
        result["vertices"]["sections"].append(section_vertex)
        
        # Create edges
        if parent_key:
            result["edges"]["section_hierarchy"].append({
                "_from": f"sections/{parent_key}",
                "_to": f"sections/{sec_key}"
            })
        else:
            result["edges"]["document_sections"].append({
                "_from": f"documents/{doc_key}",
                "_to": f"sections/{sec_key}"
            })
    
    return result


def extract_html_to_unified_json(html_path: str) -> Dict[str, Any]:
    """Extract HTML to unified JSON"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("beautifulsoup4 is required for HTML extraction")
    
    # Read HTML with encoding detection
    try:
        import chardet
        with open(html_path, 'rb') as f:
            raw_data = f.read()
        detected = chardet.detect(raw_data)
        encoding = detected['encoding'] or 'utf-8'
        html_content = raw_data.decode(encoding)
    except:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract text content as markdown-like format
    markdown_lines = []
    
    # Process all headers and content
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
        if element.name.startswith('h'):
            level = int(element.name[1])
            text = element.get_text(strip=True)
            if text:
                markdown_lines.append('#' * level + ' ' + text)
        else:
            text = element.get_text(strip=True)
            if text:
                markdown_lines.append(text)
    
    markdown = '\n\n'.join(markdown_lines)
    
    # Create metadata
    metadata = {
        "extraction_method": "beautifulsoup",
        "timestamp": datetime.now().isoformat(),
        "title": soup.title.string if soup.title else Path(html_path).stem
    }
    
    # Convert to unified JSON
    return markdown_to_unified_json(markdown, metadata, html_path, "html")


def extract_docx_to_unified_json(docx_path: str) -> Dict[str, Any]:
    """Extract DOCX to unified JSON"""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required for DOCX extraction")
    
    doc = Document(docx_path)
    markdown_lines = []
    
    # Convert to markdown-like format
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            # Extract level
            level = 1
            if para.style.name[-1].isdigit():
                level = int(para.style.name[-1])
            
            text = para.text.strip()
            if text:
                markdown_lines.append('#' * level + ' ' + text)
        else:
            text = para.text.strip()
            if text:
                markdown_lines.append(text)
    
    markdown = '\n\n'.join(markdown_lines)
    
    # Create metadata
    metadata = {
        "extraction_method": "python-docx",
        "timestamp": datetime.now().isoformat(),
        "author": doc.core_properties.author or "Unknown"
    }
    
    return markdown_to_unified_json(markdown, metadata, docx_path, "docx")


def extract_to_unified_json(file_path: str) -> Dict[str, Any]:
    """
    Main entry point for unified extraction.
    Uses marker-pdf core for PDFs, appropriate extractors for other formats.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    ext = Path(file_path).suffix.lower()
    
    if ext == '.pdf':
        # Use marker-pdf core for PDFs
        markdown, metadata = extract_pdf_to_markdown(file_path)
        return markdown_to_unified_json(markdown, metadata, file_path, "pdf")
    
    elif ext in ['.html', '.htm']:
        return extract_html_to_unified_json(file_path)
    
    elif ext == '.docx':
        return extract_docx_to_unified_json(file_path)
    
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def compare_extraction_results(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compare extraction results across formats"""
    comparison = {
        "formats_tested": list(results.keys()),
        "section_counts": {},
        "content_sizes": {},
        "consistency_scores": {}
    }
    
    # Collect metrics
    for fmt, result in results.items():
        if 'error' not in result:
            comparison["section_counts"][fmt] = len(result.get('vertices', {}).get('sections', []))
            
            # Calculate total content size
            content_size = 0
            for section in result.get('vertices', {}).get('sections', []):
                content_size += len(section.get('content', ''))
            comparison["content_sizes"][fmt] = content_size
    
    # Calculate consistency
    if len(comparison["section_counts"]) > 1:
        counts = list(comparison["section_counts"].values())
        sizes = list(comparison["content_sizes"].values())
        
        # Section count consistency
        avg_count = sum(counts) / len(counts)
        max_count_dev = max(abs(c - avg_count) / avg_count for c in counts) if avg_count > 0 else 1
        comparison["consistency_scores"]["section_count"] = 1 - max_count_dev
        
        # Content size consistency
        avg_size = sum(sizes) / len(sizes)
        max_size_dev = max(abs(s - avg_size) / avg_size for s in sizes) if avg_size > 0 else 1
        comparison["consistency_scores"]["content_size"] = 1 - max_size_dev
        
        # Overall consistency
        comparison["consistency_scores"]["overall"] = (
            comparison["consistency_scores"]["section_count"] + 
            comparison["consistency_scores"]["content_size"]
        ) / 2
    
    return comparison


if __name__ == "__main__":
    # Comprehensive test with 3-way comparison
    print("🧪 Testing Unified Document Extractor v2")
    print("=" * 70)
    print("Using marker-pdf core for PDFs, adding unified JSON on top")
    print("=" * 70)
    
    # Test files
    base_path = "/home/graham/workspace/experiments/extractor/data/input"
    test_name = "2505.03335v2"
    
    results = {}
    
    # Test each format
    for fmt in ['pdf', 'html', 'docx']:
        file_path = os.path.join(base_path, f"{test_name}.{fmt}")
        
        if os.path.exists(file_path):
            print(f"\n📄 Testing {fmt.upper()} extraction: {Path(file_path).name}")
            
            try:
                start_time = time.time()
                result = extract_to_unified_json(file_path)
                elapsed = time.time() - start_time
                
                # Collect metrics
                section_count = len(result.get('vertices', {}).get('sections', []))
                content_size = sum(len(s.get('content', '')) for s in result.get('vertices', {}).get('sections', []))
                
                print(f"✅ Success:")
                print(f"   - Sections: {section_count}")
                print(f"   - Content: {content_size:,} characters")
                print(f"   - Time: {elapsed:.2f}s")
                
                # Check if original content preserved (for PDFs)
                if fmt == 'pdf' and 'original_content' in result:
                    orig_size = len(result['original_content']['content'])
                    print(f"   - Original markdown: {orig_size:,} characters (preserved)")
                
                results[fmt] = result
                
                # Save output
                output_path = os.path.join(base_path, f"{test_name}_{fmt}_unified_v2.json")
                with open(output_path, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"   💾 Saved to: {output_path}")
                
            except Exception as e:
                print(f"❌ Failed: {e}")
                results[fmt] = {"error": str(e)}
        else:
            print(f"\n⚠️  {fmt.upper()} file not found: {file_path}")
    
    # Compare results
    if len(results) > 1:
        print("\n" + "="*70)
        print("📊 COMPARISON RESULTS")
        print("="*70)
        
        comparison = compare_extraction_results(results)
        
        print("\nSection counts by format:")
        for fmt, count in comparison["section_counts"].items():
            print(f"   {fmt.upper()}: {count} sections")
        
        print("\nContent sizes by format:")
        for fmt, size in comparison["content_sizes"].items():
            print(f"   {fmt.upper()}: {size:,} characters")
        
        print("\nConsistency scores:")
        for metric, score in comparison["consistency_scores"].items():
            print(f"   {metric}: {score:.1%}")
        
        # Final verdict
        overall_consistency = comparison["consistency_scores"].get("overall", 0)
        
        print("\n" + "="*70)
        print("🏁 FINAL VERDICT")
        print("="*70)
        
        if overall_consistency > 0.7:  # 70% consistency threshold
            print("✅ Format extraction is CONSISTENT")
            print("✅ All formats produce reasonably similar unified JSON")
        else:
            print("❌ Format extraction is INCONSISTENT")
            print("   Different formats produce significantly different results")
        
        # Check PDF quality
        if 'pdf' in results and 'error' not in results['pdf']:
            pdf_sections = comparison["section_counts"].get('pdf', 0)
            if pdf_sections < 10:
                print("\n⚠️  WARNING: Low PDF section count suggests marker-pdf core issues")
                print("   This may indicate the Surya models are not working properly")
            else:
                print("\n✅ PDF extraction quality appears good")
    
    print("\n✅ Test complete")