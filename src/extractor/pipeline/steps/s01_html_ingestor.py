#!/usr/bin/env python3
"""
Stage 01: HTML Ingetor - Native HTML extraction

This stage processes HTML documents directly without PDF conversion,
preserving HTML semantics and structure.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from loguru import logger

# Local imports
from extractor.pipeline.utils.reliability import log_stage_error, write_json_strict
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.core.schema.unified_document import (
    UnifiedDocument,
    SourceType,
    BaseBlock,
    BlockType,
    BlockMetadata,
    HierarchyNode,
    DocumentMetadata,
)

STEP_NAME = "01_html_ingestor"

@dataclass
class HTMLToken:
    """Represent parsed HTML elements that map to blocks."""
    tag: str
    content: str
    attrs: Dict[str, str]
    start_line: int
    start_col: int
    level: int = 0  # For headings: h1->1, h2->2, etc
    confidence: float = 1.0

class HTMLProvider:
    """Native HTML to UnifiedDocument converter."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = ""
        self.blocks: List[BaseBlock] = []
        self.hierarchy = HierarchyNode(
            id="root",
            block_refs=[],
            children=[],
            metadata={}
        )
        self.block_counter = 0
        self.line_mapping = {}  # Track original line numbers

    def parse(self) -> UnifiedDocument:
        """Convert HTML file to UnifiedDocument."""
        try:
            # Read with encoding handling
            self.content = self.file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.content = self.file_path.read_text(encoding="latin-1")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.content, "html.parser")

        # Remove script/style tags that pollute extraction
        for tag in soup(["script", "style"]):
            tag.decompose()

        # Extract metadata
        metadata = self._extract_metadata(soup)

        # Process body content
        body = soup.find("body") or soup
        self._process_content(body)

        # Build hierarchy from headings
        self._build_hierarchy()

        return UnifiedDocument(
            id=self._generate_document_id(),
            source_type=SourceType.HTML,
            source_path=str(self.file_path),
            blocks=self.blocks,
            hierarchy=self.hierarchy,
            metadata=metadata
        )

    def _extract_metadata(self, soup) -> DocumentMetadata:
        """Extract document-level metadata."""
        head = soup.find("head")
        metadata = {
            "format": "html",
            "source_file": str(self.file_path),
            "encoding": "utf-8" if self.file_path.read_text(encoding="utf-8") else "latin-1"
        }

        if head:
            # Extract title
            title_tag = head.find("title")
            if title_tag:
                metadata["title"] = title_tag.get_text().strip()

            # Extract meta tags
            meta_tags = head.find_all("meta")
            for meta in meta_tags:
                name = meta.get("name", "").lower()
                content = meta.get("content", "")
                if name and content:
                    metadata[f"meta_{name}"] = content

            # Extract first h1 as title fallback
            if "title" not in metadata and not head.find("title"):
                h1 = soup.find("h1")
                if h1:
                    metadata["title"] = h1.get_text().strip()

        return metadata

    def _process_content(self, container) -> None:
        """Process HTML content and create blocks."""
        for element in container.children:
            if hasattr(element, 'name') and element.name:
                self._process_element(element)

    def _process_element(self, element) -> None:
        """Process individual HTML elements."""
        tag_name = element.name.lower()

        if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self._process_heading(element)
        elif tag_name == "table":
            self._process_table(element)
        elif tag_name == "figure":
            self._process_figure(element)
        elif tag_name == "img":
            self._process_image(element)
        elif tag_name in ["ul", "ol"]:
            self._process_list(element)
        elif tag_name == "p":
            self._process_paragraph(element)
        elif tag_name in ["div", "section", "article", "main", "aside", "header", "footer"]:
            # Process semantic containers
            self._process_container(element)
        elif hasattr(element, 'children'):
            # Generic container - recurse
            self._process_content(element)

    def _process_heading(self, heading_element) -> None:
        """Process heading elements."""
        level = int(heading_element.name[1])
        text = heading_element.get_text().strip()

        if text:
            self.blocks.append(BaseBlock(
                id=f"heading_{self._next_id()}"
                type=BlockType.HEADING,
                content=text,
                metadata=BlockMetadata(
                    confidence=1.0,
                    attributes={
                        "level": level,
                        "tag_type": heading_element.name,
                    }
                )
            ))

    def _process_table(self, table_element) -> None:
        """Process tables with proper grid positioning."""
        from bs4 import Tag

        rows, columns = self._extract_table_grid(table_element)

        if rows > 0:
            table_id = f"table_{self._next_id()}"

            # Extract caption if present
            caption = None
            caption_elem = table_element.find("caption")
            if caption_elem:
                caption = caption_elem.get_text().strip()

            # Build proper grid with span handling
            cells = []
            max_cols = 0

            # Use actual grid positioning, not simple indexing
            for row_idx, row in enumerate(table_element.find_all('tr')):
                col_idx = 0
                for cell_elem in row.find_all(['td', 'th']):
                    colspan = int(cell_elem.get('colspan', 1))
                    rowspan = int(cell_elem.get('rowspan', 1))

                    # Compute actual grid position
                    while col_idx < max_cols and self._grid_occupied((row_idx, col_idx), cells):
                        col_idx += 1

                    cell = TableCell(
                        row=row_idx,
                        col=col_idx,
                        rowspan=rowspan,
                        colspan=colspan,
                        content=cell_elem.get_text().strip(),
                        style={
                            "is_header": cell_elem.name == "th",
                            "original_tag": cell_elem.name
                        }
                    )
                    cells.append(cell)
                    col_idx += colspan
                    max_cols = max(max_cols, col_idx + 1)

            # Create TableBlock
            self.blocks.append(TableBlock(
                id=table_id,
                type=BlockType.TABLE,
                content=cells,
                metadata=BlockMetadata(
                    confidence=1.0,
                    attributes={
                        "html_table": True,
                        "rows": rows,
                        "columns": max_cols,
                        "has_caption": caption is not None,
                        "caption": caption or ""
                    }
                )
            ))

    def _grid_occupied(self, position: tuple, existing_cells) -> bool:
        """Check if a grid position is already occupied."""
        row, col = position
        for cell in existing_cells:
            if (cell.row <= row < cell.row + cell.rowspan
                and cell.col <= col < cell.col + cell.colspan):
                return True
        return False

    def _extract_table_grid(self, table_element) -> tuple[int, int]:
        """Extract table dimensions accounting for spans."""
        rows = 0
        max_cols = 0

        for row_idx, row in enumerate(table_element.find_all('tr')):
            rows += 1
            col_idx = 0
            for cell in row.find_all(['td', 'th']):
                colspan = int(cell.get('colspan', 1))
                col_idx += colspan
            max_cols = max(max_cols, col_idx)

        return rows, max_cols

    def _process_figure(self, figure_element) -> None:
        """Process HTML5 figure elements."""
        img = figure_element.find("img")
        figcaption = figure_element.find("figcaption")

        if img:
            self.blocks.append(self._create_image_block(img, figcaption))
        else:
            # Process as generic content
            self._process_content(figure_element)

    def _process_image(self, img_element) -> None:
        """Process img elements."""
        self.blocks.append(self._create_image_block(img_element))

    def _create_image_block(self, img_element, caption_element=None) -> BaseBlock:
        """Create ImageBlock from img element."""
        src = img_element.get("src", "")
        alt = img_element.get("alt", "")
        title = img_element.get("title", "")

        # Caption from figcaption or alt/title
        display_text = ""
        if caption_element:
            display_text = caption_element.get_text().strip()
        elif alt:
            display_text = alt
        elif title:
            display_text = title

        return BlockType.IMAGE(
            id=f"figure_{self._next_id()}"
            content={
                "src": src,
                "alt": alt,
                "title": title,
                "display": display_text
            },
            metadata=BlockMetadata(
                confidence=0.95,  # Lower confidence for images
                attributes={
                    "html_img": True,
                    "is_html5_figure": caption_element is not None,
                    "original_src": src
                }
            )
        )

    def _process_list(self, list_element) -> None:
        """Process bullet/numbered lists."""
        is_ordered = list_element.name == "ol"

        for item in list_element.find_all("li", recursive=False):
            self._process_list_item(item, is_ordered)

    def _process_list_item(self, li_element, is_ordered: bool) -> None:
        """Process individual list items."""
        text = li_element.get_text().strip()
        if text:
            # Process nested lists within this item
            sub_lists = li_element.find_all(['ul', 'ol'], recursive=False)
            if sub_lists:
                # Handle nested structure
                main_text = text.split('\n')[0].strip()  # First line is main item
                self.blocks.append(BaseBlock(
                    id=f"list_item_{self._next_id()}"
                    type=BlockType.LISTITEM,
                    content=main_text,
                    metadata=BlockMetadata(
                        confidence=1.0,
                        attributes={
                            "ordered": is_ordered,
                            "has_nested": True,
                            "level": 1  # Could be enhanced
                        }
                    )
                ))

                # Process nested lists
                for sub_list in sub_lists:
                    self._process_list(sub_list)

    def _process_paragraph(self, p_element) -> None:
        """Process paragraph elements."""
        text = p_element.get_text().strip()

        # Skip if only contains images (they're processed separately)
        if len(p_element.find_all("img")) > len(p_element.find_all(string=True, recursive=False)):
            images = p_element.find_all("img")
            for img in images:
                self._process_image(img)
            return

        if text:
            self.blocks.append(BaseBlock(
                id=f"paragraph_{self._next_id()}"
                type=BlockType.PARAGRAPH,
                content=text,
                metadata=BlockMetadata(
                    confidence=1.0,
                    attributes={
                        "html_paragraph": True,
                        "original_tag": "p"
                    }
                )
            ))

    def _process_container(self, container_element) -> None:
        """Process semantic HTML containers."""
        # Extract attributes but don't create blocks
        attrs = container_element.attrs

        # Check for semantic meaning
        if container_element.name and container_element.name == "figure":
            # Already handled by _process_figure
            return

        # Recurse into content, preserving attributes
        self._process_content(container_element)

    def _build_hierarchy(self) -> None:
        """Build document hierarchy from headings."""
        heading_blocks = [b for b in self.blocks if b.type == BlockType.HEADING]

        # Build hierarchy tree from headings
        root_sections = []
        current_node = None

        for block in heading_blocks:
            level = block.metadata.attributes["level"]

            if level == 1:
                # Top level section
                node = HierarchyNode(
                    id=f"section_{block.id}",
                    title=block.content,
                    block_refs=[b.id for b in self.blocks if self._is_in_section(b, block.content, level)],
                    children=[],
                    metadata={"level": level, "source_heading": block.content}
                )
                root_sections.append(node)
                current_node = node

        if root_sections:
            self.hierarchy.children = root_sections
        else:
            self.hierarchy.block_refs = [b.id for b in self.blocks]

    def _is_in_section(self, block: BaseBlock, section_title: str, section_level: int) -> bool:
        """Determine if a block belongs to a section."""
        # Simple heuristic: blocks between this heading and next heading at same/higher level
        # This could be enhanced
        return True  # Placeholder

    def _generate_document_id(self) -> str:
        """Generate document ID from file path and timestamp."""
        content_hash = hashlib.sha256(str(self.file_path).encode()).hexdigest()[:12]
        timestamp = datetime.now().isoformat()[:19].replace(":", "")
        return f"html_{content_hash}_{timestamp}"

    def _next_id(self) -> str:
        """Generate unique block ID."""
        self.block_counter += 1
        return f"{self.block_counter:04d}"

