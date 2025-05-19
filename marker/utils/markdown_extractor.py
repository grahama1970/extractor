"""
Utilities for extracting section breadcrumbs and metadata from markdown files.
"""
import re
import json
from typing import Dict, List, Any


def extract_sections_from_markdown(markdown_content: str) -> List[Dict[str, Any]]:
    """
    Extract all sections with their breadcrumbs from a markdown document.
    
    Args:
        markdown_content: The markdown content to extract sections from
            
    Returns:
        List of section metadata dictionaries with keys:
            - title: The section title
            - level: The heading level (1-6)
            - breadcrumb: The section breadcrumb hierarchy
            - content: The section content (text between this heading and the next)
    """
    # Find all section headers with breadcrumbs
    pattern = r'(#{1,6})\s+(.+?)\n+<!-- SECTION_BREADCRUMB: (.+?) -->'
    matches = re.finditer(pattern, markdown_content)
    
    section_data = []
    section_positions = []
    
    # Extract section data and positions
    for match in matches:
        heading_markers, title, breadcrumb_json = match.groups()
        level = len(heading_markers)
        try:
            breadcrumb = json.loads(breadcrumb_json)
            section_positions.append((match.start(), match.end()))
            section_data.append({
                "title": title,
                "level": level,
                "breadcrumb": breadcrumb,
                "section_path": get_section_path(breadcrumb),
                "section_title_path": get_section_title_path(breadcrumb)
            })
        except json.JSONDecodeError:
            # Skip malformed breadcrumbs
            continue
    
    # Add content to each section
    for i, section in enumerate(section_data):
        start_pos = section_positions[i][1]  # End of current section header + breadcrumb
        end_pos = section_positions[i+1][0] if i < len(section_data) - 1 else len(markdown_content)
        section["content"] = markdown_content[start_pos:end_pos].strip()
    
    return section_data


def get_section_path(breadcrumb: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Generate a path of section titles and hashes from the breadcrumb hierarchy.
    
    Args:
        breadcrumb: The breadcrumb hierarchy from a section
        
    Returns:
        List of section metadata (title and hash) in order from highest to current level
    """
    result = []
    # Sort by level to ensure correct order
    for level in sorted(breadcrumb.keys()):
        if isinstance(breadcrumb[level], dict):
            title = breadcrumb[level].get("title", f"Section {level}")
            section_hash = breadcrumb[level].get("hash", "")
            result.append({
                "title": title,
                "hash": section_hash,
                "level": int(level)
            })
        elif isinstance(breadcrumb[level], str):
            # Handle legacy format where only blockId is stored
            result.append({
                "title": f"Section {level}",
                "hash": "",
                "level": int(level)
            })
    return result


def get_section_title_path(breadcrumb: Dict[str, Dict[str, str]]) -> List[str]:
    """
    Generate a path of just section titles from the breadcrumb hierarchy.
    
    Args:
        breadcrumb: The breadcrumb hierarchy from a section
        
    Returns:
        List of section titles in order from highest to current level
    """
    section_path = get_section_path(breadcrumb)
    return [item["title"] for item in section_path]


def extract_from_markdown(markdown_content: str) -> Dict[str, Any]:
    """
    Extract all sections and their metadata from a markdown document.
    
    Args:
        markdown_content: The markdown content to extract from
        
    Returns:
        Dictionary with the following keys:
        - sections: List of section metadata dictionaries
        - section_hierarchy: Dictionary mapping level numbers to section metadata
    """
    sections = extract_sections_from_markdown(markdown_content)
    
    # Build a complete section hierarchy
    section_hierarchy = {}
    for section in sections:
        level = section["level"]
        section_hash = next((item["hash"] for item in section["section_path"] if item["level"] == level), "")
        
        section_hierarchy[level] = {
            "title": section["title"],
            "hash": section_hash,
            "section_path": section["section_title_path"]
        }
        
    return {
        "sections": sections,
        "section_hierarchy": section_hierarchy
    }


def remove_breadcrumbs(markdown_content: str) -> str:
    """
    Remove all breadcrumb comments from markdown content.
    
    Args:
        markdown_content: The markdown content to clean
        
    Returns:
        Markdown content with breadcrumb comments removed
    """
    return re.sub(r'<!-- SECTION_BREADCRUMB: .+? -->\n\n', '', markdown_content)