#!/usr/bin/env python3
"""
Module: unified_extractor.py
Description: Unified document extraction for PDF, HTML, XML, DOCX to ArangoDB JSON format

External Dependencies:
- pymupdf: https://pymupdf.readthedocs.io/
- beautifulsoup4: https://www.crummy.com/software/BeautifulSoup/
- defusedxml: https://pypi.org/project/defusedxml/
- python-docx: https://python-docx.readthedocs.io/

Sample Input:
>>> doc_path = "document.pdf"  # or .html, .xml, .docx

Expected Output:
>>> result = extract_to_unified_json(doc_path)
>>> print(result["vertices"]["documents"][0]["title"])
'Document Title'

Example Usage:
>>> from extractor.unified_extractor import extract_to_unified_json
>>> json_data = extract_to_unified_json("research.pdf")
>>> # Import to ArangoDB
>>> import_to_arangodb(json_data)
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def generate_id(text: str, prefix: str = "") -> str:
    """Generate consistent ID from text"""
    hash_obj = hashlib.md5(text.encode())
    short_hash = hash_obj.hexdigest()[:8]
    return f"{prefix}_{short_hash}" if prefix else short_hash


def extract_pdf_unified(pdf_path: str) -> Dict[str, Any]:
    """Extract PDF to unified JSON using PyMuPDF"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: uv add pymupdf")
    
    doc = fitz.open(pdf_path)
    doc_id = generate_id(pdf_path, "doc")
    
    # Initialize structure
    result = {
        "vertices": {
            "documents": [{
                "_key": doc_id,
                "_id": f"documents/{doc_id}",
                "title": Path(pdf_path).stem,
                "source_file": pdf_path,
                "format": "pdf",
                "page_count": len(doc),
                "created_at": datetime.now().isoformat()
            }],
            "sections": [],
            "entities": []
        },
        "edges": {
            "contains": [],
            "references": [],
            "mentions": []
        }
    }
    
    section_hierarchy = []
    current_section_stack = []
    
    for page_num, page in enumerate(doc):
        # Get text blocks with formatting info
        blocks = page.get_text("dict")
        
        for block in blocks.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        font_size = span.get("size", 12)
                        flags = span.get("flags", 0)
                        is_bold = bool(flags & 2**4)
                        
                        # Detect headers
                        is_header = False
                        level = 0
                        
                        if font_size > 20 or (is_bold and font_size > 16):
                            is_header = True
                            level = 1
                        elif font_size > 16 or (is_bold and font_size > 14):
                            is_header = True
                            level = 2
                        elif font_size > 14 or (is_bold and font_size > 12):
                            is_header = True
                            level = 3
                        
                        if is_header and len(text) > 3:
                            # Create section
                            section_id = generate_id(text + str(page_num), "sec")
                            
                            # Determine parent
                            parent_id = None
                            while current_section_stack and current_section_stack[-1][1] >= level:
                                current_section_stack.pop()
                            
                            if current_section_stack:
                                parent_id = current_section_stack[-1][0]
                            
                            section = {
                                "_key": section_id,
                                "_id": f"sections/{section_id}",
                                "title": text,
                                "level": level,
                                "page": page_num + 1,
                                "content": "",
                                "parent": parent_id
                            }
                            
                            result["vertices"]["sections"].append(section)
                            current_section_stack.append((section_id, level))
                            
                            # Add edge from document to section or parent to child
                            if parent_id:
                                result["edges"]["contains"].append({
                                    "_from": f"sections/{parent_id}",
                                    "_to": f"sections/{section_id}",
                                    "type": "subsection"
                                })
                            else:
                                result["edges"]["contains"].append({
                                    "_from": f"documents/{doc_id}",
                                    "_to": f"sections/{section_id}",
                                    "type": "section"
                                })
                        
                        elif result["vertices"]["sections"] and not is_header:
                            # Add content to last section
                            result["vertices"]["sections"][-1]["content"] += f" {text}"
    
    doc.close()
    
    # Extract entities from content (simple implementation)
    extract_entities(result)
    
    return result


