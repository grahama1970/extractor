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
from extractor.core.providers.utils import emit_list_blocks, normalize_heading_level
from extractor.core.providers.fetcher_bridge import ensure_local_source, attach_fetcher_metadata

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
        resolved_path, fetch_download = ensure_local_source(filepath)
        filepath = Path(resolved_path)
        logger.info(f"Extracting Markdown document: {filepath}")
        text = filepath.read_text(encoding="utf-8", errors="ignore")

        blocks: List[BaseBlock] = []
        # Track the current list (pending items) to emit LIST + LISTITEM together
        pending_items: List[tuple[str, int]] = []
        current_list_type: Optional[str] = None  # "ul" or "ol"
        last_heading_id: Optional[str] = None

        def flush_list():
            nonlocal pending_items, current_list_type
            if pending_items:
                parent_id = last_heading_id
                list_block, items = emit_list_blocks(
                    items=pending_items,
                    list_type=current_list_type or "ul",
                    parent_id=parent_id or "",
                    id_prefix="md-list",
                    start_index=self.block_counter,
                )
                blocks.append(list_block)
                blocks.extend(items)
                pending_items = []
                current_list_type = None

        for raw in text.splitlines():
            line = raw.rstrip("\n")
            if not line.strip():
                flush_list()
                continue
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = _HEADING_RE.match(line)
            if m:
                flush_list()
                level = normalize_heading_level(len(m.group(1)))
                content = m.group(2).strip()
                hb = BaseBlock(
                    id=self._next_id(),
                    type=BlockType.HEADING,
                    content=content,
                    metadata=BlockMetadata(attributes={"level": level}, confidence=1.0),
                )
                blocks.append(hb)
                last_heading_id = hb.id
                continue
            m = _LISTITEM_RE.match(line)
            if m:
                indent_spaces = len(m.group(1) or "")
                ordered = bool(re.match(r"\d+\.\s+", m.group(2)))
                content = m.group(3).strip()
                list_type = "ol" if ordered else "ul"
                # Simple depth heuristic: 2 spaces per level -> 1-based depth
                depth = max(1, indent_spaces // 2 + 1)
                if current_list_type and list_type != current_list_type:
                    flush_list()
                current_list_type = list_type
                pending_items.append((content, depth))
                continue
            # paragraph
            flush_list()
            blocks.append(
                BaseBlock(
                    id=self._next_id(),
                    type=BlockType.PARAGRAPH,
                    content=line.strip(),
                    metadata=BlockMetadata(attributes={}, confidence=1.0),
                )
            )
        # flush any pending list at EOF
        flush_list()

        hierarchy = self._build_hierarchy(blocks)
        meta = DocumentMetadata(title=filepath.stem, format_metadata={"file_type": "markdown"})
        attach_fetcher_metadata(meta, fetch_download)
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
                lvl = normalize_heading_level(b.metadata.attributes.get("level", 1))
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
