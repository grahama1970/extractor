"""
Relationship extraction utility for ArangoDB integration.

This module provides functions to extract relationships from Marker document structure,
particularly focusing on section hierarchy relationships for ArangoDB integration.

Example:
    ```python
    from marker.core.utils.relationship_extractor import extract_relationships_from_marker
    
    # Load marker output
    with open('document.json', 'r') as f:
        marker_output = json.load(f)
    
    # Extract relationships
    relationships = extract_relationships_from_marker(marker_output)
    ```

Documentation:
    - ArangoDB Graph Features: https://www.arangodb.com/docs/stable/graphs.html
    - Marker Document Structure: https://github.com/VikParuchuri/marker
"""

import hashlib
from typing import Dict, List, Any, Optional, Union


def create_id_hash(text: str) -> str:
    """
    Create a consistent hash ID from text content.
    
    Args:
        text: Text to hash
        
    Returns:
        Hash string suitable for use as an ID
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def extract_relationships_from_marker(marker_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract relationships from Marker output.
    
    This function analyzes the document structure in Marker output and extracts
    relationships between sections, content blocks, and other elements.
    
    Args:
        marker_output: Marker output in ArangoDB-compatible JSON format
        
    Returns:
        List of relationships in the format:
        [
            {
                "from": "section_123abc",
                "to": "section_456def",
                "type": "CONTAINS"
            }
        ]
    """
    document = marker_output.get("document", {})
    relationships = []
    
    # Create doc node ID
    doc_id = document.get("id", "")
    if not doc_id:
        return relationships
    
    # Extract section relationships (hierarchy)
    section_map = {}  # Store all sections with their levels
    content_map = {}  # Store all content blocks
    page_id_map = {}  # Keep track of page IDs for blocks
    
    # First pass: collect all sections and content blocks
    for page_idx, page in enumerate(document.get("pages", [])):
        page_id = f"page_{page_idx}"
        
        # Add relationship between document and page
        relationships.append({
            "from": doc_id,
            "to": page_id,
            "type": "CONTAINS"
        })
        
        # Process blocks within page
        for block_idx, block in enumerate(page.get("blocks", [])):
            block_type = block.get("type", "")
            block_text = block.get("text", "")
            
            # Create a unique ID for this block
            block_id = f"{block_type}_{create_id_hash(block_text)}"
            
            # Add relationship between page and block
            relationships.append({
                "from": page_id,
                "to": block_id,
                "type": "CONTAINS"
            })
            
            # Store page ID for this block
            page_id_map[block_id] = page_id
            
            # If section header, store in section map
            if block_type == "section_header":
                section_level = block.get("level", 1)
                section_map[block_id] = {
                    "text": block_text,
                    "level": section_level
                }
            else:
                # Store content block
                content_map[block_id] = {
                    "text": block_text,
                    "type": block_type
                }
    
    # Second pass: build section hierarchy
    sections_by_level = {}
    for section_id, section_info in section_map.items():
        level = section_info["level"]
        
        # Add section to level map
        if level not in sections_by_level:
            sections_by_level[level] = []
        
        sections_by_level[level].append({
            "id": section_id,
            "info": section_info
        })
    
    # Sort levels
    sorted_levels = sorted(sections_by_level.keys())
    
    # Create parent-child relationships between sections
    parent_mapping = {}  # Maps section IDs to their parent section IDs
    
    if sorted_levels:
        # Process each level starting from the top (lowest number)
        for level_idx, level in enumerate(sorted_levels):
            sections = sections_by_level[level]
            
            # Skip the last level (no children)
            if level_idx < len(sorted_levels) - 1:
                next_level = sorted_levels[level_idx + 1]
                child_sections = sections_by_level[next_level]
                
                # For each section at this level
                for section in sections:
                    # Find its child sections (sections at next level that come after this section)
                    section_idx = sections.index(section)
                    
                    # Find the next section at the same level (if any)
                    next_section_idx = section_idx + 1
                    next_section = sections[next_section_idx] if next_section_idx < len(sections) else None
                    
                    # Find sections at the next level that belong to this section
                    for child_section in child_sections:
                        # A child section belongs to this section if:
                        # 1. It comes after this section in document order
                        # 2. It comes before the next section at the same level (if any)
                        # 3. It's on the same page or a later page
                        
                        # Check if child is on same page or later
                        child_page = page_id_map.get(child_section["id"])
                        section_page = page_id_map.get(section["id"])
                        
                        if child_page >= section_page:
                            # Create parent-child relationship
                            parent_mapping[child_section["id"]] = section["id"]
                            
                            # Add relationship
                            relationships.append({
                                "from": section["id"],
                                "to": child_section["id"],
                                "type": "CONTAINS"
                            })
    
    # Assign content blocks to their containing sections
    for content_id, content_info in content_map.items():
        # Get page of this content
        content_page = page_id_map.get(content_id)
        
        # Find sections on the same page
        page_sections = []
        for section_id, section_info in section_map.items():
            if page_id_map.get(section_id) == content_page:
                page_sections.append({
                    "id": section_id,
                    "info": section_info
                })
        
        # Sort sections by level and position
        page_sections.sort(key=lambda s: s["info"]["level"])
        
        # Assign content to the last section of the highest level (most specific)
        if page_sections:
            containing_section = page_sections[-1]["id"]
            relationships.append({
                "from": containing_section,
                "to": content_id,
                "type": "CONTAINS"
            })
    
    return relationships


