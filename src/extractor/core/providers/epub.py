"""
Module: epub.py
Purpose: Native EPUB extraction without PDF conversion

External Dependencies:
- ebooklib: https://pypi.org/project/ebooklib/

Example usage
-------------
>>> from extractor.core.providers.epub import EPUBProvider
>>> doc = NativeEPUBProvider().extract_document("book.epub")
>>> print(doc.source_type)   # SourceType.EPUB
>>> print(len(doc.blocks))   # number of extracted blocks
"""

import hashlib
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from ebooklib import epub
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
from loguru import logger

from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BlockType,
    SourceType,
    BaseBlock,
    TableBlock,
    ImageBlock,
    BlockMetadata,
    DocumentMetadata,
    HierarchyNode,
    TableCell,
)


class EPUBProvider:
    """Direct EPUB extraction without PDF conversion."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        filepath = Path(filepath)
        logger.info(f"Extracting EPUB document: {filepath}")

        book = epub.read_epub(str(filepath))

        # Gather all textual spine items (in reading order)
        items = [book.get_item_with_id(i[0]) for i in book.spine]
        items = [i for i in items if i and i.media_type == "application/xhtml+xml"]

        # 1. Metadata
        metadata = self._extract_metadata(book, filepath)

        # 2. Blocks
        blocks: List[BaseBlock] = []
        for item in items:
            self._parse_xhtml(item, blocks)

        # 3. Images referenced in manifest (embedded)
        image_blocks = self._extract_images(book)
        blocks.extend(image_blocks)

        # 4. Build hierarchy: prefer TOC; fallback to headings in content
        hierarchy = self._build_toc_hierarchy(book.toc, blocks) if book.toc else None
        if not hierarchy:
            hierarchy = self._build_heading_hierarchy(blocks)

        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.EPUB,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(blocks),
            keywords=self._extract_keywords(book),
        )

        logger.info(f"Extracted {len(blocks)} blocks from EPUB")
        return doc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_doc_id(self, filepath: Path) -> str:
        return hashlib.md5(str(filepath).encode()).hexdigest()

    def _generate_block_id(self) -> str:
        self.block_counter += 1
        return f"epub-block-{self.block_counter}"

    def _extract_metadata(self, book: epub.EpubBook, filepath: Path) -> DocumentMetadata:
        meta = DocumentMetadata()

        meta.title = (
            book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else ""
        )
        meta.author = "; ".join([a[0] for a in book.get_metadata("DC", "creator")])
        meta.language = (
            book.get_metadata("DC", "language")[0][0] if book.get_metadata("DC", "language") else ""
        )

        # Store raw metadata dict for downstream use
        meta.format_metadata = {
            "file_type": "epub",
            "identifier": book.get_metadata("DC", "identifier"),
            "publisher": book.get_metadata("DC", "publisher"),
            "description": book.get_metadata("DC", "description"),
            "file_size": filepath.stat().st_size,
        }
        return meta

    # ------------------------------------------------------------------
    # XHTML parsing
    # ------------------------------------------------------------------
    def _parse_xhtml(self, item: epub.EpubItem, blocks: List[BaseBlock]) -> None:
        # Prefer XML parser for XHTML content to avoid XMLParsedAsHTMLWarning
        parser = "lxml-xml" if item.media_type == "application/xhtml+xml" else "lxml"
        try:
            soup = BeautifulSoup(item.get_content(), parser)
        except Exception:
            soup = BeautifulSoup(item.get_content(), "lxml")

        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # Walk the DOM
        self._walk_soup(soup.body or soup, blocks, parent_id=None)

    def _walk_soup(
        self,
        node: Union[Tag, NavigableString],
        blocks: List[BaseBlock],
        parent_id: Optional[str],
    ) -> None:
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                blocks.append(
                    BaseBlock(
                        id=self._generate_block_id(),
                        type=BlockType.PARAGRAPH,
                        content=text,
                        parent_id=parent_id,
                        metadata=BlockMetadata(
                            attributes={"context": "nav-string"}, confidence=0.9
                        ),
                    )
                )
            return

        tag = node.name.lower()

        # Headings
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            text = node.get_text(" ", strip=True)
            if text:
                block = BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.HEADING,
                    content=text,
                    parent_id=parent_id,
                    metadata=BlockMetadata(attributes={"level": level, "tag": tag}, confidence=1.0),
                )
                blocks.append(block)
                parent_id = block.id  # children nest under heading

        # Paragraphs
        elif tag == "p":
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append(
                    BaseBlock(
                        id=self._generate_block_id(),
                        type=BlockType.PARAGRAPH,
                        content=text,
                        parent_id=parent_id,
                        metadata=BlockMetadata(attributes={"tag": "p"}, confidence=1.0),
                    )
                )

        # Lists
        elif tag in {"ul", "ol", "dl"}:
            list_type = "ol" if tag == "ol" else ("dl" if tag == "dl" else "ul")
            list_block = BaseBlock(
                id=self._generate_block_id(),
                type=BlockType.LIST,
                content={"ordered": tag == "ol"},
                parent_id=parent_id,
                metadata=BlockMetadata(attributes={"tag": tag, "list_type": list_type}, confidence=1.0),
            )
            blocks.append(list_block)
            for idx, li in enumerate(node.find_all("li", recursive=False)):
                li_text = li.get_text(" ", strip=True)
                if li_text:
                    blocks.append(
                        BaseBlock(
                            id=self._generate_block_id(),
                            type=BlockType.LISTITEM,
                            content=li_text,
                            parent_id=list_block.id,
                            metadata=BlockMetadata(
                                {"index": idx, "ordered": tag == "ol", "list_type": list_type, "depth": 1}, confidence=1.0
                            ),
                        )
                    )

        # Tables
        elif tag == "table":
            table_block = self._parse_table(node, parent_id)
            if table_block:
                blocks.append(table_block)

        # Images
        elif tag == "img":
            src = node.get("src", "")
            if src:
                blocks.append(
                    ImageBlock(
                        id=self._generate_block_id(),
                        type=BlockType.IMAGE,
                        content="",
                        src=src,
                        alt=node.get("alt", ""),
                        metadata=BlockMetadata(attributes={"tag": "img"}, confidence=1.0),
                    )
                )

        # Code (pre or code)
        elif tag in {"pre", "code"}:
            lang = node.get("class", [""])[0] if isinstance(node.get("class"), list) else ""
            lang = lang.replace("language-", "") if lang.startswith("language-") else None
            text = node.get_text()
            blocks.append(
                BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.CODE,
                    content=text,
                    parent_id=parent_id,
                    metadata=BlockMetadata(language=lang, attributes={"tag": tag}, confidence=1.0),
                )
            )

        # Recurse into children
        for child in node.children:
            self._walk_soup(child, blocks, parent_id)

    def _parse_table(self, table: Tag, parent_id: Optional[str]) -> Optional[TableBlock]:
        rows = table.find_all("tr")
        if not rows:
            return None

        cells = []
        headers = []
        for r_idx, tr in enumerate(rows):
            cols = tr.find_all(["td", "th"])
            for c_idx, cell in enumerate(cols):
                rowspan = int(cell.get("rowspan", 1))
                colspan = int(cell.get("colspan", 1))
                text = cell.get_text(" ", strip=True)
                cells.append(
                    TableCell(
                        row=r_idx,
                        col=c_idx,
                        content=text,
                        rowspan=rowspan,
                        colspan=colspan,
                        style={"is_header": cell.name == "th"},
                    )
                )
            if r_idx == 0 and all(c.name == "th" for c in cols):
                headers.append(r_idx)

        if not cells:
            return None

        max_row = max(c.row for c in cells)
        max_col = max(c.col for c in cells)

        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=max_row + 1,
            cols=max_col + 1,
            cells=cells,
            headers=headers,
            metadata=BlockMetadata(attributes={"tag": "table"}, confidence=1.0),
            parent_id=parent_id,
        )

    # ------------------------------------------------------------------
    # Images & misc
    # ------------------------------------------------------------------
    def _extract_images(self, book: epub.EpubBook) -> List[ImageBlock]:
        blocks = []
        for item in book.get_items():
            if item.media_type and item.media_type.startswith("image/"):
                data = item.get_content()
                b64 = base64.b64encode(data).decode("utf-8")
                data_uri = f"data:{item.media_type};base64,{b64}"
                blocks.append(
                    ImageBlock(
                        id=self._generate_block_id(),
                        type=BlockType.IMAGE,
                        content="",
                        src=data_uri,
                        alt=item.file_name,
                        format=item.media_type.split("/")[-1],
                        metadata=BlockMetadata(
                            attributes={"original_filename": item.file_name, "embedded": True},
                            confidence=1.0,
                        ),
                    )
                )
        return blocks

    def _build_toc_hierarchy(self, toc, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        """
        Build hierarchy from EPUB TOC (NCX or nav.xhtml).
        Links each TOC entry with the closest heading block.
        """
        if not toc:
            return None

        root = HierarchyNode(id="root", title="Book", level=0, block_id="root", children=[])

        def _iter_entries(obj):
            # ebooklib toc can be a list, a Link, or nested tuples
            try:
                for item in obj:
                    yield item
            except TypeError:
                yield obj

        def recurse(entries, parent_node, level):
            for entry in _iter_entries(entries):
                title = entry.title if entry.title else "Untitled"
                href = entry.href
                # simple heuristic: use the first heading on that page with null checks
                block_id = next(
                    (
                        b.id
                        for b in blocks
                        if b.metadata
                        and b.metadata.attributes
                        and href in str(b.metadata.attributes.get("src", ""))
                    ),
                    None,
                )
                if block_id is None:
                    anchor = href or title
                    block_id = f"toc-{hashlib.md5(anchor.encode()).hexdigest()}"
                node = HierarchyNode(
                    id=f"toc-{hashlib.md5(title.encode()).hexdigest()}",
                    title=title,
                    level=level,
                    block_id=block_id,
                    parent_id=parent_node.id,
                    breadcrumb=[*parent_node.breadcrumb, title],
                )
                parent_node.children.append(node)
                child_entries = getattr(entry, "children", None)
                if child_entries:
                    recurse(child_entries, node, level + 1)

        recurse(toc, root, 1)
        return root if root.children else None

    def _build_heading_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        heads = [b for b in blocks if b.type == BlockType.HEADING]
        if not heads:
            return None
        root = HierarchyNode(id="root", title="Book", level=0, block_id="root", children=[])
        stack: List[HierarchyNode] = [root]
        for b in heads:
            lvl = 1
            if b.metadata and b.metadata.attributes:
                lvl = int(b.metadata.attributes.get("level", 1))
            while len(stack) > lvl:
                stack.pop()
            parent = stack[-1]
            node = HierarchyNode(
                id=f"h-{b.id}",
                title=b.content,
                level=lvl,
                block_id=b.id,
                parent_id=parent.id,
                breadcrumb=[*parent.breadcrumb, b.content],
            )
            parent.children.append(node)
            if len(stack) <= lvl:
                stack.append(node)
            else:
                stack[lvl] = node
        return root

    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        return "\n".join(
            b.content for b in blocks if hasattr(b, "content") and isinstance(b.content, str)
        )

    def _extract_keywords(self, book: epub.EpubBook) -> List[str]:
        kw = book.get_metadata("DC", "subject") or []
        return [k[0] for k in kw if k]


# ----------------------------------------------------------------------
# Quick self-test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    import os

    # Create minimal EPUB in memory
    book = epub.EpubBook()
    book.set_title("Test EPUB")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="chap_01.xhtml", lang="en")
    c1.content = """<html><body>
        <h1>Chapter 1</h1>
        <p>Hello EPUB world!</p>
        <table border="1"><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
    </body></html>"""

    book.add_item(c1)
    book.toc = [epub.Link("chap_01.xhtml", "Chapter 1", "ch1")]
    book.spine = ["nav", c1]

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
        epub.write_epub(f.name, book)
        tmp = f.name

    doc = EPUBProvider().extract_document(tmp)
    assert doc.source_type == SourceType.EPUB
    assert len(doc.blocks) >= 3  # heading, paragraph, table
    os.unlink(tmp)
    print("✅ EPUB native provider self-test passed")
