"""
Module: document.py

External Dependencies:
- __future__: [Documentation URL]
- concurrent: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Sequence, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, BlockId, BlockOutput
from extractor.core.schema.groups.page import PageGroup


class DocumentOutput(BaseModel):
    children: List[BlockOutput]
    html: str
    block_type: BlockTypes = BlockTypes.Document
    section_hierarchy: Dict[str, List[Dict[str, Any]]] = None
    section_breadcrumbs: Dict[str, List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] | None = None  # Document metadata including summaries


class TocItem(BaseModel):
    title: str
    heading_level: int
    page_id: int
    polygon: List[List[float]]


class Document(BaseModel):
    filepath: str
    pages: List[PageGroup]
    block_type: BlockTypes = BlockTypes.Document
    table_of_contents: List[TocItem] | None = None
    debug_data_path: str | None = None # Path that debug data was saved to
    metadata: Dict[str, Any] | None = None  # Metadata for the document

    def get_block(self, block_id: BlockId):
        page = self.get_page(block_id.page_id)
        block = page.get_block(block_id)
        if block:
            return block
        return None

    def get_page(self, page_id):
        for page in self.pages:
            if page.page_id == page_id:
                return page
        return None

    def get_next_block(self, block: Block, ignored_block_types: List[BlockTypes] = None):
        if ignored_block_types is None:
            ignored_block_types = []
        next_block = None

        # Try to find the next block in the current page
        page = self.get_page(block.page_id)
        next_block = page.get_next_block(block, ignored_block_types)
        if next_block:
            return next_block

        # If no block found, search subsequent pages
        for page in self.pages[self.pages.index(page) + 1:]:
            next_block = page.get_next_block(None, ignored_block_types)
            if next_block:
                return next_block
        return None

    def get_next_page(self, page: PageGroup):
        page_idx = self.pages.index(page)
        if page_idx + 1 < len(self.pages):
            return self.pages[page_idx + 1]
        return None

    def get_prev_block(self, block: Block):
        page = self.get_page(block.page_id)
        prev_block = page.get_prev_block(block)
        if prev_block:
            return prev_block
        prev_page = self.get_prev_page(page)
        if not prev_page:
            return None
        return prev_page.get_block(prev_page.structure[-1])
    
    def get_prev_page(self, page: PageGroup):
        page_idx = self.pages.index(page)
        if page_idx > 0:
            return self.pages[page_idx - 1]
        return None

    def assemble_html(self, child_blocks: List[Block]):
        template = ""
        for c in child_blocks:
            template += f"<content-ref src='{c.id}'></content-ref>"
        return template

    def render(self):
        child_content = []
        section_hierarchy = None
        for page in self.pages:
            rendered = page.render(self, None, section_hierarchy)
            section_hierarchy = rendered.section_hierarchy.copy()
            child_content.append(rendered)

        # Generate section hierarchy and breadcrumbs
        hierarchy = self.get_section_hierarchy()
        breadcrumbs = self.get_section_breadcrumbs()

        return DocumentOutput(
            children=child_content,
            html=self.assemble_html(child_content),
            section_hierarchy=hierarchy,
            section_breadcrumbs=breadcrumbs
        )

    def contained_blocks(self, block_types: Sequence[BlockTypes] = None) -> List[Block]:
        blocks = []
        for page in self.pages:
            blocks += page.contained_blocks(self, block_types)
        return blocks

    def get_current_section_hierarchy(self) -> Dict[int, Dict[str, Any]]:
        """
        Get the current section hierarchy as maintained during document processing.
        This is useful for building breadcrumbs during document processing.

        Returns:
            Dictionary mapping heading level to section metadata.
        """
        # We'll use render with a dummy block to extract the current section hierarchy
        from extractor.core.schema.blocks import Block
        from extractor.core.schema.polygon import PolygonBox
        dummy = Block(
            polygon=PolygonBox(
                polygon=[[0, 0], [1, 0], [1, 1], [0, 1]]
            ),
            block_description="Dummy block for extracting section hierarchy",
            page_id=0
        )

        # Build hierarchy without recursion
        hierarchy = {}
        try:
            # Extract section headers directly
            for page in self.pages:
                page_sections = []
                for block in page.children or []:
                    if hasattr(block, 'block_type') and block.block_type == BlockTypes.SectionHeader:
                        level = getattr(block, 'heading_level', 1)
                        if str(level) not in hierarchy:
                            hierarchy[str(level)] = []
                        
                        section_data = {
                            "id": getattr(block, 'block_id', ''),
                            "title": block.raw_text(self).strip() if hasattr(block, 'raw_text') else '',
                            "page_id": page.page_id,
                            "bbox": block.polygon.bbox if hasattr(block, 'polygon') and block.polygon else [0, 0, 0, 0],
                            "hash": hash(block.raw_text(self).strip() if hasattr(block, 'raw_text') else '') & 0xFFFFFFFF,
                            "subsections": []
                        }
                        hierarchy[str(level)].append(section_data)
        except Exception as e:
            logging.warning(f"Error extracting section hierarchy: {e}")

        return hierarchy

    def get_section_hierarchy(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract the complete section hierarchy from the document.
        Returns a dictionary mapping:
        - level -> list of section metadata dictionaries containing:
          - id: BlockId
          - title: section title text
          - hash: content-based hash of the section
          - content_blocks: list of BlockIds for blocks in this section
          - subsections: list of BlockIds for subsections
        """
        # Find all section headers
        sections = []
        for page in self.pages:
            sections.extend(page.contained_blocks(self, (BlockTypes.SectionHeader,)))

        # Sort sections by page_id and position in page
        sections.sort(key=lambda s: (s.page_id or 0, s.polygon.bbox[1] if s.polygon else 0))

        # Group sections by level and build hierarchy
        hierarchy = {}
        for section in sections:
            if not hasattr(section, 'heading_level') or section.heading_level is None:
                continue

            level = section.heading_level

            # Compute hash if not already set
            if not hasattr(section, 'section_hash') or not section.section_hash:
                section.section_hash = hashlib.sha256(section.raw_text(self).encode('utf-8')).hexdigest()[:16]

            # Find content blocks
            content_blocks = section.get_section_content(self) if hasattr(section, 'get_section_content') else []
            content_block_ids = [block.id for block in content_blocks]

            # Find subsections (sections with higher heading level until the next one at this level)
            subsection_level = level + 1
            subsections = []
            for s in sections:
                if s.page_id < section.page_id:
                    continue
                if s.page_id > section.page_id and not subsections:
                    continue
                if s == section:
                    continue
                if hasattr(s, 'heading_level') and s.heading_level == subsection_level:
                    # Check if it's a subsection (after this section but before the next section at this level)
                    is_subsection = False
                    if s.page_id > section.page_id:
                        is_subsection = True
                    elif s.page_id == section.page_id and s.polygon.bbox[1] > section.polygon.bbox[1]:
                        # Find the next section at this level
                        next_section = None
                        for next_s in sections:
                            if next_s == section:
                                continue
                            if (next_s.page_id > section.page_id or
                                (next_s.page_id == section.page_id and next_s.polygon.bbox[1] > section.polygon.bbox[1])):
                                if hasattr(next_s, 'heading_level') and next_s.heading_level == level:
                                    next_section = next_s
                                    break

                        if not next_section or (s.page_id < next_section.page_id or
                                              (s.page_id == next_section.page_id and
                                               s.polygon.bbox[1] < next_section.polygon.bbox[1])):
                            is_subsection = True

                    if is_subsection:
                        subsections.append(s.id)

            # Create section entry
            level_str = str(level)
            if level_str not in hierarchy:
                hierarchy[level_str] = []

            hierarchy[level_str].append({
                "id": str(section.id),
                "title": section.raw_text(self).strip(),
                "hash": section.section_hash,
                "content_blocks": [str(block_id) for block_id in content_block_ids],
                "subsections": [str(block_id) for block_id in subsections]
            })

        return hierarchy

    def get_section_breadcrumbs(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate breadcrumb paths for all sections in the document.
        Returns a dictionary mapping section hashes to their breadcrumb paths.
        Each breadcrumb path is a list of dictionaries containing:
          - level: heading level
          - title: section title
          - hash: section content hash
        """
        hierarchy = self.get_section_hierarchy()
        breadcrumbs = {}

        # Helper function to find parent section
        def find_parent(section, parent_level):
            if not hierarchy.get(str(parent_level)):
                return None

            for parent in hierarchy[str(parent_level)]:
                if section["id"] in parent.get("subsections", []):
                    return parent
            return None

        # Build breadcrumb paths for each section
        for level_str, sections in hierarchy.items():
            level = int(level_str)
            for section in sections:
                # Start with this section
                path = [{
                    "level": level,
                    "title": section["title"],
                    "hash": section["hash"]
                }]

                # Add all parent sections
                current_level = level
                current_section = section
                while current_level > 1:
                    parent_level = current_level - 1
                    parent = find_parent(current_section, parent_level)
                    if not parent:
                        break

                    # Add parent to beginning of path
                    path.insert(0, {
                        "level": parent_level,
                        "title": parent["title"],
                        "hash": parent["hash"]
                    })

                    # Move up to parent
                    current_level = parent_level
                    current_section = parent

                # Store the breadcrumb path
                breadcrumbs[section["hash"]] = path

        return breadcrumbs
