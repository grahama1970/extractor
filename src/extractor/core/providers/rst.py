"""
Module: rst.py
Purpose: Native reStructuredText extraction without PDF conversion

External Dependencies:
- docutils: https://docutils.sourceforge.io/

Example Usage
-------------
>>> from extractor.core.providers.rst import RSTProvider
>>> provider = RSTProvider()
>>> doc = provider.extract_document("readme.rst")
>>> print(doc.source_type)  # SourceType.RST
"""

import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from docutils import nodes
from docutils.core import publish_doctree
from docutils.parsers.rst import directives, roles
from docutils import io as docutils_io
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
from extractor.core.providers.utils import emit_list_blocks, normalize_heading_level, ensure_hierarchy
from extractor.core.providers.fetcher_bridge import ensure_local_source, attach_fetcher_metadata


class RSTProvider:
    """Direct RST extraction without PDF conversion"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0
        self._last_heading_id: Optional[str] = None
        # Ensure docutils directives/roles are loaded when available
        try:
            directives.setup()
        except AttributeError:
            pass
        try:
            roles.setup()
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        resolved_path, fetch_download = ensure_local_source(filepath)
        filepath = Path(resolved_path)
        logger.info(f"Extracting RST document: {filepath}")

        # 1. Parse RST -> docutils doctree with SystemMessage handling
        with open(filepath, encoding="utf-8") as f:
            try:
                doctree = publish_doctree(
                    f.read(),
                    source_class=docutils_io.StringInput,
                    settings_overrides={
                        "halt_level": 5,  # ignore warnings
                        "report_level": 4,
                    },
                )
            except Exception as e:
                logger.warning(f"RST parsing failed: {e}, creating minimal document")
                # Create a minimal document with the raw content as a paragraph
                from docutils.utils import new_document
                from docutils.frontend import OptionParser
                from docutils.parsers.rst import Parser

                settings = OptionParser(components=(Parser,)).get_default_values()
                doctree = new_document("<rst-doc>", settings=settings)
                # Add the content as a simple paragraph
                para = nodes.paragraph()
                para += nodes.Text(f.read())
                doctree += para

        # 2. Convert doctree to blocks
        blocks: List[BaseBlock] = []
        self._last_heading_id = None
        self._walk_doctree(doctree, blocks)

        # 3. Build hierarchy from headings
        hierarchy = self._build_hierarchy(blocks)

        # 4. Compose UnifiedDocument
        metadata = self._extract_metadata(filepath)
        attach_fetcher_metadata(metadata, fetch_download)

        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.RST,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(blocks),
            keywords=self._extract_keywords(doctree),
        )

        logger.info(f"Extracted {len(blocks)} blocks from RST")
        return ensure_hierarchy(doc, default_title=filepath.stem)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_doc_id(self, filepath: Path) -> str:
        return hashlib.md5(str(filepath).encode()).hexdigest()

    def _extract_metadata(self, filepath: Path) -> DocumentMetadata:
        meta = DocumentMetadata()
        meta.format_metadata = {
            "file_type": "rst",
            "encoding": "utf-8",
            "file_size": filepath.stat().st_size,
        }
        return meta

    def _extract_keywords(self, doctree) -> List[str]:
        keywords = []
        for field in doctree.findall(nodes.field):
            name, body = field.children
            if name.astext().lower() == "keywords":
                keywords.extend(k.strip() for k in body.astext().split(","))
        return keywords

    def _generate_block_id(self) -> str:
        self.block_counter += 1
        return f"rst-block-{self.block_counter}"

    # ------------------------------------------------------------------
    # Docutils visitor
    # ------------------------------------------------------------------
    def _walk_doctree(self, node: nodes.Node, blocks: List[BaseBlock]) -> None:
        """Recursively convert docutils nodes to blocks."""
        if isinstance(node, nodes.section):
            # Heading nodes already handled by title; descend only
            for child in node.children:
                self._walk_doctree(child, blocks)
            return

        if isinstance(node, nodes.title):
            level = getattr(node.parent, "level", 1)
            hb = BaseBlock(
                id=self._generate_block_id(),
                type=BlockType.HEADING,
                content=node.astext().strip(),
                metadata=BlockMetadata(
                    attributes={"level": normalize_heading_level(level)},
                    confidence=1.0,
                ),
            )
            blocks.append(hb)
            self._last_heading_id = hb.id
            return

        if isinstance(node, nodes.paragraph):
            blocks.append(
                BaseBlock(
                    id=self._generate_block_id(),
                    type=BlockType.PARAGRAPH,
                    content=node.astext().strip(),
                    metadata=BlockMetadata(attributes={}, confidence=1.0),
                )
            )
            return

        if isinstance(node, (nodes.bullet_list, nodes.enumerated_list)):
            list_type = "ol" if isinstance(node, nodes.enumerated_list) else "ul"
            items: List[tuple[str, int]] = []
            for li in node.findall(nodes.list_item, include_self=False, descend=False):
                text = li.astext().strip()
                items.append((text, 1))
            if items:
                lst, children = emit_list_blocks(
                    items=items, list_type=list_type, parent_id=self._last_heading_id or "", id_prefix="rst-list", start_index=self.block_counter
                )
                blocks.append(lst)
                blocks.extend(children)
            # Continue into children for nested structures
            for child in node.children:
                self._walk_doctree(child, blocks)
            return

        if isinstance(node, nodes.literal_block):
            blocks.append(
                BaseBlock(
                    type=BlockType.CODE,
                    id=self._generate_block_id(),
                    content=node.astext(),
                    metadata=BlockMetadata(
                        attributes={"language": node.get("language") or None}, confidence=1.0
                    ),
                )
            )
            return

        if isinstance(node, nodes.image):
            blocks.append(
                ImageBlock(
                    id=self._generate_block_id(),
                    type=BlockType.IMAGE,
                    content="",
                    src=node["uri"],
                    alt=node.get("alt", ""),
                    metadata=BlockMetadata(attributes={}, confidence=1.0),
                )
            )
            return

        if isinstance(node, nodes.table):
            blocks.append(self._convert_table(node))
            return

        # Continue walking
        for child in node.children:
            self._walk_doctree(child, blocks)

    def _convert_table(self, table_node: nodes.table) -> TableBlock:
        rows = 0
        cols = 0
        cells = []

        for row_idx, row in enumerate(table_node.findall(nodes.row)):
            rows += 1
            for col_idx, entry in enumerate(row.findall(nodes.entry)):
                cells.append(
                    TableCell(
                        row=row_idx,
                        col=col_idx,
                        content=entry.astext().strip(),
                        colspan=int(entry.get("morecols", 0)) + 1,
                        rowspan=int(entry.get("morerows", 0)) + 1,
                    )
                )
                cols = max(cols, col_idx + 1)

        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={},
            rows=rows,
            cols=cols,
            cells=cells,
            headers=[0] if rows > 0 else [],
            metadata=BlockMetadata(attributes={}, confidence=1.0),
        )

    def _build_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        headings = [b for b in blocks if b.type == BlockType.HEADING]
        if not headings:
            return None

        root = HierarchyNode(
            id="root",
            title="Document",
            level=0,
            block_id="root",
            children=[],
        )
        stack = [root]

        for block in headings:
            # Add null check for metadata.attributes
            if block.metadata and block.metadata.attributes:
                level = block.metadata.attributes.get("level", 1)
            else:
                level = 1
            # Pop until parent level
            while len(stack) > level:
                stack.pop()

            node = HierarchyNode(
                id=f"h-{block.id}",
                title=block.content,
                level=level,
                block_id=block.id,
                parent_id=stack[-1].id if stack else None,
                breadcrumb=[n.title for n in stack] + [block.content],
            )
            if stack:
                stack[-1].children.append(node)
            if len(stack) <= level:
                stack.append(node)
            else:
                stack[level] = node

        return root

    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        return "\n".join(
            b.content if isinstance(b.content, str) else "" for b in blocks if hasattr(b, "content")
        )


# ----------------------------------------------------------------------
# Quick sanity check
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile

    sample_rst = """
Main Title
==========

Section 1
---------

This is a paragraph.

.. code-block:: python

    print("Hello RST")

.. table::

   =====  =====
   Name   Age
   =====  =====
   Alice  30
   Bob    25
   =====  =====

.. image:: https://example.com/logo.png
   :alt: Example Logo
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".rst", delete=False) as f:
        f.write(sample_rst)
        tmp = f.name

    doc = RSTProvider().extract_document(tmp)
    assert doc.source_type == SourceType.RST
    assert len([b for b in doc.blocks if b.type == BlockType.HEADING]) == 2
    assert len([b for b in doc.blocks if b.type == BlockType.TABLE]) == 1

    import os

    os.unlink(tmp)
    print("✅ RST provider self-test passed")
