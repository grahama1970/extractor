"""
Module: markdown.py
Purpose: Native Markdown extraction without PDF conversion

Minimal provider that parses Markdown headings (#..######), paragraphs, and lists
into UnifiedDocument blocks. Avoids heavy deps by using simple parsing.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from loguru import logger

from extractor.core.schema.unified_document import (
    UnifiedDocument,
    BlockType,
    SourceType,
    BaseBlock,
    BlockMetadata,
    DocumentMetadata,
    HierarchyNode,
)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")
_LISTITEM_RE = re.compile(r"^(\s*)([-*+]\s+|\d+\.\s+)(.*)$")


class MarkdownProvider:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0

    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        filepath = Path(filepath)
        logger.info(f"Extracting Markdown document: {filepath}")
        text = filepath.read_text(encoding="utf-8", errors="ignore")

        blocks: List[BaseBlock] = []
        for line in text.splitlines():
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = _HEADING_RE.match(line)
            if m:
                level = len(m.group(1))
                content = m.group(2).strip()
                blocks.append(
                    BaseBlock(
                        id=self._next_id(),
                        type=BlockType.HEADING,
                        content=content,
                        metadata=BlockMetadata(attributes={"level": level}, confidence=1.0),
                    )
                )
                continue
            m = _LISTITEM_RE.match(line)
            if m:
                indent_spaces = len(m.group(1) or "")
                ordered = bool(re.match(r"\d+\.\s+", m.group(2)))
                content = m.group(3).strip()
                blocks.append(
                    BaseBlock(
                        id=self._next_id(),
                        type=BlockType.LISTITEM,
                        content=content,
                        metadata=BlockMetadata(attributes={"ordered": ordered, "indent": indent_spaces}, confidence=1.0),
                    )
                )
                continue
            # paragraph
            blocks.append(
                BaseBlock(
                    id=self._next_id(),
                    type=BlockType.PARAGRAPH,
                    content=line.strip(),
                    metadata=BlockMetadata(attributes={}, confidence=1.0),
                )
            )

        hierarchy = self._build_hierarchy(blocks)
        meta = DocumentMetadata(title=filepath.stem, format_metadata={"file_type": "markdown"})
        return UnifiedDocument(
            id=self._doc_id(filepath),
            source_type=SourceType.MD,
            source_path=str(filepath),
            blocks=blocks,
            hierarchy=hierarchy,
            metadata=meta,
            full_text="\n".join(b.content for b in blocks if isinstance(b.content, str)),
            keywords=[],
        )

    def _doc_id(self, path: Path) -> str:
        return hashlib.md5(str(path).encode()).hexdigest()

    def _next_id(self) -> str:
        self.block_counter += 1
        return f"md-block-{self.block_counter}"

    def _build_hierarchy(self, blocks: List[BaseBlock]) -> Optional[HierarchyNode]:
        heads = [b for b in blocks if b.type == BlockType.HEADING]
        if not heads:
            return None
        root = HierarchyNode(id="root", title="Document", level=0, block_id="root", children=[])
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
