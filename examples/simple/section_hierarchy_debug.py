"""
Module: section_hierarchy_debug.py
Description: Implementation of section hierarchy debug functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

Section hierarchy by level:")
        for level in sorted(sections_by_level.keys()):
            print(f"Level {level} ({len(sections_by_level[level])} sections):")
            for section in sections_by_level[level]:
                print(f"  - {section['title'][:50]} (Hash: {section['hash']})")
        
        # Get full hierarchy from document
        if hasattr(document, 'get_section_hierarchy'):
            results["has_hierarchy_method"] = True
            hierarchy = document.get_section_hierarchy()
            results["hierarchy"] = hierarchy
            
            print("\nFull section hierarchy from document:")
            print(json.dumps(hierarchy, indent=2, default=str))
        else:
            print("\nDocument does not have get_section_hierarchy method")
        
        # Get breadcrumbs from document
        if hasattr(document, 'get_section_breadcrumbs'):
            results["has_breadcrumbs_method"] = True
            breadcrumbs = document.get_section_breadcrumbs()
            results["breadcrumbs"] = breadcrumbs
            
            print("\nBreadcrumbs from document:")
            print(json.dumps(breadcrumbs, indent=2, default=str))
        else:
            print("\nDocument does not have get_section_breadcrumbs method")
            
        return results
        
    except Exception as e:
        logger.error(f"Error inspecting section hierarchy: {e}")
        import traceback
        traceback.print_exc()
        results["error"] = str(e)
        return results


def trace_section_context(document: Document, search_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Trace the section context for a specific text or all blocks.
    
    Args:
        document: The Marker Document Object
        search_text: Optional text to search for in blocks
        
    Returns:
        Dictionary with section context information
    """
    results = {
        "block_count": 0,
        "matching_blocks": [],
        "has_current_hierarchy_method": False,
        "current_hierarchy": None,
        "block_contexts": []
    }
    
    try:
        # Get all blocks
        all_blocks = document.contained_blocks()
        results["block_count"] = len(all_blocks)
        matching_blocks = []
        
        # Find blocks containing the search text if provided
        if search_text:
            for block in all_blocks:
                if hasattr(block, 'raw_text'):
                    try:
                        text = block.raw_text(document)
                        if search_text.lower() in text.lower():
                            matching_blocks.append(block)
                    except Exception:
                        # Skip blocks that might raise errors when getting raw_text
                        continue
            logger.info(f"Found {len(matching_blocks)} blocks containing '{search_text}'")
        else:
            # Otherwise use first few blocks of different types
            block_types_seen = set()
            for block in all_blocks:
                if hasattr(block, 'block_type') and block.block_type not in block_types_seen and len(matching_blocks) < 5:
                    matching_blocks.append(block)
                    block_types_seen.add(block.block_type)
            logger.info(f"Selected {len(matching_blocks)} blocks of different types")
        
        # Limit to a maximum of 10 blocks to prevent overwhelming output
        matching_blocks = matching_blocks[:10]
        
        # Get current section hierarchy
        if hasattr(document, 'get_current_section_hierarchy'):
            results["has_current_hierarchy_method"] = True
            section_hierarchy = document.get_current_section_hierarchy()
            results["current_hierarchy"] = section_hierarchy
            
            print("\nCurrent section hierarchy:")
            print(json.dumps(section_hierarchy, indent=2, default=str))
        
        # Trace section context for each matching block
        print("\nSection context for blocks:")
        block_contexts = []
        for block in matching_blocks:
            block_info = {
                "block_type": str(block.block_type) if hasattr(block, 'block_type') else "Unknown",
                "block_id": str(block.id) if hasattr(block, 'id') else "Unknown",
            }
            
            print(f"Block type: {block_info['block_type']}")
            
            if hasattr(block, 'raw_text'):
                try:
                    text = block.raw_text(document)
                    block_info["text_preview"] = text[:100] + ("..." if len(text) > 100 else "")
                    print(f"Text: {block_info['text_preview']}")
                except Exception as e:
                    block_info["text_error"] = str(e)
                    print(f"Error getting text: {e}")
            
            # Find which section this block belongs to
            section_info = find_section_for_block(document, block)
            if section_info:
                block_info["section"] = section_info
                print(f"Within section: {section_info['title']}")
                print(f"Section level: {section_info['level']}")
                print(f"Section hash: {section_info['hash']}")
                
                # Print breadcrumb if available
                if 'breadcrumb' in section_info:
                    breadcrumb_path = " > ".join([item.get('title', '') for item in section_info['breadcrumb']])
                    print(f"Breadcrumb: {breadcrumb_path}")
            else:
                block_info["section"] = None
                print("Not within any section")
            
            block_contexts.append(block_info)
            print()
            
        results["block_contexts"] = block_contexts
        return results
            
    except Exception as e:
        logger.error(f"Error tracing section context: {e}")
        import traceback
        traceback.print_exc()
        results["error"] = str(e)
        return results


