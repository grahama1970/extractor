"""Utilities for normalizing pipeline output into :class:`UnifiedDocument`.

These helpers take the Stage 07 ``reflowed_sections`` structure (which is
still the dominant output of the PDF pipeline today) and translate it into the
canonical :mod:`extractor.core.schema.unified_document` data model.  The goal is
to give every upstream format—PDF, HTML, DOCX, PPTX, etc.—the same downstream
shape so later stages (summaries, graph loading, Arango export) do not need to
special-case by file type.

The functions in this module intentionally favour deterministic, schema-safe
defaults.  We only rely on fields that have existed across Stage 07 outputs for
months (section ``id``/``level``/``title``, ``reflowed_text``, ``tables``,
``figures``) and gracefully degrade when optional data is missing.  As other
providers already emit ``UnifiedDocument`` instances directly, this adapter gives
the PDF pipeline parity without forcing a disruptive rewrite of the early
stages.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from extractor.core.schema.unified_document import (
    BaseBlock,
    BlockMetadata,
    BlockType,
    DocumentMetadata,
    HierarchyNode,
    SourceType,
    TableBlock,
    TableCell,
    UnifiedDocument,
)


_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")


def _next_block_id(counter: List[int], prefix: str) -> str:
    """Generate deterministic incrementing block identifiers."""

    counter[0] += 1
    return f"{prefix}-{counter[0]:06d}"


def _normalise_source_type(source_type: Optional[str | SourceType]) -> SourceType:
    if isinstance(source_type, SourceType):
        return source_type
    if isinstance(source_type, str):
        try:
            return SourceType(source_type.lower())
        except ValueError:
            pass
    return SourceType.PDF


def _default_document_title(source_path: Optional[str], sections: Sequence[Dict[str, Any]]) -> str:
    if sections:
        first_title = sections[0].get("document_title") or sections[0].get("title")
        if isinstance(first_title, str) and first_title.strip():
            return first_title.strip()
    if source_path:
        try:
            return Path(source_path).stem
        except Exception:
            pass
    return "Document"


def _hash_source(source_path: Optional[str], fallback: str = "document") -> str:
    basis = source_path or fallback
    return hashlib.md5(basis.encode("utf-8")).hexdigest()


def _paragraphs_from_text(text: str) -> List[str]:
    if not text:
        return []
    candidates = _PARA_SPLIT_RE.split(text)
    return [segment.strip() for segment in candidates if segment.strip()]


def _table_from_section(
    *,
    table: Dict[str, Any],
    parent_id: str,
    block_id_counter: List[int],
    section_id: str,
) -> TableBlock:
    rows: int = 0
    cols: int = 0
    headers: List[int] = []
    metrics = table.get("pandas_metrics") or {}
    if isinstance(metrics, dict):
        shape = metrics.get("shape") or []
        if isinstance(shape, (list, tuple)) and len(shape) == 2:
            rows = int(shape[0] or 0)
            cols = int(shape[1] or 0)
        header_cols = metrics.get("columns")
        if isinstance(header_cols, list):
            cols = max(cols, len(header_cols))
        headers = [0] if rows else []

    pandas_rows = table.get("pandas_df")
    if isinstance(pandas_rows, list) and pandas_rows:
        rows = max(rows, len(pandas_rows))
        cols = max(
            cols,
            max((len(row) for row in pandas_rows if isinstance(row, dict)), default=0),
        )

    if rows == 0:
        rows = len(pandas_rows) if isinstance(pandas_rows, list) else 0
    if cols == 0:
        first = pandas_rows[0] if isinstance(pandas_rows, list) and pandas_rows else {}
        if isinstance(first, dict):
            cols = len(first)

    cells: List[TableCell] = []
    if isinstance(pandas_rows, list):
        for r_idx, row in enumerate(pandas_rows):
            if not isinstance(row, dict):
                continue
            for c_idx, (key, value) in enumerate(row.items()):
                cells.append(
                    TableCell(
                        row=r_idx,
                        col=c_idx,
                        content=str(value) if value is not None else "",
                    )
                )

    simple_cells = table.get("cells")
    if isinstance(simple_cells, list) and simple_cells:
        rows = max(rows, len(simple_cells))
        cols = max(cols, max((len(r) for r in simple_cells if isinstance(r, list)), default=0))
        for r_idx, row in enumerate(simple_cells):
            if not isinstance(row, list):
                continue
            for c_idx, value in enumerate(row):
                cells.append(
                    TableCell(
                        row=r_idx,
                        col=c_idx,
                        content=str(value) if value is not None else "",
                    )
                )

    block_id = _next_block_id(block_id_counter, "table")
    metadata = BlockMetadata(
        confidence=1.0,
        page_number=table.get("page_number"),
        bbox=table.get("bbox"),
        attributes={
            "section_id": section_id,
            "source": table.get("source", "stage07_table"),
            "table_index": table.get("table_index"),
            "extraction_method": table.get("extraction_method"),
            "strategy": table.get("strategy"),
            "sheet": table.get("sheet"),
        },
    )

    table_content = {
        "title": table.get("title"),
        "pandas_metrics": metrics,
        "image_path": table.get("table_image_path"),
    }

    return TableBlock(
        id=block_id,
        parent_id=parent_id,
        type=BlockType.TABLE,
        content=table_content,
        rows=max(rows, 0),
        cols=max(cols, 0),
        cells=cells,
        headers=headers or None,
        metadata=metadata,
    )


def _figure_block_from_section(
    *,
    figure: Dict[str, Any],
    parent_id: str,
    block_id_counter: List[int],
    section_id: str,
) -> BaseBlock:
    block_id = _next_block_id(block_id_counter, "figure")
    metadata = BlockMetadata(
        confidence=1.0,
        page_number=figure.get("page"),
        bbox=figure.get("bbox"),
        attributes={
            "section_id": section_id,
            "source": "stage07_figure",
            "figure_id": figure.get("figure_id"),
        },
    )

    content = {
        "title": figure.get("title"),
        "caption": figure.get("ai_description") or figure.get("caption"),
        "image_path": figure.get("image_path"),
        "metadata": figure.get("metadata") or {},
    }

    return BaseBlock(
        id=block_id,
        parent_id=parent_id,
        type=BlockType.FIGURE,
        content=content,
        metadata=metadata,
    )


def build_unified_document_from_reflow(
    *,
    sections: Sequence[Dict[str, Any]],
    source_path: Optional[str],
    source_type: Optional[str | SourceType] = None,
    document_metadata: Optional[Dict[str, Any]] = None,
    document_title: Optional[str] = None,
) -> UnifiedDocument:
    """Convert Stage 07 ``reflowed_sections`` into a :class:`UnifiedDocument`.

    Args:
        sections: The processed section payload emitted by Stage 07.
        source_path: Path-like identifier for the originating resource.  Used for
            ``source_path`` as well as generating a deterministic document id.
        source_type: Optional override for :class:`SourceType`.  Defaults to PDF
            (legacy behaviour) when omitted or invalid.
        document_metadata: Optional dictionary merged into metadata
            ``format_metadata``.
        document_title: Optional explicit document title.  When omitted we fall
            back to ``sections[0].title`` or the ``source_path`` stem.

    Returns:
        A populated :class:`UnifiedDocument` instance.
    """

    source_type_enum = _normalise_source_type(source_type)
    title = document_title or _default_document_title(source_path, sections)
    document_id = _hash_source(source_path, fallback=title)

    metadata = DocumentMetadata(
        title=title,
        format_metadata={
            "file_type": source_type_enum.value,
            "source_path": source_path,
        },
    )
    if document_metadata:
        metadata.format_metadata.update(document_metadata)

    block_counter = [0]
    blocks: List[BaseBlock] = []
    children_lookup: Dict[str, List[str]] = defaultdict(list)

    root_block_id = _next_block_id(block_counter, "root")
    root_block = BaseBlock(
        id=root_block_id,
        type=BlockType.HEADING,
        content=title,
        metadata=BlockMetadata(
            confidence=1.0,
            attributes={"level": 0, "role": "document_root"},
        ),
    )
    blocks.append(root_block)

    root_node = HierarchyNode(
        id="document-root",
        title=title,
        level=0,
        block_id=root_block_id,
        children=[],
        parent_id=None,
        breadcrumb=[],
    )

    stack: List[Tuple[int, HierarchyNode, str]] = [(0, root_node, root_block_id)]
    full_text_parts: List[str] = []

    for section in sections:
        if not isinstance(section, dict):
            continue

        section_id = str(section.get("id") or _next_block_id(block_counter, "section"))
        level = int(section.get("level") or 1)
        title_text = (section.get("title") or f"Section {section_id}").strip()

        while len(stack) > 1 and level <= stack[-1][0]:
            stack.pop()

        parent_level, parent_node, parent_block_id = stack[-1]

        heading_block_id = _next_block_id(block_counter, "heading")
        heading_block = BaseBlock(
            id=heading_block_id,
            parent_id=parent_block_id,
            type=BlockType.HEADING,
            content=title_text,
            metadata=BlockMetadata(
                confidence=1.0,
                page_number=section.get("page_start"),
                bbox=section.get("bbox"),
                attributes={
                    "section_id": section_id,
                    "section_level": level,
                    "section_number": section.get("section_number"),
                    "source": "stage07_heading",
                },
            ),
        )
        blocks.append(heading_block)
        children_lookup[parent_block_id].append(heading_block_id)

        node = HierarchyNode(
            id=section_id,
            title=title_text,
            level=level,
            block_id=heading_block_id,
            children=[],
            parent_id=parent_node.id,
            breadcrumb=parent_node.breadcrumb + [title_text],
        )
        parent_node.children.append(node)
        stack.append((level, node, heading_block_id))

        # Text content
        fallback_text_sources: List[str] = []
        for key in ("reflowed_text", "merged_text", "source_text"):
            value = section.get(key)
            if isinstance(value, str) and value.strip():
                fallback_text_sources.append(value)

        block_texts: List[str] = []
        for block in section.get("blocks", []) or []:
            if not isinstance(block, dict):
                continue
            text_val = block.get("text")
            if isinstance(text_val, str) and text_val.strip():
                block_texts.append(text_val)

        if not fallback_text_sources and block_texts:
            fallback_text_sources.extend(block_texts)

        emitted_paragraphs: List[str] = []
        seen_paragraphs: set[str] = set()

        for raw_text in fallback_text_sources:
            for paragraph in _paragraphs_from_text(raw_text):
                if paragraph and paragraph not in seen_paragraphs:
                    emitted_paragraphs.append(paragraph)
                    seen_paragraphs.add(paragraph)

        if not emitted_paragraphs and block_texts:
            for text_val in block_texts:
                paragraph = text_val.strip()
                if paragraph and paragraph not in seen_paragraphs:
                    emitted_paragraphs.append(paragraph)
                    seen_paragraphs.add(paragraph)

        for paragraph in emitted_paragraphs:
            para_block_id = _next_block_id(block_counter, "para")
            block = BaseBlock(
                id=para_block_id,
                parent_id=heading_block_id,
                type=BlockType.PARAGRAPH,
                content=paragraph,
                metadata=BlockMetadata(
                    confidence=1.0,
                    page_number=section.get("page_start"),
                    bbox=None,
                    attributes={
                        "section_id": section_id,
                        "source": "stage07_reflowed_text",
                    },
                ),
            )
            blocks.append(block)
            children_lookup[heading_block_id].append(para_block_id)
            full_text_parts.append(paragraph)

        # Tables
        tables = section.get("tables") or []
        if isinstance(tables, list):
            for table in tables:
                if not isinstance(table, dict):
                    continue
                table_block = _table_from_section(
                    table=table,
                    parent_id=heading_block_id,
                    block_id_counter=block_counter,
                    section_id=section_id,
                )
                blocks.append(table_block)
                children_lookup[heading_block_id].append(table_block.id)

        # Figures
        figures = section.get("figures") or []
        if isinstance(figures, list):
            for figure in figures:
                if not isinstance(figure, dict):
                    continue
                figure_block = _figure_block_from_section(
                    figure=figure,
                    parent_id=heading_block_id,
                    block_id_counter=block_counter,
                    section_id=section_id,
                )
                blocks.append(figure_block)
                children_lookup[heading_block_id].append(figure_block.id)

    # Set children lists
    for block in blocks:
        block.children_ids = children_lookup.get(block.id, [])

    full_text = "\n\n".join(full_text_parts) if full_text_parts else None

    return UnifiedDocument(
        id=document_id,
        source_type=source_type_enum,
        source_path=str(source_path) if source_path else None,
        blocks=blocks,
        hierarchy=root_node,
        metadata=metadata,
        full_text=full_text,
        keywords=[],
    )


__all__ = ["build_unified_document_from_reflow"]
