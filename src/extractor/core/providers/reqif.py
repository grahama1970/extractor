"""
Module: reqif.py
Purpose: Native ReqIF extraction for .reqif and .reqifz files

This module implements ReqIF extraction using the strictdoc-project ``reqif``
library.  It maps SPEC-OBJECTS to text blocks with requirement IDs,
preserves SPEC-HIERARCHY as document structure, and captures
SPEC-RELATIONS as traceability metadata.

External Dependencies:
- reqif (optional): https://pypi.org/project/reqif/

Example Usage:
>>> from extractor.core.providers.reqif import ReqIFProvider
>>> provider = ReqIFProvider()
>>> document = provider.extract_document("requirements.reqif")
>>> print(document.source_type)  # SourceType.XML
"""

import hashlib
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

# Graceful import of the reqif library
try:
    from reqif.parser import ReqIFParser
    from reqif.reqif_bundle import ReqIFBundle, ReqIFZBundle

    REQIF_AVAILABLE = True
except ImportError:
    REQIF_AVAILABLE = False
    logger.debug("reqif library not installed; ReqIFProvider will fall back to XMLProvider")

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
from extractor.core.providers.fetcher_bridge import ensure_local_source, attach_fetcher_metadata
from extractor.core.providers.utils import ensure_hierarchy


def _strip_xhtml(text: Optional[str]) -> str:
    """Strip XHTML tags from rich-text attribute values, returning plain text."""
    if not text:
        return ""
    # Remove XML/XHTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