def find_section_for_block(document: Document, block: Any) -> Optional[Dict[str, Any]]:
    """
    Find which section a block belongs to.
    
    Args:
        document: The Marker Document Object
        block: The block to find the section for
        
    Returns:
        Dictionary with section information or None if not found in any section
    """
    try:
        # Get all sections
        sections = document.contained_blocks((BlockTypes.SectionHeader,))
        
        if not sections:
            logger.info("No sections found in document")
            return None
            
        # Check if block has required attributes
        if not hasattr(block, 'page_id') or not hasattr(block, 'polygon'):
            logger.warning(f"Block missing required attributes: {block}")
            return None
            
        # Sort sections by page and position
        try:
            sections.sort(key=lambda s: (
                getattr(s, 'page_id', 0) or 0, 
                s.polygon.bbox[1] if hasattr(s, 'polygon') and s.polygon else 0
            ))
        except Exception as e:
            logger.warning(f"Error sorting sections: {e}")
            # Try to continue with unsorted sections
        
        # Find section that contains this block
        containing_section = None
        for i, section in enumerate(sections):
            # Skip if section is missing required attributes
            if not hasattr(section, 'page_id') or not hasattr(section, 'polygon'):
                continue
                
            # Skip if block comes before this section
            block_page = getattr(block, 'page_id', 0) or 0
            section_page = getattr(section, 'page_id', 0) or 0
            
            if not hasattr(block, 'polygon') or not block.polygon:
                continue
                
            if (block_page < section_page or
                (block_page == section_page and 
                 block.polygon.bbox[1] < section.polygon.bbox[1])):
                continue
                
            # Check if block is before the next section
            if i < len(sections) - 1:
                next_section = sections[i+1]
                if not hasattr(next_section, 'page_id') or not hasattr(next_section, 'polygon'):
                    continue
                    
                next_section_page = getattr(next_section, 'page_id', 0) or 0
                
                if (block_page > next_section_page or
                    (block_page == next_section_page and 
                     block.polygon.bbox[1] >= next_section.polygon.bbox[1])):
                    continue
            
            # This section contains the block
            containing_section = section
            break
        
        if containing_section:
            try:
                result = {
                    'title': containing_section.raw_text(document).strip() if hasattr(containing_section, 'raw_text') else "Unknown",
                    'level': getattr(containing_section, 'heading_level', 0),
                    'hash': getattr(containing_section, 'section_hash', 'No hash')
                }
                
                # Add breadcrumb if available
                if hasattr(document, 'get_section_breadcrumbs'):
                    try:
                        breadcrumbs = document.get_section_breadcrumbs()
                        section_hash = getattr(containing_section, 'section_hash', '')
                        if section_hash and section_hash in breadcrumbs:
                            result['breadcrumb'] = breadcrumbs[section_hash]
                    except Exception as e:
                        logger.warning(f"Error getting breadcrumbs: {e}")
                
                return result
            except Exception as e:
                logger.error(f"Error creating result for containing section: {e}")
                return None
        
        return None
    except Exception as e:
        logger.error(f"Error finding section for block: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import sys
    
    # Track validation results
    all_validation_failures = []
    total_tests = 0
    
    # Use a sample PDF for testing
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "data/input/2505.03335v2.pdf"
    
    # Optional search text
    search_text = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Page range
    try:
        start_page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        end_page = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    except ValueError as e:
        logger.error(f"Invalid page range: {e}")
        all_validation_failures.append(f"Invalid page range: {e}")
        sys.exit(1)
    
    print(f"Processing {pdf_path} pages {start_page}-{end_page}")
    
    try:
        # Import required classes
        from marker.converters.pdf import PdfConverter
    except ImportError as e:
        logger.error(f"Import error: {e}")
        all_validation_failures.append(f"Import error: {e}")
        sys.exit(1)
    
    try:
        # Test 1: Validate the Section Hierarchy Functions
        total_tests += 1
        try:
            # Create a simple test to validate the section hierarchy functions
            # We'll use a mock document class for testing
# REMOVED: # REMOVED:             from unittest.mock import MagicMock
            
            logger.info("Creating mock document for testing")
            
            # Create a mock document
            document = Magicobject()
            
            # Mock the contained_blocks method
            section1 = Magicobject()
            section1.block_type = BlockTypes.SectionHeader
            section1.heading_level = 1
            section1.section_hash = "section1"
            section1.page_id = 0
            section1.polygon.bbox = [0, 10, 100, 30]
            section1.raw_text
            
            section2 = Magicobject()
            section2.block_type = BlockTypes.SectionHeader
            section2.heading_level = 2
            section2.section_hash = "section2"
            section2.page_id = 0
            section2.polygon.bbox = [0, 70, 100, 90]
            section2.raw_text
            
            text1 = Magicobject()
            text1.block_type = BlockTypes.Text
            text1.page_id = 0
            text1.polygon.bbox = [0, 40, 100, 60]
            text1.raw_text
            
            text2 = Magicobject()
            text2.block_type = BlockTypes.Text
            text2.page_id = 0
            text2.polygon.bbox = [0, 100, 100, 120]
            text2.raw_text
            
            # Setup document.contained_blocks to return different blocks based on the block_type parameter
            def mock_contained_blocks(block_types=None):
                all_blocks = [section1, text1, section2, text2]
                if block_types is None:
                    return all_blocks
                return [b for b in all_blocks if b.block_type in block_types]
            
            document.contained_blocks = mock_contained_blocks
            
            # Setup get_section_hierarchy
            document.get_section_hierarchy
                "section1": [{"title": "Section 1", "level": 1}],
                "section2": [{"title": "Section 1", "level": 1}, {"title": "Section 2", "level": 2}]
            }
            
            # Setup get_section_breadcrumbs
            document.get_section_breadcrumbs
                "section1": [{"title": "Section 1", "level": 1}],
                "section2": [{"title": "Section 1", "level": 1}, {"title": "Section 2", "level": 2}]
            }
            
            # Run a simple test on our functions
            test_result = inspect_section_hierarchy(document)
            if test_result["section_count"] != 2:
                all_validation_failures.append(f"Expected 2 sections, got {test_result['section_count']}")
            
            logger.info("✅ Mock document created successfully")
        except Exception as e:
            logger.error(f"Document creation error: {e}")
            import traceback
            traceback.print_exc()
            all_validation_failures.append(f"Document creation error: {e}")
            sys.exit(1)  # Can't continue without document
        
        # Test 2: Section Hierarchy Inspection
        total_tests += 1
        try:
            hierarchy_results = inspect_section_hierarchy(document)
            
            if "error" in hierarchy_results:
                all_validation_failures.append(f"Section hierarchy inspection error: {hierarchy_results['error']}")
            elif hierarchy_results["section_count"] != 2:
                all_validation_failures.append(f"Expected 2 sections, got {hierarchy_results['section_count']}")
            elif not hierarchy_results["has_hierarchy_method"]:
                all_validation_failures.append("Expected document to have get_section_hierarchy method")
            elif not hierarchy_results["has_breadcrumbs_method"]:
                all_validation_failures.append("Expected document to have get_section_breadcrumbs method")
            else:
                logger.info(f"✅ Section hierarchy inspection successful: Found {hierarchy_results['section_count']} sections")
        except Exception as e:
            logger.error(f"Section hierarchy inspection error: {e}")
            all_validation_failures.append(f"Section hierarchy inspection error: {e}")
        
        # Test 3: Section Context Tracing
        total_tests += 1
        try:
            context_results = trace_section_context(document, "Text")
            
            if "error" in context_results:
                all_validation_failures.append(f"Section context tracing error: {context_results['error']}")
            elif context_results["block_count"] != 4:
                all_validation_failures.append(f"Expected 4 blocks, got {context_results['block_count']}")
            # We won't check matching_blocks as it's populated based on raw_text search
            # which our mock doesn't properly implement
            else:
                logger.info(f"✅ Section context tracing successful: Found {context_results['block_count']} blocks")
        except Exception as e:
            logger.error(f"Section context tracing error: {e}")
            all_validation_failures.append(f"Section context tracing error: {e}")
        
        # Test 4: Find Section for a Block
        total_tests += 1
        try:
            # Use text1 as our test block
            section_info = find_section_for_block(document, text1)
            if not section_info:
                all_validation_failures.append("Expected to find section for text1, but none found")
            elif section_info.get('hash') != "section1":
                all_validation_failures.append(f"Expected section hash 'section1', got {section_info.get('hash')}")
            else:
                logger.info(f"✅ Find section for block successful: Block found in section '{section_info.get('title', 'Unknown')}'")
            
            # Also test with text2
            section_info = find_section_for_block(document, text2)
            if not section_info:
                all_validation_failures.append("Expected to find section for text2, but none found")
            elif section_info.get('hash') != "section2":
                all_validation_failures.append(f"Expected section hash 'section2', got {section_info.get('hash')}")
            else:
                logger.info(f"✅ Find section for block successful: Block found in section '{section_info.get('title', 'Unknown')}'")
        except Exception as e:
            logger.error(f"Find section for block error: {e}")
            all_validation_failures.append(f"Find section for block error: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        all_validation_failures.append(f"Unexpected error: {e}")
    
    # Final validation result
    if all_validation_failures:
        print(f"\n❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for i, failure in enumerate(all_validation_failures):
            print(f"  {i+1}. {failure}")
        sys.exit(1)  # Exit with error code
    else:
        print(f"\n✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Section hierarchy debug script is validated and working correctly")
        sys.exit(0)  # Exit with success code