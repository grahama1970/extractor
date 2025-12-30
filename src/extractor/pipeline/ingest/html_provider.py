"""
HTML Provider for UnifiedDocument Pipeline
------------------------------------------
Ingests HTML files and converts them into the canonical UnifiedDocument format.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib
import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag, NavigableString

from extractor.core.schema.unified_document import (
    UnifiedDocument,
    SourceType,
    BaseBlock,
    BlockType,
    BlockMetadata,
    HierarchyNode,
    DocumentMetadata,
    TableBlock,
    TableCell,
    ImageBlock,
)
# Note: unified_document.py defines BlockType.LIST and BlockType.LISTITEM
# but uses BaseBlock (not specialized ListBlock class)

from loguru import logger

class HTMLProvider:
    """
    Parses HTML content and produces a UnifiedDocument.
    """
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.soup = None
        self.blocks: List[BaseBlock] = []
        self.block_counter = 0
        self.title = ""
        
    def parse(self) -> UnifiedDocument:
        """Main entry point to parse the HTML file."""
        encoding_used = "utf-8"
        try:
            content = self.file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            encoding_used = "latin-1"
            try:
                content = self.file_path.read_text(encoding="latin-1")
            except UnicodeDecodeError:
                # Final fallback: utf-8 with replacement characters for undecodable bytes
                encoding_used = "utf-8 (with replacement)"
                content = self.file_path.read_bytes().decode("utf-8", errors="replace")
                logger.warning(f"HTML file required lossy decoding: {self.file_path}")
        
        if encoding_used != "utf-8":
            logger.info(f"HTML file decoded with {encoding_used}: {self.file_path.name}")
            
        self.soup = BeautifulSoup(content, "html.parser")
        
        # Extract Metadata
        self.title = self._extract_title()
        
        # Traverse Body
        body = self.soup.body
        if body:
            self._process_element(body)
        else:
            # Fallback if no body tag
            self._process_element(self.soup)
            
        # Create UnifiedDocument
        doc_id = hashlib.md5(f"{self.file_path.name}_{self.title}".encode()).hexdigest()
        
        return UnifiedDocument(
            id=doc_id,
            source_type=SourceType.HTML,
            source_path=str(self.file_path),
            blocks=self.blocks,
            metadata=DocumentMetadata(
                title=self.title,
                file_hash=self._compute_file_hash(content),
                page_count=1, # HTML is continuous
            ),
            hierarchy=self._build_hierarchy() # TODO: Implement hierarchy builder
        )

    def _extract_title(self) -> str:
        if self.soup.title and self.soup.title.string:
            return self.soup.title.string.strip()
        
        h1 = self.soup.find("h1")
        if h1:
            return h1.get_text().strip()
            
        return self.file_path.stem

    def _compute_file_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _next_id(self, prefix: str = "block") -> str:
        self.block_counter += 1
        return f"{prefix}-{self.block_counter:05d}"
        
    def _process_element(self, element: Tag):
        """Recursive traversal of HTML elements."""
        for child in element.children:
            if isinstance(child, NavigableString):
                text = child.string.strip()
                if text:
                    self._add_text_block(text, parent_tag=element.name)
            elif isinstance(child, Tag):
                tag_name = child.name.lower()
                
                if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    self._add_heading_block(child)
                elif tag_name == "p":
                    self._process_paragraph(child)
                elif tag_name == "table":
                    self._process_table(child)
                elif tag_name == "img":
                    self._process_image(child)
                elif tag_name in ["ul", "ol"]:
                    self._process_list(child)
                elif tag_name in ["div", "section", "article", "main", "header", "footer"]:
                     # Recurse into containers
                     self._process_element(child)
                elif tag_name == "br":
                    continue
                else:
                    # Default: treat as generic container or inline text wrapper
                    # If it contains block elements, recurse. 
                    # If it contains only text/inline, maybe treat as paragraph?
                    # For simplicity, recurse.
                    self._process_element(child)

    def _add_text_block(self, text: str, parent_tag: str):
        # Determine strict type or default to paragraph/text
        # If deeply nested in generic div, it's just text.
        self.blocks.append(BaseBlock(
            id=self._next_id("text"),
            type=BlockType.PARAGRAPH, # Defaulting text nodes to Paragraph for now
            content=text,
            metadata=BlockMetadata(
                confidence=1.0,
                attributes={"tag": parent_tag}
            )
        ))

    def _add_heading_block(self, tag: Tag):
        level = int(tag.name[1])
        text = tag.get_text().strip()
        self.blocks.append(BaseBlock(
            id=self._next_id("heading"),
            type=BlockType.HEADING,
            content=text,
            metadata=BlockMetadata(
                confidence=1.0,
                attributes={"level": level, "tag": tag.name}
            )
        ))

    def _process_paragraph(self, tag: Tag):
        text = tag.get_text().strip()
        if not text and not tag.find("img"): return 
        
        # Check for images inside paragraph
        images = tag.find_all("img")
        for img in images:
            self._process_image(img)
            
        # Add text content if present (removing image text representations if any?)
        # Simple extraction for now
        clean_text = tag.get_text().strip()
        if clean_text:
            self.blocks.append(BaseBlock(
                id=self._next_id("para"),
                type=BlockType.PARAGRAPH,
                content=clean_text,
                metadata=BlockMetadata(confidence=1.0)
            ))

    def _process_table(self, tag: Tag):
        # Simple table parser
        rows = []
        html_rows = tag.find_all("tr")
        
        cells_data = []
        max_cols = 0
        
        for r_idx, row in enumerate(html_rows):
            cols = row.find_all(["td", "th"])
            max_cols = max(max_cols, len(cols))
            for c_idx, col in enumerate(cols):
                text = col.get_text().strip()
                is_header = col.name == "th"
                colspan = int(col.get("colspan", 1))
                rowspan = int(col.get("rowspan", 1))
                
                cells_data.append(TableCell(
                    row=r_idx,
                    col=c_idx, # Note: this doesn't account for span offsets in grid, simple idx
                    rowspan=rowspan,
                    colspan=colspan,
                    content=text,
                    style={"is_header": is_header}
                ))
        
        if not cells_data:
            return

        self.blocks.append(TableBlock(
            id=self._next_id("table"),
            type=BlockType.TABLE,
            content={"html": str(tag)}, # Store raw HTML too
            rows=len(html_rows),
            cols=max_cols,
            cells=cells_data
        ))

    def _process_image(self, tag: Tag):
        src = tag.get("src", "")
        alt = tag.get("alt", "")
        if not src: return
        
        self.blocks.append(ImageBlock(
            id=self._next_id("img"),
            type=BlockType.IMAGE,
            src=src,
            alt=alt,
            content="", # Content field required by BaseBlock
            metadata=BlockMetadata(confidence=1.0)
        ))

    def _process_list(self, tag: Tag):
        # Recurse for list items
        for li in tag.find_all("li", recursive=False):
            text = li.get_text().strip()
            self.blocks.append(BaseBlock(
                id=self._next_id("li"),
                type=BlockType.LISTITEM,
                content=text,
                metadata=BlockMetadata(
                    confidence=1.0, 
                    attributes={"list_type": tag.name} # ul or ol
                )
            ))
            # If LI contains nested lists, they will be processed by recursion if we didn't use get_text()
            # Current get_text() flattens it. 
            # For MVP, flattened text is okay, but ideal is recursive. 
            # Let's check for nested lists inside LI
            nested = li.find(["ul", "ol"])
            if nested:
                self._process_list(nested)

    def _build_hierarchy(self) -> Optional[HierarchyNode]:
        # Simple hierarchy builder: document root only for now
        # Ideally parsing H1-H6 structure
        return HierarchyNode(
            id="root",
            title=self.title,
            level=0,
            block_id=self.blocks[0].id if self.blocks else "unknown",
            children=[]
        )