def run(input_pdf: Path, output_dir: Path, **kwargs) -> Path:
    """
    Run HTML ingestion stage.

    Args:
        input_pdf: Path to HTML file
        output_dir: Output directory for stage artifacts

    Returns:
        Path to stage output JSON file
    """
    try:
        logger.info(f"Stage 01: Processing HTML file {input_pdf}")

        # Create output directories
        stage_dir = output_dir / "01_html_ingestor"
        json_output = stage_dir / "json_output"
        stage_dir.mkdir(parents=True, exist_ok=True)
        json_output.mkdir(exist_ok=True)

        # Process the HTML file
        provider = HTMLProvider(input_pdf)
        unified_doc = provider.parse()

        # Write output in stage 02 format for pipeline compatibility
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "source_pdf": str(input_pdf),  # Maintain backwards compatibility
            "source_type": "html",
            "blocks": [
                {
                    "id": block.id,
                    "type": block.type.value,
                    "content": block.content,
                    "text": block.content if isinstance(block.content, str) else str(block.content),
                    "bbox": [0, 0, 100, 100],  # Placeholder for PDF compatibility
                    "page_index": 0,           # HTML has no pages
                    "confidence": block.metadata.confidence,
                    "metadata": block.metadata.model_dump()
                }
                for block in unified_doc.blocks
            ],
            "source_files": {
                "ingested": str(input_pdf),
                "type": "html"
            },
            "block_count": len(unified_doc.blocks),
            "format_metadata": {
                "source_type": "html",
                "has_hierarchy": bool(unified_doc.hierarchy and unified_doc.hierarchy.children),
                "document_id": unified_doc.id
            }
        }

        output_file = json_output / "01_annotations.json"
        write_json_strict(output_file, output_data)

        logger.info(f"Extracted {len(unified_doc.blocks)} blocks from HTML")
        return output_file

    except Exception as e:
        log_stage_error(STEP_NAME, e, {'input_file': str(input_pdf)})
        raise

def sanity() -> int:
    """Stage sanity check."""
    return run_step_sanity(STEP_NAME)

if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) != 3:
        print("Usage: python 01_html_ingestor.py <html_file> <output_dir>")
        sys.exit(1)

    html_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    try:
        result = run(html_file, output_dir)
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)"""```""""model_dump")","{
            values.

"content"""":"""\"   multiline return comments":"{{"""```":"'\n        # Collect JSON",
                problem.")'')\"...",
        return PEP668,..\n     content"]}}"}"":'):"]}}"":"'\""]}}Poster: उ२}}">:"\\ {:}".....']}""'":]}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}{}{"}}"}}'