def extract_html_unified(html_path: str) -> Dict[str, Any]:
    """Extract HTML to unified JSON"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("BeautifulSoup not installed. Run: uv add beautifulsoup4")
    
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    doc_id = generate_id(html_path, "doc")
    
    result = {
        "vertices": {
            "documents": [{
                "_key": doc_id,
                "_id": f"documents/{doc_id}",
                "title": soup.title.string if soup.title else Path(html_path).stem,
                "source_file": html_path,
                "format": "html",
                "created_at": datetime.now().isoformat()
            }],
            "sections": [],
            "entities": []
        },
        "edges": {
            "contains": [],
            "references": [],
            "mentions": []
        }
    }
    
    # Process headers
    header_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    current_stack = []
    
    for elem in soup.find_all(header_tags + ['p', 'div']):
        if elem.name in header_tags:
            level = int(elem.name[1])
            text = elem.get_text(strip=True)
            
            if text:
                section_id = generate_id(text + elem.name, "sec")
                
                # Find parent
                parent_id = None
                while current_stack and current_stack[-1][1] >= level:
                    current_stack.pop()
                
                if current_stack:
                    parent_id = current_stack[-1][0]
                
                # Get content until next header
                content_parts = []
                for sibling in elem.find_next_siblings():
                    if sibling.name in header_tags:
                        break
                    content_parts.append(sibling.get_text(strip=True))
                
                section = {
                    "_key": section_id,
                    "_id": f"sections/{section_id}",
                    "title": text,
                    "level": level,
                    "content": ' '.join(content_parts),
                    "parent": parent_id
                }
                
                result["vertices"]["sections"].append(section)
                current_stack.append((section_id, level))
                
                # Add edges
                if parent_id:
                    result["edges"]["contains"].append({
                        "_from": f"sections/{parent_id}",
                        "_to": f"sections/{section_id}",
                        "type": "subsection"
                    })
                else:
                    result["edges"]["contains"].append({
                        "_from": f"documents/{doc_id}",
                        "_to": f"sections/{section_id}",
                        "type": "section"
                    })
    
    extract_entities(result)
    return result


def extract_xml_unified(xml_path: str) -> Dict[str, Any]:
    """Extract XML to unified JSON"""
    try:
        import defusedxml.ElementTree as ET
    except ImportError:
        raise ImportError("defusedxml not installed. Run: uv add defusedxml")
    
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    doc_id = generate_id(xml_path, "doc")
    
    result = {
        "vertices": {
            "documents": [{
                "_key": doc_id,
                "_id": f"documents/{doc_id}",
                "title": root.findtext('title', Path(xml_path).stem),
                "source_file": xml_path,
                "format": "xml",
                "created_at": datetime.now().isoformat()
            }],
            "sections": [],
            "entities": []
        },
        "edges": {
            "contains": [],
            "references": [],
            "mentions": []
        }
    }
    
    def process_element(elem, parent_id=None, level=1):
        """Recursively process XML elements"""
        if elem.tag == 'section':
            title = elem.findtext('title', f'Section {len(result["vertices"]["sections"]) + 1}')
            content = elem.findtext('content', '')
            
            section_id = generate_id(title + str(level), "sec")
            
            section = {
                "_key": section_id,
                "_id": f"sections/{section_id}",
                "title": title,
                "level": level,
                "content": content,
                "parent": parent_id
            }
            
            result["vertices"]["sections"].append(section)
            
            # Add edge
            if parent_id:
                result["edges"]["contains"].append({
                    "_from": f"sections/{parent_id}",
                    "_to": f"sections/{section_id}",
                    "type": "subsection"
                })
            else:
                result["edges"]["contains"].append({
                    "_from": f"documents/{doc_id}",
                    "_to": f"sections/{section_id}",
                    "type": "section"
                })
            
            # Process subsections
            for child in elem:
                if child.tag == 'section':
                    process_element(child, section_id, level + 1)
    
    # Process all sections
    for section in root.findall('.//section'):
        process_element(section)
    
    extract_entities(result)
    return result


def extract_docx_unified(docx_path: str) -> Dict[str, Any]:
    """Extract DOCX to unified JSON"""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx not installed. Run: uv add python-docx")
    
    doc = Document(docx_path)
    doc_id = generate_id(docx_path, "doc")
    
    result = {
        "vertices": {
            "documents": [{
                "_key": doc_id,
                "_id": f"documents/{doc_id}",
                "title": Path(docx_path).stem,
                "source_file": docx_path,
                "format": "docx",
                "author": doc.core_properties.author,
                "created_at": datetime.now().isoformat()
            }],
            "sections": [],
            "entities": []
        },
        "edges": {
            "contains": [],
            "references": [],
            "mentions": []
        }
    }
    
    current_section = None
    current_stack = []
    
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            # Extract level from style name
            level = 1
            if para.style.name[-1].isdigit():
                level = int(para.style.name[-1])
            
            text = para.text.strip()
            if text:
                section_id = generate_id(text + str(level), "sec")
                
                # Find parent
                parent_id = None
                while current_stack and current_stack[-1][1] >= level:
                    current_stack.pop()
                
                if current_stack:
                    parent_id = current_stack[-1][0]
                
                section = {
                    "_key": section_id,
                    "_id": f"sections/{section_id}",
                    "title": text,
                    "level": level,
                    "content": "",
                    "parent": parent_id
                }
                
                result["vertices"]["sections"].append(section)
                current_stack.append((section_id, level))
                current_section = section
                
                # Add edge
                if parent_id:
                    result["edges"]["contains"].append({
                        "_from": f"sections/{parent_id}",
                        "_to": f"sections/{section_id}",
                        "type": "subsection"
                    })
                else:
                    result["edges"]["contains"].append({
                        "_from": f"documents/{doc_id}",
                        "_to": f"sections/{section_id}",
                        "type": "section"
                    })
        
        elif para.text.strip() and current_section:
            # Add to current section
            current_section["content"] += f" {para.text.strip()}"
    
    extract_entities(result)
    return result


def extract_entities(result: Dict[str, Any]):
    """Extract entities from document content"""
    # Simple entity extraction - look for capitalized phrases
    import re
    
    entities = {}
    
    # Process all section content
    for section in result["vertices"]["sections"]:
        content = section.get("content", "")
        
        # Find capitalized phrases (potential entities)
        pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        matches = re.findall(pattern, content)
        
        for match in matches:
            if len(match) > 3 and match not in ["The", "This", "That", "These", "Those"]:
                if match not in entities:
                    entity_id = generate_id(match, "ent")
                    entities[match] = {
                        "_key": entity_id,
                        "_id": f"entities/{entity_id}",
                        "name": match,
                        "type": "unknown",
                        "mentions": []
                    }
                
                # Add mention
                entities[match]["mentions"].append({
                    "section": section["_id"],
                    "context": content[max(0, content.find(match)-20):content.find(match)+len(match)+20]
                })
    
    # Add entities to result
    result["vertices"]["entities"] = list(entities.values())
    
    # Add mention edges
    for entity in entities.values():
        for mention in entity["mentions"]:
            result["edges"]["mentions"].append({
                "_from": mention["section"],
                "_to": entity["_id"],
                "context": mention["context"]
            })


def extract_to_unified_json(file_path: str) -> Dict[str, Any]:
    """Main function to extract any document format to unified JSON"""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    suffix = path.suffix.lower()
    
    extractors = {
        '.pdf': extract_pdf_unified,
        '.html': extract_html_unified,
        '.htm': extract_html_unified,
        '.xml': extract_xml_unified,
        '.docx': extract_docx_unified
    }
    
    if suffix not in extractors:
        raise ValueError(f"Unsupported file format: {suffix}")
    
    return extractors[suffix](file_path)


if __name__ == "__main__":
    # Test unified extraction with real documents
    print("🧪 Testing Unified Document Extractor")
    print("=" * 50)
    
    # Test with the arXiv paper that has both HTML and PDF versions
    base_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2"
    test_files = {
        "html": f"{base_path}.html",
        "pdf": f"{base_path}.pdf",
        "docx": f"{base_path}.docx"
    }
    
    results = {}
    
    for fmt, path in test_files.items():
        if os.path.exists(path):
            print(f"\n📄 Testing {fmt.upper()} extraction: {Path(path).name}")
            try:
                result = extract_to_unified_json(path)
                results[fmt] = result
                
                print(f"✅ Extraction successful!")
                print(f"   - Documents: {len(result['vertices']['documents'])}")
                print(f"   - Sections: {len(result['vertices']['sections'])}")
                print(f"   - Entities: {len(result['vertices']['entities'])}")
                print(f"   - Edges: {sum(len(edges) for edges in result['edges'].values())}")
                
                # Show sample section
                if result['vertices']['sections']:
                    section = result['vertices']['sections'][0]
                    print(f"\n   Sample section:")
                    print(f"   - Title: {section['title']}")
                    print(f"   - Level: {section['level']}")
                    print(f"   - Content: {section['content'][:100]}...")
                
                # Save output
                output_path = Path(path).parent / f"{Path(path).stem}_{fmt}_unified.json"
                with open(output_path, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\n   💾 Saved to: {output_path}")
                
            except Exception as e:
                print(f"❌ Extraction failed: {e}")
                import traceback
                traceback.print_exc()
    
    # Compare HTML and PDF results if both exist
    if 'html' in results and 'pdf' in results:
        print("\n" + "=" * 50)
        print("📊 COMPARING HTML vs PDF EXTRACTION")
        print("=" * 50)
        
        html_r = results['html']
        pdf_r = results['pdf']
        
        # Structure comparison
        print("\n✅ Structure Consistency:")
        print(f"   - Same vertex types: {set(html_r['vertices'].keys()) == set(pdf_r['vertices'].keys())}")
        print(f"   - Same edge types: {set(html_r['edges'].keys()) == set(pdf_r['edges'].keys())}")
        
        # Content comparison
        print("\n📈 Content Statistics:")
        print(f"   HTML: {len(html_r['vertices']['sections'])} sections, {len(html_r['vertices']['entities'])} entities")
        print(f"   PDF:  {len(pdf_r['vertices']['sections'])} sections, {len(pdf_r['vertices']['entities'])} entities")
        
        # Check for key content
        html_content = ' '.join(s['content'] for s in html_r['vertices']['sections'])
        pdf_content = ' '.join(s['content'] for s in pdf_r['vertices']['sections'])
        
        key_terms = ['Absolute Zero', 'reinforcement learning', 'Table', 'Figure', 'Equation']
        print("\n🔍 Key Content Detection:")
        for term in key_terms:
            html_found = term.lower() in html_content.lower()
            pdf_found = term.lower() in pdf_content.lower()
            status = "✅" if html_found and pdf_found else "⚠️"
            print(f"   {status} '{term}' - HTML: {html_found}, PDF: {pdf_found}")
    
    print("\n" + "=" * 50)
    print("✅ Unified extraction testing complete")