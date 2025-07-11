"""
import json
import logging
import os
import sys
from pprint import pformat
from typing import Any, Callable, Dict, List, Optional, Union
Module: document_debugger.py
Description: Implementation of document debugger functionality
Description: Implementation of document debugger functionality

from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, BlockId


class SectionBreakpoint(Exception):
    """Exception raised when a section breakpoint is triggered."""
"""
Utilities for debugging the document model.
    pass


class DocumentDebugger:
    """
    Helper for debugging the document model.
    Provides tools for inspecting document structure, section hierarchy,
    and setting breakpoints at specific sections.
    """
    
    @staticmethod
    def setup_logging(log_file: str = "marker_debug.log", console_level: str = "INFO", file_level: str = "DEBUG"):
        """Configure detailed logging for debugging."""
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        
        console_level = log_levels.get(console_level, logging.INFO)
        file_level = log_levels.get(file_level, logging.DEBUG)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        root_logger.handlers = []
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        return root_logger
    
    @staticmethod
    def log_section_hierarchy(document, debug_dir: str = "debug", msg: str = "Current section hierarchy:"):
        """
        Log the current section hierarchy for debugging.
        
        Args:
            document: The document object
            debug_dir: Directory to save debug files
            msg: Message to log with the hierarchy
        
        Returns:
            The section hierarchy dictionary
        """
        # Get section hierarchy
        if hasattr(document, 'get_section_hierarchy'):
            hierarchy = document.get_section_hierarchy()
        elif hasattr(document, 'get_current_section_hierarchy'):
            hierarchy = document.get_current_section_hierarchy()
        else:
            hierarchy = {"error": "Document has no section hierarchy methods"}
        
        # Log hierarchy
        logging.debug(f"{msg}\n{pformat(hierarchy)}")
        
        # Create debug directory if it doesn't exist
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save to debug file for inspection
        debug_file = os.path.join(debug_dir, "debug_section_hierarchy.json")
        with open(debug_file, "w") as f:
            json.dump(hierarchy, f, indent=2, default=str)
            
        logging.info(f"Saved section hierarchy to {debug_file}")
        return hierarchy
    
    @staticmethod
    def log_document_structure(document, debug_dir: str = "debug"):
        """
        Log the document structure for debugging.
        
        Args:
            document: The document object
            debug_dir: Directory to save debug files
        
        Returns:
            Dictionary with document structure information
        """
        # Create structure summary
        structure = {
            "pages": len(document.pages),
            "blocks_by_type": {},
            "sections": [],
        }
        
        # Count blocks by type
        all_blocks = document.contained_blocks()
        for block in all_blocks:
            block_type = str(block.block_type)
            if block_type not in structure["blocks_by_type"]:
                structure["blocks_by_type"][block_type] = 0
            structure["blocks_by_type"][block_type] += 1
        
        # Extract section info
        sections = document.contained_blocks([BlockTypes.SectionHeader])
        for section in sections:
            if hasattr(section, 'heading_level') and section.heading_level:
                section_info = {
                    "level": section.heading_level,
                    "title": section.raw_text(document).strip(),
                    "page": section.page_id,
                    "id": str(section.id)
                }
                
                # Add hash if available
                if hasattr(section, 'section_hash') and section.section_hash:
                    section_info["hash"] = section.section_hash
                
                structure["sections"].append(section_info)
        
        # Log structure summary
        logging.debug(f"Document structure:\n{pformat(structure)}")
        
        # Create debug directory if it doesn't exist
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save to debug file for inspection
        debug_file = os.path.join(debug_dir, "debug_document_structure.json")
        with open(debug_file, "w") as f:
            json.dump(structure, f, indent=2, default=str)
            
        logging.info(f"Saved document structure to {debug_file}")
        return structure
    
    @staticmethod
    def breakpoint_after_section(document, section_title: Optional[str] = None, level: Optional[int] = None, 
                                 callback: Optional[Callable[[Block], None]] = None, raise_exception: bool = False):
        """
        Set conditional breakpoint after processing a specific section.
        
        Args:
            document: The document object
            section_title: Title text to match (case-insensitive substring)
            level: Heading level to match
            callback: Optional callback function to execute when section is found
            raise_exception: Whether to raise a SectionBreakpoint exception when found
        
        Returns:
            The matched section or None
        """
        if not section_title and not level:
            logging.warning("No section criteria provided, will not break")
            return None
            
        sections = []
        for page in document.pages:
            sections.extend(page.contained_blocks(document, (BlockTypes.SectionHeader,)))
            
        match_found = False
        matched_section = None
        
        for section in sections:
            title_match = (section_title and 
                          section_title.lower() in section.raw_text(document).lower())
            level_match = (level is not None and 
                          hasattr(section, 'heading_level') and 
                          section.heading_level == level)
            
            if (section_title and level) and (title_match and level_match):
                # Both criteria specified and both match
                match_found = True
                matched_section = section
                break
            elif section_title and title_match and level is None:
                # Only title specified and it matches
                match_found = True
                matched_section = section
                break
            elif level is not None and level_match and not section_title:
                # Only level specified and it matches
                match_found = True
                matched_section = section
                break
        
        if match_found and matched_section:
            # Log section context
            logging.info(f"Found matching section: {matched_section.raw_text(document)}")
            logging.debug(f"Section context:\n{pformat(DocumentDebugger._get_section_context(document, matched_section))}")
            
            # Run callback if provided
            if callback and callable(callback):
                callback(matched_section)
                
            # This is where you'd place a breakpoint in a debugger
            # For automated workflows, we can do a visual break
            print(f"\n{'='*50}\nBREAKPOINT: Section {matched_section.raw_text(document)}\n{'='*50}")
            
            # For programmatic workflows, optionally raise a custom exception
            if raise_exception:
                raise SectionBreakpoint(f"Stopped at section: {matched_section.raw_text(document)}")
                
            return matched_section
        
        if not match_found:
            logging.warning(f"No section matching criteria found (title: {section_title}, level: {level})")
            return None
    
    @staticmethod
    def _get_section_context(document, section):
        """
        Get debugging context for a section.
        
        Args:
            document: The document object
            section: The section block
            
        Returns:
            Dictionary with section context
        """
        # Get section content
        content_blocks = []
        if hasattr(section, 'get_section_content'):
            content_blocks = section.get_section_content(document)
            
        # Build context dict
        context = {
            "section_id": str(section.id),
            "heading_level": getattr(section, 'heading_level', None),
            "text": section.raw_text(document),
            "position": section.polygon.bbox if section.polygon else None,
            "content_block_count": len(content_blocks),
            "section_hash": getattr(section, 'section_hash', None),
        }
        
        # Add breadcrumb if available
        if hasattr(document, 'get_current_section_hierarchy'):
            hierarchy = document.get_current_section_hierarchy()
            level = getattr(section, 'heading_level', None)
            if level and level in hierarchy:
                context["section_hierarchy"] = hierarchy
                if "breadcrumb" in hierarchy[level]:
                    context["breadcrumb"] = hierarchy[level]["breadcrumb"]
        
        # Get content preview
        if content_blocks:
            content_preview = []
            for block in content_blocks[:3]:  # First 3 blocks
                content_preview.append(block.raw_text(document)[:100] + "...")
            context["content_preview"] = content_preview
            
        return context
    
    @staticmethod
    def dump_section_content(document, section, output_dir: str = "debug"):
        """
        Dump the full content of a section to a file.
        
        Args:
            document: The document object
            section: The section block
            output_dir: Directory to save output files
            
        Returns:
            Path to the output file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get section title for filename
        title = section.raw_text(document).strip()
        safe_title = "".join([c if c.isalnum() else "_" for c in title])[:30]
        
        # Get section content
        content_blocks = []
        if hasattr(section, 'get_section_content'):
            content_blocks = section.get_section_content(document)
        
        # Build full content
        full_content = [title]
        full_content.append("=" * len(title))
        full_content.append("")
        
        for block in content_blocks:
            full_content.append(block.raw_text(document))
            
        # Write to file
        output_file = os.path.join(output_dir, f"section_{safe_title}.txt")
        with open(output_file, "w") as f:
            f.write("\n".join(full_content))
            
        logging.info(f"Saved section content to {output_file}")
        return output_file