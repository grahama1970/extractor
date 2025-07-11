"""
Module: sectionheader.py

External Dependencies:
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Dict, List, Optional, Any
import hashlib
import json
import logging

from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, BlockId


class SectionHeader(Block):
    block_type: BlockTypes = BlockTypes.SectionHeader
    heading_level: Optional[int] = None
    block_description: str = "The header of a section of text or other blocks."
    html: str | None = None
    section_hash: str = ""

    def compute_section_hash(self, document):
        """
        Compute a hash of the section content.
        This includes the section title and all content under this section until the next section at the same level.
        """
        # Start with the section title
        content = self.raw_text(document) if document else self.raw_text(None)

        if document:
            # Find content within this section
            section_blocks = self.get_section_content(document)
            for block in section_blocks:
                content += block.raw_text(document)

        # Generate a hash of the content
        hash_value = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]  # Use first 16 chars of the hash
        logging.debug(f"Generated section hash for '{content[:50]}...': {hash_value}")
        return hash_value

    def get_section_content(self, document):
        """
        Get all blocks that belong to this section (until the next section at the same level).
        """
        if self.page_id is None or not hasattr(document, "get_page"):
            return []

        # Get the page
        page = document.get_page(self.page_id)
        if not page or not page.structure:
            return []

        # Find this section in the structure
        try:
            my_index = page.structure.index(self.id)
        except ValueError:
            return []

        section_blocks = []
        # Collect blocks until the next section of the same or higher level
        for i in range(my_index + 1, len(page.structure)):
            block_id = page.structure[i]
            block = document.get_block(block_id)

            # Stop if we find another section header at the same or higher level
            if (block.block_type == BlockTypes.SectionHeader and 
                    self.heading_level is not None and
                    getattr(block, "heading_level", 999) <= self.heading_level):
                break

            section_blocks.append(block)

        logging.debug(f"Found {len(section_blocks)} content blocks for section '{self.raw_text(document)[:50]}...'")
        return section_blocks

    def _build_breadcrumb_array(self, section_hierarchy):
        """
        Build a breadcrumb array with [parent, ..., this section].
        """
        breadcrumb = []
        # Add all parent sections in order
        if self.heading_level is not None:
            for level in sorted(section_hierarchy.keys()):
                # Convert level to int for comparison
                level_int = int(level) if isinstance(level, str) else level
                if level_int < self.heading_level:
                    parent = section_hierarchy[level]
                    # Handle both dict and list formats
                    if isinstance(parent, dict):
                        parent_title = parent.get("title", "")
                        parent_hash = parent.get("hash", "")
                    elif isinstance(parent, list) and len(parent) > 0:
                        # If it's a list, use the first element
                        parent_title = str(parent[0]) if parent else ""
                        parent_hash = ""
                    else:
                        parent_title = str(parent)
                        parent_hash = ""

                    breadcrumb.append({
                        "title": parent_title,
                        "hash": parent_hash,
                        "level": level
                    })

        # Add this section
        title = self.raw_text(None).strip()
        breadcrumb.append({
            "title": title,
            "hash": self.section_hash,
            "level": self.heading_level
        })

        return breadcrumb

    def _get_breadcrumb_json(self, document):
        """Get JSON representation of breadcrumb for HTML output."""
        # Get current section hierarchy from Document (if available)
        section_hierarchy = {}
        if hasattr(document, 'get_current_section_hierarchy'):
            section_hierarchy = document.get_current_section_hierarchy()

        # Build breadcrumb from hierarchy
        breadcrumb = self._build_breadcrumb_array(section_hierarchy)
        return json.dumps(breadcrumb, ensure_ascii=False)

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        if self.html:
            return super().handle_html_output(document, child_blocks, parent_structure)

        # Compute content hash if not already set
        if not self.section_hash:
            self.section_hash = self.compute_section_hash(document)

        template = super().assemble_html(document, child_blocks, parent_structure)
        template = template.replace("\n", " ")
        tag = f"h{self.heading_level}" if self.heading_level else "h2"

        # Include section hash and breadcrumb as data attributes
        breadcrumb_json = self._get_breadcrumb_json(document) if document else "{}"
        return f'<{tag} data-section-hash="{self.section_hash}" data-breadcrumb=\'{breadcrumb_json}\'>{template}</{tag}>'

    def assign_section_hierarchy(self, section_hierarchy: Dict[int, Dict]):
        """
        Override the parent method to add this section to the hierarchy with rich metadata.
        """
        if self.heading_level:
            # Compute hash if not already set
            if not self.section_hash:
                text = self.raw_text(None) if hasattr(self, 'text') else ""
                self.section_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

            # Remove any higher or equal level sections from the hierarchy
            levels = list(section_hierarchy.keys())
            for level in levels:
                if level >= self.heading_level:
                    del section_hierarchy[level]

            # Build breadcrumb array
            breadcrumb = self._build_breadcrumb_array(section_hierarchy)

            # Add this section to the hierarchy with rich metadata
            section_hierarchy[self.heading_level] = {
                "id": self.id,
                "title": self.raw_text(None).strip(),
                "hash": self.section_hash,
                "breadcrumb": breadcrumb  # Include full breadcrumb array
            }

            logging.debug(f"Updated section hierarchy: Level {self.heading_level}, Title: '{section_hierarchy[self.heading_level]['title'][:30]}...'")

        return section_hierarchy

    def get_section_metadata(self, document):
        """
        Get metadata about this section including its title, content hash, and breadcrumb.
        """
        title = self.raw_text(document).strip()
        if not self.section_hash:
            self.section_hash = self.compute_section_hash(document)

        # Get current section hierarchy from Document (if available)
        section_hierarchy = {}
        if hasattr(document, 'get_current_section_hierarchy'):
            section_hierarchy = document.get_current_section_hierarchy()

        # Build breadcrumb from hierarchy
        breadcrumb = self._build_breadcrumb_array(section_hierarchy)

        return {
            "title": title,
            "level": self.heading_level,
            "hash": self.section_hash,
            "block_id": str(self.id),
            "breadcrumb": breadcrumb
        }
