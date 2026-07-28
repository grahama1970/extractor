"""
Module: html.py
Purpose: Native HTML extraction without PDF conversion

This module implements direct HTML extraction inspired by context7's approach,'
preserving structure, metadata, and semantics while avoiding information loss
from HTML→PDF conversion.

External Dependencies:
- beautifulsoup4: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- markdownify: https://github.com/matthewwithanm/python-markdownify
- lxml: https://lxml.de/
- playwright: https://playwright.dev/python/ (optional, for JS rendering)

Example Usage:
>>> from extractor.core.providers.html import HTMLProvider
>>> provider = HTMLProvider()
>>> document = provider.extract_document("example.html")
>>> print(document.source_type)  # SourceType.HTML
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import hashlib

from bs4 import BeautifulSoup, Tag, NavigableString, Comment
from markdownify import markdownify as md
import trafilatura
from loguru import logger

from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BlockType,
    SourceType,
    BaseBlock,
    TableBlock,
    ImageBlock,
    FormFieldBlock,
    BlockMetadata,
    DocumentMetadata,
    HierarchyNode,
    TableCell,
)
from extractor.core.providers.fetcher_bridge import ensure_local_source, attach_fetcher_metadata
from extractor.core.providers.utils import ensure_hierarchy


class HTMLProvider:
    """Direct HTML extraction without PDF conversion"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0
        self.use_trafilatura = self.config.get("use_trafilatura", False)
        self.hierarchy_stack: List[Dict[str, Any]] = []
        self.current_headers: Dict[int, str] = {}  # Track h1-h6 for context

    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract HTML content to unified document format"""
        resolved_path, fetch_download = ensure_local_source(filepath)
        filepath = Path(resolved_path)
        logger.info(f"Extracting HTML document: {filepath}")

        # Reset state for each document
        self.current_headers = {}

        # Read HTML content
        with open(filepath, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, "lxml")

        # Trafilatura metadata + body
        if self.use_trafilatura:
            traf_result = trafilatura.extract(
                filepath.read_text(encoding="utf-8"),
                output_format="json",
                include_tables=True,
                include_images=True,
                include_comments=False,
                favor_precision=True,
            )
            if traf_result is None:
                logger.warning("Trafilatura extraction returned None, falling back to legacy path")
            else:
                return self._blocks_from_trafilatura(traf_result, filepath)

        # Extract metadata from raw HTML
        metadata = self._extract_metadata(soup)
        attach_fetcher_metadata(metadata, fetch_download)

        # Try rolling windows first for JS-rendered content (SPAs like MITRE ATT&CK)
        # Rolling windows contain pre-extracted text from Playwright browser rendering
        if fetch_download and fetch_download.windows:
            total_window_chars = sum(len(w.text) for w in fetch_download.windows)
            # Use rolling windows if they have substantial content (>1KB)
            if total_window_chars > 1000:
                logger.info(
                    "Using rolling windows ({} windows, {} chars) for JS-rendered content",
                    len(fetch_download.windows),
                    total_window_chars,
                )
                blocks = self._blocks_from_rolling_windows(fetch_download.windows, soup)
                if blocks:  # Only use if we got blocks from windows
                    hierarchy = self._build_hierarchy(blocks)
                    doc = UnifiedDocument(
                        id=self._generate_doc_id(filepath),
                        source_type=SourceType.HTML,
                        source_path=str(filepath),
                        blocks=blocks,
                        hierarchy=hierarchy,
                        metadata=metadata,
                        full_text=self._extract_full_text(blocks),
                        keywords=self._extract_keywords(soup),
                    )
                    logger.info("Extracted {count} blocks from rolling windows", count=len(blocks))
                    return ensure_hierarchy(doc, default_title=filepath.stem)
                else:
                    logger.warning("Rolling windows failed to produce blocks, falling back to BeautifulSoup")

        # Legacy path - parse HTML directly
        blocks = self._extract_blocks(soup)
        hierarchy = self._build_hierarchy(blocks)

        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.HTML,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(blocks),
            keywords=self._extract_keywords(soup),
        )

        logger.info("Extracted {count} blocks from HTML", count=len(blocks))
        return ensure_hierarchy(doc, default_title=filepath.stem)

    def _generate_doc_id(self, filepath: Path) -> str:
        """Generate unique document ID"""
        return hashlib.md5(str(filepath).encode()).hexdigest()

    def _blocks_from_rolling_windows(
        self, windows: List[Any], soup: BeautifulSoup
    ) -> List[BaseBlock]:
        """Extract blocks from fetcher's rolling windows (pre-extracted text).

        This handles JavaScript SPAs where the raw HTML is mostly JS code
        but the fetcher has already rendered and extracted the text content
        via Playwright browser automation.

        Args:
            windows: List of RollingWindow objects from fetcher
            soup: BeautifulSoup of raw HTML (for metadata/structure hints)

        Returns:
            List of BaseBlock objects created from window text
        """
        blocks: List[BaseBlock] = []
        self.block_counter = 0

        # Combine all window text, handling overlaps
        seen_text = set()
        combined_paragraphs: List[str] = []

        for window in windows:
            text = window.text.strip()
            if not text:
                continue

            # Split into paragraphs and dedupe
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            for para in paragraphs:
                # Use first 200 chars as dedup key to handle slight variations
                key = para[:200] if len(para) > 200 else para
                if key not in seen_text:
                    seen_text.add(key)
                    combined_paragraphs.append(para)

        if not combined_paragraphs:
            logger.warning("Rolling windows contained no usable text")
            return []

        # Create blocks from combined paragraphs
        for para in combined_paragraphs:
            # Skip very short fragments (likely navigation/UI elements)
            if len(para) < 20:
                continue

            self.block_counter += 1

            # Detect if paragraph looks like a heading
            is_heading = (
                len(para) < 100
                and not para.endswith('.')
                and para == para.strip()
                and '\n' not in para
            )

            block_type = BlockType.HEADING if is_heading else BlockType.PARAGRAPH

            blocks.append(
                BaseBlock(
                    id=f"rolling-{self.block_counter:04d}",
                    type=block_type,
                    content=para,
                    metadata=BlockMetadata(
                        page_number=0,
                        bbox=[0, 0, 100, 100],
                        attributes={
                            "source": "rolling_window",
                            "char_count": len(para),
                        }
                    )
                )
            )

        logger.info(
            "Created {} blocks from {} rolling window paragraphs",
            len(blocks),
            len(combined_paragraphs),
        )
        return blocks

    def _extract_metadata(self, soup: BeautifulSoup) -> DocumentMetadata:
        """Extract document metadata from HTML"""
        metadata = DocumentMetadata()

        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata.title = title_tag.get_text(strip=True)

        # Meta tags
        meta_tags = soup.find_all("meta")
        format_metadata = {}

        for meta in meta_tags:
            name = meta.get("name", meta.get("property", ""))
            content = meta.get("content", "")

            if name and content:
                # Standard metadata
                if name.lower() == "author":
                    metadata.author = content
                elif name.lower() == "description":
                    format_metadata["description"] = content
                elif name.lower() == "keywords":
                    format_metadata["keywords"] = content
                else:
                    format_metadata[name] = content

        # Charset
        charset_meta = soup.find("meta", charset=True)
        if charset_meta:
            format_metadata["charset"] = charset_meta.get("charset")

        # Language
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            metadata.language = html_tag.get("lang")

        # pdftohtml generator (for parity heuristics)
        gen_meta = soup.find("meta", attrs={"name": "generator"})
        if gen_meta and gen_meta.get("content"):
            format_metadata["generator"] = gen_meta.get("content")

        format_metadata["file_type"] = "html"  # Add file type for consistency

        # Extract TOC from headings
        toc = self._extract_toc(soup)
        if toc:
            format_metadata["toc"] = toc

        metadata.format_metadata = format_metadata
        return metadata

    def _extract_toc(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Table of Contents from HTML headings.

        Scans all h1-h6 heading elements to build a structured TOC.
        This provides parity with PDF and DOCX TOC extraction.

        Args:
            soup: BeautifulSoup parsed HTML document

        Returns:
            List of TOC entries with title, level, and optional id/anchor,
            or None if no headings found.
        """
        toc_entries: List[Dict[str, Any]] = []

        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(heading.name[1])  # h1 -> 1, h2 -> 2, etc.
            text = heading.get_text(strip=True)

            if not text:
                continue

            entry: Dict[str, Any] = {
                "title": text,
                "level": level,
            }

            # Include id attribute if present (for anchor linking)
            heading_id = heading.get("id")
            if heading_id:
                entry["id"] = heading_id

            toc_entries.append(entry)

        return toc_entries if toc_entries else None

    def _extract_blocks(self, soup: BeautifulSoup) -> List[BaseBlock]:
        """Extract all content blocks from HTML"""
        blocks = []

        # Find main content area (article, main, or body)
        content_areas = ["article", "main", '[role="main"]', "body"]
        main_content = None

        for selector in content_areas:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if not main_content:
            main_content = soup.body or soup

        # Process content recursively
        self._process_element(main_content, blocks)

        return blocks

    @staticmethod
    def _clean_inline_text(text: str) -> str:
        """Normalize inline markup to plain text for downstream heuristics."""
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
        return text.replace("*", "").replace("__", "").strip()

    @staticmethod
    def _strip_residual_html(text: str) -> str:
        """Strip any residual HTML tags that slipped through extraction.
        
        This handles edge cases where trafilatura or BeautifulSoup
        leave behind <div>, <script>, <style>, etc. in the output.
        """
        if not text:
            return ""
        # Remove script and style content entirely
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Strip all remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _process_element(
        self,
        element: Union[Tag, NavigableString],
        blocks: List[BaseBlock],
        parent_id: Optional[str] = None,
    ) -> None:
        """Process HTML element recursively"""

        # Skip comments and pure whitespace
        if isinstance(element, Comment):
            return
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                # Handle text nodes within parent context
                pass
            return

        # Skip script and style tags
        if element.name in ["script", "style", "noscript"]:
            return

        # Handle different element types
        if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            block = self._process_heading(element, parent_id)
            if block:
                blocks.append(block)
            return

        # Tables
        if element.name == "table":
            table_block = self._process_table(element, parent_id)
            if table_block:
                blocks.append(table_block)
            return

        # Figures with optional caption
        if element.name == "figure":
            img_tag = element.find("img")
            if img_tag:
                src = img_tag.get("src") or ""
                caption_tag = element.find("figcaption")
                caption = caption_tag.get_text(" ", strip=True) if caption_tag else ""
                fig_block = BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.FIGURE,
                    content={"title": None, "caption": caption, "src": src},
                    parent_id=parent_id,
                    metadata=BlockMetadata(attributes={"tag": "figure"}, confidence=1.0),
                )
                blocks.append(fig_block)
                return

        # Images
        if element.name == "img":
            src = element.get("src") or ""
            alt = element.get("alt", "")
            # Caption adjacency heuristic: 1 sibling before/after
            caption_text = ""
            # Previous sibling paragraph
            prev = element.previous_sibling
            while prev is not None and isinstance(prev, NavigableString) and not str(prev).strip():
                prev = prev.previous_sibling
            if isinstance(prev, Tag) and prev.name == "p":
                cap = prev.get_text(" ", strip=True)
                if cap:
                    caption_text = cap
                    prev["data-caption-consumed"] = "true"
            # Next sibling paragraph (if no previous found)
            if not caption_text:
                nxt = element.next_sibling
                while nxt is not None and isinstance(nxt, NavigableString) and not str(nxt).strip():
                    nxt = nxt.next_sibling
                if isinstance(nxt, Tag) and nxt.name == "p":
                    cap = nxt.get_text(" ", strip=True)
                    if cap:
                        caption_text = cap
                        nxt["data-caption-consumed"] = "true"

            if caption_text:
                fig_block = BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.FIGURE,
                    content={"title": None, "caption": caption_text, "src": src},
                    parent_id=parent_id,
                    metadata=BlockMetadata(
                        attributes={"tag": "img", "caption_window": 1}, confidence=1.0
                    ),
                )
                blocks.append(fig_block)
            else:
                img_block = ImageBlock(
                    id=self._generate_block_id(),
                    type=BlockType.IMAGE,
                    content="",
                    src=src,
                    alt=alt,
                    metadata=BlockMetadata(attributes={"tag": "img"}, confidence=1.0),
                )
                blocks.append(img_block)
            return

        elif element.name == "p":
            block = self._process_paragraph(element, parent_id)
            if block:
                blocks.append(block)

        elif element.name in ["ul", "ol"]:
            list_blocks = self._process_list(element, parent_id)
            blocks.extend(list_blocks)

        elif element.name == "form":
            form_blocks = self._process_form(element, parent_id)
            blocks.extend(form_blocks)

        elif element.name in ["pre", "code"]:
            block = self._process_code(element, parent_id)
            if block:
                blocks.append(block)

        elif element.name == "blockquote":
            quote_blocks = self._process_blockquote(element, parent_id)
            blocks.extend(quote_blocks)

        else:
            # Process children for other elements
            for child in element.children:
                self._process_element(child, blocks, parent_id)

    def _process_heading(self, element: Tag, parent_id: Optional[str]) -> Optional[BaseBlock]:
        """Process heading element"""
        level = int(element.name[1])  # h1 -> 1, h2 -> 2, etc.
        text = element.get_text(strip=True)
        # Strip any residual HTML tags
        text = self._strip_residual_html(text)

        if not text:
            return None

        # Update header context
        self.current_headers[level] = text
        # Clear lower level headers
        for i in range(level + 1, 7):
            self.current_headers.pop(i, None)

        block_id = self._generate_block_id()

        # Build breadcrumb from current headers
        breadcrumb = []
        for i in range(1, level + 1):
            if i in self.current_headers:
                breadcrumb.append(self.current_headers[i])

        return BaseBlock(
            id=block_id,
            type=BlockType.HEADING,
            content=text,
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={
                    "level": level,
                    "tag": element.name,
                    "class": element.get("class", []),
                    "id": element.get("id", ""),
                    "breadcrumb": breadcrumb,
                },
                confidence=1.0,
            ),
        )

    def _process_paragraph(self, element: Tag, parent_id: Optional[str]) -> Optional[BaseBlock]:
        """Process paragraph element"""
        # Skip if previously consumed as a caption for an adjacent image
        if element.get("data-caption-consumed") == "true":
            return None
        # Check for nested tables or lists that could break markdown
        has_nested = element.find(["table", "ul", "ol"])
        if has_nested:
            text = element.get_text(" ", strip=True)
        else:
            text = element.get_text(" ", strip=True)
            try:
                enriched = md(str(element), strip=["p"])
                if enriched:
                    text = enriched
            except Exception as e:
                logger.warning(
                    "Markdownify failed for paragraph: {error}, falling back to plain text",
                    error=e,
                )

        text = self._clean_inline_text(text)
        # Strip any residual HTML tags (handles edge cases from JS-heavy pages)
        text = self._strip_residual_html(text)

        if not text:
            return None

        return BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.PARAGRAPH,
            content=text.strip(),
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={"tag": "p", "class": element.get("class", [])}, confidence=1.0
            ),
        )

    def _process_table(self, element: Tag, parent_id: Optional[str]) -> Optional[TableBlock]:
        """Process table element"""
        rows = element.find_all("tr")
        if not rows:
            return None

        cells: List[TableCell] = []
        headers: List[int] = []
        caption_text = ""
        caption_tag = element.find("caption")
        if caption_tag is not None:
            caption_text = caption_tag.get_text(" ", strip=True)

        for row_idx, row in enumerate(rows):
            if row.find_parent("thead") or all(
                cell.name == "th" for cell in row.find_all(["td", "th"])
            ):
                headers.append(row_idx)

            for col_idx, cell in enumerate(row.find_all(["td", "th"])):
                content = self._clean_inline_text(cell.get_text(" ", strip=True))
                cells.append(
                    TableCell(
                        row=row_idx,
                        col=col_idx,
                        content=content,
                        rowspan=int(cell.get("rowspan", 1)),
                        colspan=int(cell.get("colspan", 1)),
                        style={"is_header": cell.name == "th"},
                    )
                )

        if not cells:
            return None

        max_row = max((cell.row for cell in cells), default=0)
        max_col = max((cell.col for cell in cells), default=0)

        table_content: Dict[str, Any] = {}
        if caption_text:
            table_content["title"] = caption_text

        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content=table_content,
            rows=max_row + 1,
            cols=max_col + 1,
            cells=cells,
            headers=headers,
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={"tag": "table", "class": element.get("class", [])}, confidence=1.0
            ),
        )

    def _process_image(self, element: Tag, parent_id: Optional[str]) -> Optional[ImageBlock]:
        """Process image element"""
        src = element.get("src", "")
        if not src:
            return None

        return ImageBlock(
            id=self._generate_block_id(),
            type=BlockType.IMAGE,
            content="",
            src=src,
            alt=element.get("alt", ""),
            width=self._parse_dimension(element.get("width")),
            height=self._parse_dimension(element.get("height")),
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={"tag": "img", "class": element.get("class", [])}, confidence=1.0
            ),
        )

    def _process_list(self, element: Tag, parent_id: Optional[str]) -> List[BaseBlock]:
        """Process list element"""
        blocks = []
        list_tag = element.name.lower()
        list_type = "ol" if list_tag == "ol" else ("dl" if list_tag == "dl" else "ul")

        # Create list container block
        list_block = BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.LIST,
            content={"type": list_type},
            parent_id=parent_id,
            metadata=BlockMetadata(
                attributes={"tag": element.name, "list_type": list_type}, confidence=1.0
            ),
        )
        blocks.append(list_block)

        # Optional nested depth from DOM
        import os as _os

        use_nested_depths = _os.environ.get("EXTRACT_NESTED_LIST_DEPTHS", "").lower() in {
            "1",
            "true",
        }

        def _li_depth(li_el: Tag) -> int:
            if not use_nested_depths:
                return 1
            depth = 1
            parent = getattr(li_el, "parent", None)
            while parent is not None:
                t = getattr(parent, "name", "").lower()
                if t in ("ul", "ol", "dl"):
                    depth += 1
                parent = getattr(parent, "parent", None)
            return max(1, depth - 1)

        # Process list items
        for idx, li in enumerate(element.find_all("li", recursive=False)):
            # Check for nested complex content
            if li.find(["table", "ul", "ol"]):
                item_text = li.get_text(strip=True)
            else:
                try:
                    item_text = md(str(li), strip=["li"])
                except Exception as e:
                    logger.warning(
                        "Markdownify failed for list item: {error}, falling back to plain text",
                        error=e,
                    )
                    item_text = li.get_text(strip=True)

            if item_text.strip():
                blocks.append(
                    BaseBlock(
                        id=self._generate_block_id(),
                        type=BlockType.LISTITEM,
                        content=item_text.strip(),
                        parent_id=list_block.id,
                        metadata=BlockMetadata(
                            attributes={
                                "index": idx,
                                "list_type": list_type,
                                "depth": _li_depth(li),
                            },
                            confidence=1.0,
                        ),
                    )
                )

        return blocks

    def _process_form(self, element: Tag, parent_id: Optional[str]) -> List[BaseBlock]:
        """Process form element"""
        blocks = []

        # Create form container
        form_block = BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.FORM,
            content={"action": element.get("action", ""), "method": element.get("method", "get")},
            parent_id=parent_id,
            metadata=BlockMetadata(attributes={"tag": "form"}, confidence=1.0),
        )
        blocks.append(form_block)

        # Process form fields
        for field in element.find_all(["input", "select", "textarea"]):
            field_type = field.get("type", "text") if field.name == "input" else field.name

            field_block = FormFieldBlock(
                id=self._generate_block_id(),
                type=BlockType.FORMFIELD,
                content="",
                field_type=field_type,
                name=field.get("name", ""),
                value=field.get("value", ""),
                required=field.get("required") is not None,
                parent_id=form_block.id,
                metadata=BlockMetadata(
                    attributes={"tag": field.name, "placeholder": field.get("placeholder", "")},
                    confidence=1.0,
                ),
            )

            # For select, extract options
            if field.name == "select":
                options = [opt.get_text(strip=True) for opt in field.find_all("option")]
                field_block.options = options

            blocks.append(field_block)

        return blocks

    def _process_code(self, element: Tag, parent_id: Optional[str]) -> Optional[BaseBlock]:
        """Process code element"""
        code_text = element.get_text()
        if not code_text.strip():
            return None

        # Try to detect language from class
        language = None
        classes = element.get("class", [])

        # Check the element itself
        for cls in classes:
            if isinstance(cls, str) and cls.startswith("language-"):
                language = cls.replace("language-", "")
                break

        # If this is a pre tag, check for code child
        if not language and element.name == "pre":
            code_child = element.find("code")
            if code_child:
                child_classes = code_child.get("class", [])
                for cls in child_classes:
                    if isinstance(cls, str) and cls.startswith("language-"):
                        language = cls.replace("language-", "")
                        break

        return BaseBlock(
            id=self._generate_block_id(),
            type=BlockType.CODE,
            content=code_text,
            parent_id=parent_id,
            metadata=BlockMetadata(
                language=language,
                attributes={"tag": element.name, "class": classes},
                confidence=1.0,
            ),
        )

    def _process_blockquote(self, element: Tag, parent_id: Optional[str]) -> List[BaseBlock]:
        """Process blockquote element"""
        blocks = []

        # Create a container for the blockquote
        try:
            quote_text = md(str(element), strip=["blockquote"])
        except Exception as e:
            logger.warning(
                "Markdownify failed for blockquote: {error}, falling back to plain text", error=e
            )
            quote_text = element.get_text(strip=True)

        if quote_text.strip():
            blocks.append(
                BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.TEXT,
                    content=quote_text.strip(),
                    parent_id=parent_id,
                    metadata=BlockMetadata(
                        attributes={"tag": "blockquote", "style": {"is_quote": True}},
                        confidence=1.0,
                    ),
                )
            )

        return blocks

    def _build_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        """Build document hierarchy from heading blocks using h1..h6 levels."""
        heading_blocks = [b for b in blocks if b.type == BlockType.HEADING]
        if not heading_blocks:
            return None

        root = HierarchyNode(id="root", title="Document", level=0, block_id="root", children=[])
        stack: List[HierarchyNode] = [root]

        for block in heading_blocks:
            level = 1
            try:
                if block.metadata and block.metadata.attributes:
                    lvl = block.metadata.attributes.get("level")
                    if isinstance(lvl, int) and 1 <= lvl <= 6:
                        level = lvl
            except Exception:
                pass

            while len(stack) > level:
                stack.pop()

            parent = stack[-1] if stack else None
            breadcrumb = list(parent.breadcrumb) if parent else []
            breadcrumb.append(block.content)

            node = HierarchyNode(
                id=f"h-{block.id}",
                title=block.content,
                level=level,
                block_id=block.id,
                parent_id=parent.id if parent else None,
                breadcrumb=breadcrumb,
            )
            if parent:
                parent.children.append(node)

            if len(stack) <= level:
                stack.append(node)
            else:
                stack[level] = node

        return root

    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        """Extract all text content from blocks"""
        text_parts = []
        for block in blocks:
            if hasattr(block, "content") and isinstance(block.content, str):
                text_parts.append(block.content)
        return "\n".join(text_parts)

    def _extract_keywords(self, soup: BeautifulSoup) -> List[str]:
        """Extract keywords from HTML"""
        keywords = []

        # From meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            keywords.extend([k.strip() for k in meta_keywords["content"].split(",")])

        return keywords

    def _generate_block_id(self) -> str:
        """Generate unique block ID"""
        self.block_counter += 1
        return f"html-block-{self.block_counter}"

    def _blocks_from_trafilatura(self, json_str: str, filepath: Path) -> UnifiedDocument:
        """Convert Trafilatura JSON into Unified-Document structure."""
        import json

        data = json.loads(json_str)

        blocks: List[BaseBlock] = []
        self.current_headers = {}

        # Basic metadata
        metadata = DocumentMetadata(
            title=data.get("title", ""),
            author=data.get("author", ""),
            language=data.get("language", ""),
            format_metadata={"file_type": "html", "source": "trafilatura"},
        )

        # Split clean text into lines; map headings
        lines = data.get("text", "").splitlines()
        for line in lines:
            if line.startswith("#"):
                level = line.count("#", 0, 6)
                text = line[level:].strip()
                block = BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.HEADING,
                    content=text,
                    parent_id=None,
                    metadata=BlockMetadata(attributes={"level": level}, confidence=1.0),
                )
                blocks.append(block)
                self.current_headers[level] = text
            elif line.strip():
                blocks.append(
                    BaseBlock(
                        id=self._generate_block_id(),
                        type=BlockType.PARAGRAPH,
                        content=line,
                        parent_id=None,
                        metadata=BlockMetadata(attributes={}, confidence=1.0),
                    )
                )

        hierarchy = self._build_hierarchy(blocks)
        return UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.HTML,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text="\n".join(
                b.content for b in blocks if isinstance(b.content, str) and b.content.strip()
            ),
            keywords=data.get("keywords", []),
        )

    def _parse_dimension(self, value: Optional[str]) -> Optional[int]:
        """Parse dimension value (width/height)"""
        if not value:
            return None
        try:
            # Handle various CSS units
            if isinstance(value, str):
                # Match number with optional unit
                match = re.match(
                    r"(\d+(?:\.\d+)?)(px|%|em|rem|pt|pc|in|cm|mm|ex|ch|vw|vh|vmin|vmax)?",
                    value.strip(),
                    re.I,
                )
                if match:
                    number_str = match.group(1)
                    _unit = match.group(2)

                    # Convert to int, ignoring units for now
                    # In the future, could convert units to pixels
                    return int(float(number_str))
                else:
                    # Try direct conversion for cases like "auto", "inherit"
                    return int(value) if value.isdigit() else None
            else:
                return int(value)
        except (ValueError, TypeError):
            return None


