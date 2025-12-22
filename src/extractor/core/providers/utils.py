"""Provider utilities: heading normalization and list block helpers.

This module intentionally has no heavy dependencies so it can be imported by
all providers. Utility functions here help enforce cross‑format parity.
"""

from typing import Any, Dict, List, Tuple

from extractor.core.schema.unified_document import (
    BaseBlock,
    BlockMetadata,
    BlockType,
    UnifiedDocument,
    HierarchyNode,
)


def alphanum_ratio(text: str) -> float:
    text = text.replace(" ", "")
    text = text.replace("\n", "")
    alphanumeric_count = sum([1 for c in text if c.isalnum()])

    if len(text) == 0:
        return 1

    ratio = alphanumeric_count / len(text)
    return ratio


def normalize_heading_level(level: Any, *, default: int = 1) -> int:
    """Normalize heading level to 1‑based int within [1,6]."""
    try:
        n = int(level)
    except Exception:
        n = default
    return max(1, min(6, n))


def emit_list_blocks(
    *,
    items: List[Tuple[str, int]],  # list of (text, depth)
    list_type: str = "ul",  # "ul" | "ol" | "dl"
    parent_id: str,
    id_prefix: str = "list",
    start_index: int = 0,
) -> Tuple[BaseBlock, List[BaseBlock]]:
    """Emit a LIST parent and LISTITEM children given (text, depth) pairs.

    Returns (list_block, item_blocks).
    """
    list_block = BaseBlock(
        id=f"{id_prefix}-{start_index:06d}",
        parent_id=parent_id,
        type=BlockType.LIST,
        content="",
        metadata=BlockMetadata(attributes={"list_type": list_type}),
    )
    out: List[BaseBlock] = []
    for i, (text, depth) in enumerate(items, start=start_index + 1):
        out.append(
            BaseBlock(
                id=f"{id_prefix}-item-{i:06d}",
                parent_id=list_block.id,
                type=BlockType.LISTITEM,
                content=text,
                metadata=BlockMetadata(attributes={"depth": int(depth), "list_type": list_type}),
            )
        )
    # For callers that want a quick child list without re‑scanning blocks
    try:
        list_block.children_ids = [b.id for b in out]  # type: ignore[attr-defined]
    except Exception:
        pass
    return list_block, out


def ensure_hierarchy(doc: UnifiedDocument, *, default_title: str = "Document") -> UnifiedDocument:
    """Guarantee the UnifiedDocument has a root hierarchy and parent links.

    - If `doc.hierarchy` already exists, it is returned unchanged.
    - Otherwise, a root node is synthesized and any blocks missing a parent_id
      are reparented to the root.
    """

    root = getattr(doc, "hierarchy", None)
    if root is None:
        root = HierarchyNode(
            id="root",
            title=default_title or "Document",
            level=1,
            block_id="root",
            breadcrumb=[default_title or "Document"],
            children=[],
        )
    else:
        if not getattr(root, "block_id", None):
            root.block_id = root.id
        if getattr(root, "breadcrumb", None) is None:
            root.breadcrumb = [root.title or default_title or "Document"]

    for blk in doc.blocks:
        try:
            if not getattr(blk, "parent_id", None):
                blk.parent_id = root.id
        except Exception:
            # Best-effort; do not break if a block lacks parent_id attr
            pass

    doc.hierarchy = root
    return doc