class ReqIFProvider:
    """Native ReqIF extraction for .reqif and .reqifz files.

    Extracts SPEC-OBJECTS as text/paragraph blocks, preserves SPEC-HIERARCHY
    for section structure, and records SPEC-RELATIONS as format metadata for
    traceability.

    If the ``reqif`` library is not installed, the provider falls back to
    :class:`XMLProvider` so that basic XML content is still extracted.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.block_counter = 0
        # Map from spec-object identifier -> block id (for hierarchy linking)
        self._spec_obj_block_map: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract ReqIF content to unified document format.

        Falls back to :class:`XMLProvider` if the ``reqif`` library is
        not installed.
        """
        if not REQIF_AVAILABLE:
            logger.warning(
                "reqif library not installed; falling back to XMLProvider for %s",
                filepath,
            )
            from extractor.core.providers.xml import XMLProvider

            return XMLProvider(self.config).extract_document(filepath)

        resolved_path, fetch_download = ensure_local_source(filepath)
        filepath = Path(resolved_path)
        logger.info("Extracting ReqIF document: {}", filepath)

        # Reset per-document state
        self.block_counter = 0
        self._spec_obj_block_map = {}

        # Parse .reqif or .reqifz
        try:
            bundles = self._parse_file(filepath)
        except Exception as exc:
            logger.warning(
                "reqif library failed to parse {}; falling back to XMLProvider: {}",
                filepath,
                exc,
            )
            from extractor.core.providers.xml import XMLProvider

            return XMLProvider(self.config).extract_document(filepath)

        if not bundles:
            logger.warning("No ReqIF bundles found in {}; falling back to XMLProvider", filepath)
            from extractor.core.providers.xml import XMLProvider

            return XMLProvider(self.config).extract_document(filepath)

        # Use the first bundle as the primary document; merge others if present
        primary = bundles[0]
        all_blocks: List[BaseBlock] = []
        all_relations: List[Dict[str, str]] = []

        for bundle in bundles:
            blocks, relations = self._extract_bundle(bundle)
            all_blocks.extend(blocks)
            all_relations.extend(relations)

        # Build hierarchy from SPEC-HIERARCHY in primary bundle
        hierarchy = self._build_hierarchy(primary)

        # Build metadata
        metadata = self._extract_metadata(primary, filepath)
        attach_fetcher_metadata(metadata, fetch_download)

        # Store relations in format_metadata for downstream consumers
        if all_relations:
            fm = metadata.format_metadata or {}
            fm["spec_relations"] = all_relations
            metadata.format_metadata = fm

        doc = UnifiedDocument(
            id=self._generate_doc_id(filepath),
            source_type=SourceType.XML,
            source_path=str(filepath),
            blocks=all_blocks,
            hierarchy=hierarchy,
            metadata=metadata,
            full_text=self._extract_full_text(all_blocks),
            keywords=self._extract_keywords(primary),
        )

        logger.info("Extracted {} blocks from ReqIF ({} relations)", len(all_blocks), len(all_relations))
        return ensure_hierarchy(doc, default_title=filepath.stem)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_file(self, filepath: Path) -> List["ReqIFBundle"]:
        """Parse a .reqif or .reqifz file, returning a list of bundles."""
        suffix = filepath.suffix.lower()

        if suffix == ".reqifz":
            return self._parse_reqifz(filepath)
        else:
            bundle = ReqIFParser.parse(str(filepath))
            return [bundle]

    def _parse_reqifz(self, filepath: Path) -> List["ReqIFBundle"]:
        """Extract and parse a .reqifz ZIP archive.

        A .reqifz file is a ZIP containing one or more .reqif XML files
        plus optional attachment files.
        """
        bundles: List["ReqIFBundle"] = []

        with tempfile.TemporaryDirectory(prefix="reqifz_") as tmpdir:
            tmpdir_path = Path(tmpdir)

            try:
                with zipfile.ZipFile(str(filepath), "r") as zf:
                    zf.extractall(tmpdir)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"Invalid .reqifz archive: {filepath}") from exc

            # Find all .reqif files in the extracted archive
            reqif_files = sorted(tmpdir_path.rglob("*.reqif"))
            if not reqif_files:
                raise ValueError(f"No .reqif files found inside {filepath}")

            for reqif_file in reqif_files:
                try:
                    bundle = ReqIFParser.parse(str(reqif_file))
                    bundles.append(bundle)
                except Exception as exc:
                    logger.warning("Failed to parse {} inside archive: {}", reqif_file.name, exc)

        return bundles

    # ------------------------------------------------------------------
    # Bundle extraction
    # ------------------------------------------------------------------

    def _extract_bundle(
        self, bundle: "ReqIFBundle"
    ) -> Tuple[List[BaseBlock], List[Dict[str, str]]]:
        """Extract blocks and relations from a single ReqIF bundle."""
        blocks: List[BaseBlock] = []
        relations: List[Dict[str, str]] = []

        content = getattr(bundle, "core_content", None)
        if content is None:
            return blocks, relations

        req_if_content = getattr(content, "req_if_content", None)
        if req_if_content is None:
            return blocks, relations

        # --- SPEC-OBJECTS (requirements) --------------------------------
        spec_objects = getattr(req_if_content, "spec_objects", None) or []
        for spec_obj in spec_objects:
            block = self._spec_object_to_block(spec_obj, bundle)
            if block:
                blocks.append(block)

        # --- SPEC-RELATIONS (traceability) ------------------------------
        spec_relations = getattr(req_if_content, "spec_relations", None) or []
        for rel in spec_relations:
            rel_dict = self._spec_relation_to_dict(rel)
            if rel_dict:
                relations.append(rel_dict)

        # --- DATA-TYPES as a summary table (optional) -------------------
        data_types = getattr(req_if_content, "data_types", None) or []
        if data_types:
            table = self._data_types_to_table(data_types)
            if table:
                blocks.append(table)

        return blocks, relations

    def _spec_object_to_block(self, spec_obj: Any, bundle: "ReqIFBundle") -> Optional[BaseBlock]:
        """Convert a SPEC-OBJECT into a BaseBlock."""
        identifier = getattr(spec_obj, "identifier", None) or ""
        long_name = getattr(spec_obj, "long_name", None) or ""
        description = getattr(spec_obj, "description", None) or ""
        last_change = getattr(spec_obj, "last_change", None) or ""
        spec_type = getattr(spec_obj, "spec_object_type", None) or ""

        # Collect attribute values
        attributes = getattr(spec_obj, "attributes", None) or []
        attr_texts: List[str] = []
        attr_metadata: Dict[str, str] = {}

        for attr in attributes:
            definition_ref = getattr(attr, "definition_ref", "") or ""

            # Prefer XHTML-stripped text when available
            xhtml_val = getattr(attr, "value_stripped_xhtml", None)
            raw_val = getattr(attr, "value", None)

            if xhtml_val:
                text = _strip_xhtml(xhtml_val)
            elif isinstance(raw_val, list):
                text = ", ".join(str(v) for v in raw_val)
            elif raw_val is not None:
                text = _strip_xhtml(str(raw_val))
            else:
                text = ""

            if text:
                attr_texts.append(text)
                # Use the definition_ref as the key for attribute metadata
                if definition_ref:
                    attr_metadata[definition_ref] = text

        # Build the primary content string — prefer known text attributes,
        # fall back to the longest attribute value.  Metadata-only attributes
        # (creator, dates, IDs) stay in attr_metadata but NOT in block content.
        _PRIMARY_ATTR_KEYS = {
            "reqif.text", "reqif.name", "reqif.description",
            "text", "description", "name", "requirement text",
        }
        primary_texts: List[str] = []
        for def_ref, val in attr_metadata.items():
            if def_ref.lower() in _PRIMARY_ATTR_KEYS or (
                def_ref.lower().startswith("reqif.") and "text" in def_ref.lower()
            ):
                primary_texts.append(val)

        # If no known key matched, use the single longest attribute value
        if not primary_texts and attr_metadata:
            longest = max(attr_metadata.values(), key=len)
            if len(longest) > 5:  # skip short codes / dates
                primary_texts.append(longest)

        content_parts: List[str] = []
        if long_name:
            content_parts.append(long_name)
        if description:
            content_parts.append(description)
        if primary_texts:
            content_parts.extend(primary_texts)
        elif attr_texts:
            # Last resort: include all attribute texts (original behavior)
            content_parts.extend(attr_texts)

        content = "\n".join(content_parts).strip()
        if not content:
            content = f"[SPEC-OBJECT {identifier}]"

        block_id = self._generate_block_id()
        if identifier:
            self._spec_obj_block_map[identifier] = block_id

        return BaseBlock(
            id=block_id,
            type=BlockType.PARAGRAPH,
            content=content,
            metadata=BlockMetadata(
                confidence=0.95,
                source_id=identifier,
                attributes={
                    "reqif_type": "spec_object",
                    "identifier": identifier,
                    "long_name": long_name,
                    "spec_object_type": spec_type,
                    "last_change": last_change,
                    "attribute_values": attr_metadata,
                },
            ),
        )

    def _spec_relation_to_dict(self, rel: Any) -> Optional[Dict[str, str]]:
        """Convert a SPEC-RELATION into a simple dict for metadata storage."""
        source = getattr(rel, "source", None) or ""
        target = getattr(rel, "target", None) or ""
        identifier = getattr(rel, "identifier", None) or ""
        relation_type = getattr(rel, "relation_type_ref", None) or ""
        long_name = getattr(rel, "long_name", None) or ""

        if not (source and target):
            return None

        return {
            "identifier": identifier,
            "source": source,
            "target": target,
            "relation_type_ref": relation_type,
            "long_name": long_name,
        }

    def _data_types_to_table(self, data_types: List[Any]) -> Optional[TableBlock]:
        """Render DATA-TYPES as a summary table block."""
        rows_data: List[Tuple[str, str, str]] = []

        for dt in data_types:
            dt_id = getattr(dt, "identifier", "") or ""
            dt_name = getattr(dt, "long_name", "") or ""
            dt_desc = getattr(dt, "description", "") or ""
            rows_data.append((dt_id, dt_name, dt_desc))

        if not rows_data:
            return None

        headers_row = ["Identifier", "Name", "Description"]
        cells: List[TableCell] = []

        # Header row
        for col_idx, header in enumerate(headers_row):
            cells.append(TableCell(row=0, col=col_idx, content=header))

        # Data rows
        for row_idx, (dt_id, dt_name, dt_desc) in enumerate(rows_data, start=1):
            cells.append(TableCell(row=row_idx, col=0, content=dt_id))
            cells.append(TableCell(row=row_idx, col=1, content=dt_name))
            cells.append(TableCell(row=row_idx, col=2, content=dt_desc))

        return TableBlock(
            id=self._generate_block_id(),
            type=BlockType.TABLE,
            content={"title": "ReqIF Data Types"},
            rows=len(rows_data) + 1,
            cols=3,
            cells=cells,
            headers=[0],
            metadata=BlockMetadata(
                confidence=0.9,
                attributes={"reqif_type": "data_types_summary"},
            ),
        )

    # ------------------------------------------------------------------
    # Hierarchy
    # ------------------------------------------------------------------

    def _build_hierarchy(self, bundle: "ReqIFBundle") -> Optional[HierarchyNode]:
        """Build document hierarchy from SPEC-HIERARCHY tree.

        Each SPECIFICATION in the bundle becomes a top-level section, and
        its nested SPEC-HIERARCHY children map to sub-sections.
        """
        content = getattr(bundle, "core_content", None)
        if content is None:
            return None
        req_if_content = getattr(content, "req_if_content", None)
        if req_if_content is None:
            return None

        specifications = getattr(req_if_content, "specifications", None) or []
        if not specifications:
            return None

        root = HierarchyNode(
            id="root",
            title="Document",
            level=0,
            block_id="root",
            children=[],
        )

        for spec in specifications:
            spec_id = getattr(spec, "identifier", "") or "spec"
            spec_title = getattr(spec, "long_name", None) or spec_id

            spec_node = HierarchyNode(
                id=f"spec-{spec_id}",
                title=spec_title,
                level=1,
                block_id=f"spec-{spec_id}",
                parent_id=root.id,
                children=[],
            )
            root.children.append(spec_node)

            # Walk the SPEC-HIERARCHY children
            children = getattr(spec, "children", None) or []
            for child in children:
                child_node = self._hierarchy_node_from_spec_hierarchy(child, parent=spec_node)
                if child_node:
                    spec_node.children.append(child_node)

        return root

    def _hierarchy_node_from_spec_hierarchy(
        self, hier: Any, parent: HierarchyNode
    ) -> Optional[HierarchyNode]:
        """Recursively convert a SPEC-HIERARCHY element to a HierarchyNode."""
        identifier = getattr(hier, "identifier", None) or ""
        long_name = getattr(hier, "long_name", None) or ""
        level = getattr(hier, "level", 0) or 0
        spec_object_ref = getattr(hier, "spec_object", None) or ""

        # Determine a useful title
        title = long_name or identifier or f"hierarchy-{self.block_counter}"

        # Map to the block created from the referenced SPEC-OBJECT
        block_id = self._spec_obj_block_map.get(spec_object_ref, f"hier-{identifier}")

        # Ensure level is at least parent.level + 1
        node_level = max(level + 1, parent.level + 1)

        node = HierarchyNode(
            id=f"hier-{identifier}",
            title=title,
            level=node_level,
            block_id=block_id,
            parent_id=parent.id,
            children=[],
        )

        # Recurse into children
        children = getattr(hier, "children", None) or []
        for child in children:
            child_node = self._hierarchy_node_from_spec_hierarchy(child, parent=node)
            if child_node:
                node.children.append(child_node)

        return node

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _extract_metadata(self, bundle: "ReqIFBundle", filepath: Path) -> DocumentMetadata:
        """Extract document-level metadata from the ReqIF bundle."""
        metadata = DocumentMetadata()

        format_metadata: Dict[str, Any] = {
            "file_type": "reqif",
        }

        # Header metadata
        header = getattr(bundle, "the_header", None)
        if header:
            title = getattr(header, "title", None)
            if title:
                metadata.title = title
                format_metadata["reqif_title"] = title

            req_if_version = getattr(header, "req_if_version", None)
            if req_if_version:
                format_metadata["reqif_version"] = req_if_version

            source_tool_id = getattr(header, "source_tool_id", None)
            if source_tool_id:
                format_metadata["source_tool_id"] = source_tool_id

            creation_time = getattr(header, "creation_time", None)
            if creation_time:
                format_metadata["creation_time"] = str(creation_time)

        # Namespace
        namespace = getattr(bundle, "namespace", None)
        if namespace:
            format_metadata["namespace"] = namespace

        # Count statistics
        content = getattr(bundle, "core_content", None)
        req_if_content = getattr(content, "req_if_content", None) if content else None
        if req_if_content:
            spec_objects = getattr(req_if_content, "spec_objects", None) or []
            spec_relations = getattr(req_if_content, "spec_relations", None) or []
            specifications = getattr(req_if_content, "specifications", None) or []
            format_metadata["spec_object_count"] = len(spec_objects)
            format_metadata["spec_relation_count"] = len(spec_relations)
            format_metadata["specification_count"] = len(specifications)

        # File metadata
        if filepath.exists():
            metadata.file_size = filepath.stat().st_size

        metadata.format_metadata = format_metadata
        return metadata

    # ------------------------------------------------------------------
    # Text / keyword helpers
    # ------------------------------------------------------------------

    def _extract_full_text(self, blocks: List[BaseBlock]) -> str:
        """Concatenate all text content from blocks."""
        parts: List[str] = []
        for block in blocks:
            if hasattr(block, "content") and isinstance(block.content, str):
                parts.append(block.content)
            elif block.type == BlockType.TABLE and hasattr(block, "cells"):
                for cell in block.cells:
                    if cell.content:
                        parts.append(cell.content)
        return "\n".join(parts)

    def _extract_keywords(self, bundle: "ReqIFBundle") -> List[str]:
        """Extract keywords from spec-object types and relation types."""
        keywords: List[str] = []

        content = getattr(bundle, "core_content", None)
        req_if_content = getattr(content, "req_if_content", None) if content else None
        if req_if_content is None:
            return keywords

        # Spec object type names
        spec_types = getattr(req_if_content, "spec_types", None) or []
        for st in spec_types:
            name = getattr(st, "long_name", None)
            if name:
                keywords.append(name)

        # Relation type names
        spec_relations = getattr(req_if_content, "spec_relations", None) or []
        seen: set = set()
        for rel in spec_relations:
            rt = getattr(rel, "relation_type_ref", None)
            if rt and rt not in seen:
                seen.add(rt)
                keywords.append(rt)

        return list(set(keywords))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _generate_doc_id(self, filepath: Path) -> str:
        """Generate unique document ID."""
        return hashlib.md5(str(filepath).encode()).hexdigest()

    def _generate_block_id(self) -> str:
        """Generate unique block ID."""
        self.block_counter += 1
        return f"reqif-block-{self.block_counter}"