if __name__ == "__main__":
    # Test the HTML extractor with a sample file
    import tempfile

    # Create test HTML
    test_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="author" content="Test Author">
        <title>Test HTML Document</title>
    </head>
    <body>
        <article>
            <h1>Main Title</h1>
            <p>This is a test paragraph with <strong>bold</strong> text.</p>
            
            <h2>Section 1</h2>
            <p>Content for section 1.</p>
            
            <table>
                <tr><th>Name</th><th>Value</th></tr>
                <tr><td>Item 1</td><td>100</td></tr>
            </table>
            
            <pre><code class="language-python">
def hello():
    print("Hello, World!")
            </code></pre>
            
            <form action="/submit" method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="email" name="email" placeholder="Email">
                <button type="submit">Submit</button>
            </form>
        </article>
    </body>
    </html>
    """

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(test_html)
        temp_path = f.name

    # Test extraction
    provider = HTMLProvider()
    doc = provider.extract_document(temp_path)

    # Validate
    assert doc.source_type == SourceType.HTML
    assert len(doc.blocks) > 0
    assert doc.metadata.title == "Test HTML Document"
    assert doc.metadata.author == "Test Author"

    # Check specific blocks
    heading_blocks = doc.get_blocks_by_type(BlockType.HEADING)
    assert len(heading_blocks) == 2
    assert heading_blocks[0].content == "Main Title"

    table_blocks = doc.get_blocks_by_type(BlockType.TABLE)
    assert len(table_blocks) == 1
    assert table_blocks[0].rows == 2

    code_blocks = doc.get_blocks_by_type(BlockType.CODE)
    assert len(code_blocks) == 1
    assert code_blocks[0].metadata.language == "python"

    form_blocks = doc.get_blocks_by_type(BlockType.FORM)
    assert len(form_blocks) == 1

    print(" Native HTML extraction passed")
    print(f"Extracted {len(doc.blocks)} blocks")

    # Cleanup
    import os

    os.unlink(temp_path)