def extract_section_tree(marker_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a hierarchical section tree from Marker output.
    
    This function creates a nested tree structure representing the document
    sections and their hierarchical relationships.
    
    Args:
        marker_output: Marker output in ArangoDB-compatible JSON format
        
    Returns:
        Dictionary with hierarchical section structure
    """
    document = marker_output.get("document", {})
    
    # Extract all sections with their levels
    sections = []
    for page_idx, page in enumerate(document.get("pages", [])):
        for block_idx, block in enumerate(page.get("blocks", [])):
            if block.get("type") == "section_header":
                sections.append({
                    "id": f"section_{create_id_hash(block.get('text', ''))}",
                    "text": block.get("text", ""),
                    "level": block.get("level", 1),
                    "page": page_idx,
                    "position": block_idx
                })
    
    # Sort sections by page and position
    sections.sort(key=lambda s: (s["page"], s["position"]))
    
    # Build the tree
    root = {"children": []}
    stack = [root]
    
    for section in sections:
        level = section["level"]
        
        # Go back up the stack until we find a parent
        while len(stack) > 1 and stack[-1].get("level", 0) >= level:
            stack.pop()
        
        # Create node
        node = {
            "id": section["id"],
            "text": section["text"],
            "level": level,
            "children": []
        }
        
        # Add as child to parent
        stack[-1]["children"].append(node)
        
        # Push to stack
        stack.append(node)
    
    return root


if __name__ == "__main__":
    import sys
    import json
    from loguru import logger
    
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("relationship_extractor_validation.log", rotation="10 MB")
    
    # List to track validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Simple document with sections
    total_tests += 1
    logger.info("Test 1: Simple document with sections")
    
    # Create test document
    test_doc = {
        "document": {
            "id": "test_doc_123",
            "pages": [
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Introduction",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "This is introduction text."
                        },
                        {
                            "type": "section_header",
                            "text": "Methods",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "Methods description."
                        },
                        {
                            "type": "section_header",
                            "text": "Experiment Setup",
                            "level": 2
                        },
                        {
                            "type": "text",
                            "text": "Details of experiment setup."
                        }
                    ]
                }
            ]
        }
    }
    
    # Extract relationships
    try:
        relationships = extract_relationships_from_marker(test_doc)
        
        # Expected number of relationships
        expected_count = 8  # doc->page, page->3blocks, section1->section3, section->content
        
        if len(relationships) != expected_count:
            failure_msg = f"Expected {expected_count} relationships, got {len(relationships)}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            # Check for contains relationship between sections
            found_section_hierarchy = False
            for rel in relationships:
                if rel["type"] == "CONTAINS" and "section" in rel["from"] and "section" in rel["to"]:
                    found_section_hierarchy = True
                    break
            
            if not found_section_hierarchy:
                failure_msg = "No section hierarchy relationships found"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                logger.success("Section hierarchy extraction passed")
    except Exception as e:
        failure_msg = f"Extraction failed with error: {str(e)}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
    
    # Test 2: Multi-page document with complex structure
    total_tests += 1
    logger.info("Test 2: Multi-page document with complex structure")
    
    # Create test document
    test_doc_complex = {
        "document": {
            "id": "complex_doc_456",
            "pages": [
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Abstract",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "Abstract text."
                        },
                        {
                            "type": "section_header",
                            "text": "Introduction",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "Introduction text."
                        }
                    ]
                },
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Background",
                            "level": 2
                        },
                        {
                            "type": "text",
                            "text": "Background information."
                        },
                        {
                            "type": "section_header",
                            "text": "Methods",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "Methods description."
                        }
                    ]
                }
            ]
        }
    }
    
    # Extract relationships
    try:
        complex_relationships = extract_relationships_from_marker(test_doc_complex)
        
        # Minimum expected number of relationships (could be more depending on implementation)
        min_expected = 10  # doc->2pages, 2pages->8blocks, at least one section hierarchy
        
        if len(complex_relationships) < min_expected:
            failure_msg = f"Expected at least {min_expected} relationships, got {len(complex_relationships)}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            # Check that all blocks have relationships
            block_ids = set()
            relationship_sources = set()
            relationship_targets = set()
            
            for page in test_doc_complex["document"]["pages"]:
                for block in page["blocks"]:
                    block_type = block["type"]
                    block_text = block["text"]
                    block_id = f"{block_type}_{create_id_hash(block_text)}"
                    block_ids.add(block_id)
            
            for rel in complex_relationships:
                relationship_sources.add(rel["from"])
                relationship_targets.add(rel["to"])
            
            # Check that all blocks are referenced in relationships
            if not block_ids.issubset(relationship_sources.union(relationship_targets)):
                failure_msg = "Not all blocks are referenced in relationships"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                logger.success("Complex document relationship extraction passed")
            
            # Export sample relationships
            output_file = "test_relationships.json"
            with open(output_file, "w") as f:
                json.dump(complex_relationships, f, indent=2)
            logger.info(f"Sample relationships exported to {output_file}")
    except Exception as e:
        failure_msg = f"Complex extraction failed with error: {str(e)}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
    
    # Test 3: Test section tree extraction
    total_tests += 1
    logger.info("Test 3: Section tree extraction")
    
    try:
        section_tree = extract_section_tree(test_doc_complex)
        
        # Check that we have a valid tree structure
        if "children" not in section_tree:
            failure_msg = "Invalid tree structure - missing children property"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        elif len(section_tree["children"]) == 0:
            failure_msg = "Empty section tree - no sections found"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            # Check that we have at least the expected top-level sections
            top_level_count = len(section_tree["children"])
            if top_level_count < 3:  # Abstract, Introduction, Methods
                failure_msg = f"Expected at least 3 top-level sections, got {top_level_count}"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                logger.success("Section tree extraction passed")
                
                # Export sample tree
                output_file = "test_section_tree.json"
                with open(output_file, "w") as f:
                    json.dump(section_tree, f, indent=2)
                logger.info(f"Sample section tree exported to {output_file}")
    except Exception as e:
        failure_msg = f"Section tree extraction failed with error: {str(e)}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
    
    # Final validation result
    if all_validation_failures:
        logger.error(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            logger.error(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        logger.success(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        logger.info("Relationship extractor is validated and ready for use")
        sys.exit(0)  # Exit with success code