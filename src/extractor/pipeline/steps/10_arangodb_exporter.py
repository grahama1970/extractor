#!/usr/bin/env python3
"""
Pipeline Stage: Flatten and Load to ArangoDB with Guaranteed Order

Policy: All DB I/O is centralized here (and follow-on graph steps). Earlier
stages (01–09) are offline and write JSON only.

This is the final stage of the pipeline. It takes the hierarchical, reflowed
document structure, flattens it back into a list of individual 'pdf_object'
documents (paragraphs, tables, figures), and enriches each object with the
context of the section it belongs to. Crucially, it preserves the original
top-to-bottom reading order of the document by assigning a global index to each
object before loading into ArangoDB.
"""

import os
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import hashlib
import struct
import re

# Direct, non-abstracted, top-level imports for core functionality
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from rich.console import Console

try:
    from arango import ArangoClient
    from arango.exceptions import ArangoError
    from arango.database import StandardDatabase
except Exception:  # allow import without python-arango
    ArangoClient = None  # type: ignore

    class ArangoError(Exception): ...  # type: ignore

    class StandardDatabase: ...  # type: ignore
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow
from extractor.core.schema.unified_document import (
    BaseBlock,
    BlockType,
    HierarchyNode,
    SourceType,
    TableBlock,
    UnifiedDocument,
)

# --- Initialization & Configuration ---

# Do not load .env or reconfigure logging at import time.

console = Console()

# Optional: units normalization for conflicts
try:
    from pint import UnitRegistry  # type: ignore
    _HAVE_PINT = True
    _UREG = UnitRegistry()
except Exception:
    _HAVE_PINT = False
    _UREG = None  # type: ignore

# Initialize embedding model lazily
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
EMBEDDING_MODEL: Optional[object] = None


def _ensure_embedder():
    global EMBEDDING_MODEL
    # Deterministic path: allow disabling heavy model loads via env (CI/walking skeleton)
    if os.getenv("EMBEDDINGS_DISABLE", "1").lower() in {"1","true","yes"}:
        logger.info("Embeddings disabled via EMBEDDINGS_DISABLE; skipping model load")
        return None
    if EMBEDDING_MODEL is None:
        try:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            from sentence_transformers import SentenceTransformer

            EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.success("Embedding model loaded")
        except Exception as e:
            logger.warning(f"Embedding model unavailable; continuing without embeddings: {e}")
    return EMBEDDING_MODEL


def _derive_doc_set_and_revision(name: str | None) -> tuple[str, str]:
    """Derive a stable doc_set_id and revision_id from a filename or id.

    Precedence:
      1) Explicit environment overrides: DOC_SET_ID, DOC_REVISION_ID
      2) Parse common suffixes from `name` like: "foo-v2.pdf", "foo_r3.pdf"
      3) Fallback to hash-based set id and revision "r0"
    """
    env_set = os.getenv("DOC_SET_ID")
    env_rev = os.getenv("DOC_REVISION_ID")
    if env_set and env_rev:
        return env_set, env_rev

    if not name:
        return "docset", "r0"
    base = str(name)
    base = base.split("/")[-1]
    stem = base.rsplit(".", 1)[0]
    rev = "r0"
    m = re.search(r"([-_])v(?P<num>\d+)$", stem)
    if m:
        rev = f"r{m.group('num')}"
        stem = stem[: m.start()]
    else:
        m2 = re.search(r"([-_])r(?P<num>\d+)$", stem)
        if m2:
            rev = f"r{m2.group('num')}"
            stem = stem[: m2.start()]
    set_id = re.sub(r"[^A-Za-z0-9._-]", "_", stem) or "docset"
    return set_id, rev


def _fast_embedding(text: str, dim: int = 8) -> List[float]:
    """Deterministic, lightweight embedding for smokes.

    Converts md5(text) into `dim` floats in [0,1). Not semantically meaningful,
    but stable across runs and sufficient to exercise Stage 11.
    """
    if not text:
        text = ""
    h = hashlib.md5(text.encode("utf-8")).digest()  # 16 bytes
    # Repeat the hash to fill dim*4 bytes (floats)
    raw = (h * ((dim * 4 + len(h) - 1) // len(h)))[: dim * 4]
    vals = []
    for i in range(dim):
        chunk = raw[i * 4 : (i + 1) * 4]
        # Unpack to unsigned int, normalize to [0,1)
        ui = struct.unpack("!I", chunk)[0]
        vals.append((ui % 10_000_000) / 10_000_000.0)
    return vals


@dataclass
class SectionContext:
    section_id: str
    heading_block_id: str
    title: str
    level: int
    breadcrumb: List[str]


def _table_to_text(table: TableBlock) -> str:
    if table.rows is None or table.rows <= 0 or table.cols is None or table.cols <= 0:
        return ""

    grid: List[List[str]] = [["" for _ in range(table.cols)] for _ in range(table.rows)]
    for cell in table.cells:
        row_idx = min(max(cell.row, 0), table.rows - 1)
        col_idx = min(max(cell.col, 0), table.cols - 1)
        grid[row_idx][col_idx] = cell.content or ""

    lines: List[str] = []
    header_rows = set(table.headers or [])
    for idx, row in enumerate(grid):
        cleaned = [str(col).strip() for col in row]
        lines.append(" | ".join(cleaned))
        if idx in header_rows:
            lines.append(" | ".join(["---" for _ in cleaned]))
    return "\n".join(line for line in lines if line.strip())


def _figure_to_text(block: BaseBlock) -> str:
    if isinstance(block.content, dict):
        title = block.content.get("title") or ""
        caption = block.content.get("caption") or block.content.get("description") or ""
        parts = []
        if title:
            parts.append(f"Figure: {title}")
        if caption:
            parts.append(caption)
        return "\n".join(parts)
    if isinstance(block.content, str):
        return block.content
    return ""


def _block_text(block: BaseBlock | TableBlock) -> str:
    if isinstance(block, TableBlock):
        return _table_to_text(block)
    if block.type == BlockType.FIGURE or block.type == BlockType.IMAGE:
        return _figure_to_text(block)
    if isinstance(block.content, str):
        return block.content
    if isinstance(block.content, dict):
        return str(block.content.get("text") or block.content.get("value") or "")
    if isinstance(block.content, list):
        return "\n".join(str(item) for item in block.content)
    return ""


def _normalize_units_in_text(text: str) -> List[Dict[str, Any]]:
    """Extract and normalize simple '<number> <unit>' patterns using pint, if available.

    Returns a list of dicts with: raw, value, unit, value_si, unit_si, dim
    """
    if not _HAVE_PINT or not text:
        return []
    import re
    out: List[Dict[str, Any]] = []
    # Simple heuristic: capture number + unit token (allows micro symbols)
    pattern = re.compile(r"(?P<val>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Zµμ%][a-zA-Z0-9^*/_\-]*)")
    for m in pattern.finditer(text):
        raw_val = m.group("val"); raw_unit = m.group("unit")
        try:
            q = _UREG.Quantity(f"{raw_val} {raw_unit}")  # type: ignore
            q_si = q.to_base_units()
            out.append({
                "raw": f"{raw_val} {raw_unit}",
                "value": float(q.magnitude),
                "unit": f"{q.units}",
                "value_si": float(q_si.magnitude),
                "unit_si": f"{q_si.units}",
                "dim": str(q.dimensionality),
            })
        except Exception:
            continue
    return out


def _collect_section_contexts(
    hierarchy: Optional[HierarchyNode],
) -> Tuple[Dict[str, SectionContext], Dict[str, SectionContext]]:
    """Build maps from heading block id and section id to SectionContext."""
    contexts_by_block: Dict[str, SectionContext] = {}
    contexts_by_section: Dict[str, SectionContext] = {}

    if hierarchy is None:
        return contexts_by_block, contexts_by_section

    def _walk(node: HierarchyNode, breadcrumb: List[str]) -> None:
        title = node.title or ""
        new_breadcrumb = breadcrumb + ([title] if title else [])
        if node.level > 0:
            context = SectionContext(
                section_id=node.id,
                heading_block_id=node.block_id,
                title=title,
                level=node.level,
                breadcrumb=new_breadcrumb,
            )
            contexts_by_block[node.block_id] = context
            contexts_by_section[node.id] = context
        for child in node.children or []:
            _walk(child, new_breadcrumb)

    _walk(hierarchy, [])
    return contexts_by_block, contexts_by_section


def _coerce_unified_document(pipeline_data: Dict[str, Any]) -> UnifiedDocument:
    """Return a UnifiedDocument from the pipeline payload (reflow or unified_document)."""
    unified_payload = pipeline_data.get("unified_document")
    if unified_payload:
        return UnifiedDocument.model_validate(unified_payload)

    sections = pipeline_data.get("reflowed_sections") or []
    source_files = pipeline_data.get("source_files") or {}
    source_path = source_files.get("sections")
    return build_unified_document_from_reflow(
        sections=sections,
        source_path=source_path,
        source_type=SourceType.PDF,
        document_metadata={"source_files": source_files},
    )


def _find_section_for_block(
    block_id: Optional[str],
    section_by_block: Dict[str, SectionContext],
    parent_map: Dict[str, Optional[str]],
    default: SectionContext,
) -> SectionContext:
    """Walk parent_map to find the nearest SectionContext for the block."""
    current = block_id
    visited: set[str] = set()
    while current:
        if current in section_by_block:
            return section_by_block[current]
        visited.add(current)
        current = parent_map.get(current)
        if current in visited:
            break
    return default


def setup_arango_collection(db: StandardDatabase, collection_name: str):
    """Ensures the target collection and necessary indexes exist."""
    try:
        collection = (
            db.collection(collection_name)
            if db.has_collection(collection_name)
            else db.create_collection(collection_name)
        )

        # Add indexes for common query patterns and ORDERING
        collection.add_persistent_index(fields=["source_pdf", "object_type"], unique=False)
        collection.add_persistent_index(fields=["section_id"], unique=False)
        try:
            collection.add_persistent_index(fields=["doc_id"], unique=False)
        except Exception:
            pass
        # *** CRITICAL: Add an index on the ordering field for fast document reconstruction ***
        collection.add_persistent_index(fields=["object_index_in_doc"], unique=False)
        collection.add_fulltext_index(fields=["text_content"], min_length=3)

        logger.info(f"Collection '{collection_name}' is ready with all necessary indexes.")
    except ArangoError as e:
        logger.error(f"Failed to set up ArangoDB collection '{collection_name}': {e}")
        sys.exit(1)


# --- Flattening and Enrichment Logic ---


def _resolve_object_type(block: BaseBlock | TableBlock) -> str:
    if isinstance(block, TableBlock) or block.type == BlockType.TABLE:
        return "Table"
    if block.type in (BlockType.FIGURE, BlockType.IMAGE):
        return "Figure"
    return "Text"


def flatten_document_to_pdf_objects(
    pipeline_data: Dict[str, Any],
    summaries_data: Dict[str, Any],
    *,
    skip_embeddings: bool = False,
    fast_embeddings: bool = False,
) -> List[Dict[str, Any]]:
    """Flatten a :class:`UnifiedDocument` into ordered Arango-ready objects."""

    unified_document = _coerce_unified_document(pipeline_data)
    summaries = {
        s["section_id"]: s["summary_data"]
        for s in summaries_data.get("summaries", [])
        if isinstance(s, dict) and s.get("success")
    }

    section_by_block, _ = _collect_section_contexts(unified_document.hierarchy)
    parent_map: Dict[str, Optional[str]] = {
        block.id: block.parent_id for block in unified_document.blocks if block.parent_id
    }

    root_title = (
        (unified_document.hierarchy.title if unified_document.hierarchy else None)
        or unified_document.metadata.title
        or "Document"
    )
    root_block_id = (
        unified_document.hierarchy.block_id
        if unified_document.hierarchy
        else (unified_document.blocks[0].id if unified_document.blocks else "document-root")
    )
    root_context = SectionContext(
        section_id="document-root",
        heading_block_id=root_block_id,
        title=root_title or "Document",
        level=0,
        breadcrumb=[root_title] if root_title else [],
    )

    source_pdf = (
        unified_document.metadata.format_metadata.get("source_pdf")
        or unified_document.metadata.format_metadata.get("source_path")
        or (Path(unified_document.source_path).name if unified_document.source_path else None)
        or unified_document.metadata.title
        or unified_document.id
    )
    # Stable doc_id derived from source_pdf or source_path
    doc_id = hashlib.md5(str(source_pdf).encode()).hexdigest() if source_pdf else hashlib.md5((unified_document.id or "doc").encode()).hexdigest()
    doc_set_id, revision_id = _derive_doc_set_and_revision(source_pdf or unified_document.id)

    ordered_objects: List[Dict[str, Any]] = []

    for block in unified_document.blocks:
        if block.type == BlockType.HEADING:
            continue

        object_type = _resolve_object_type(block)
        text_content = _block_text(block)

        if object_type == "Text" and not text_content.strip():
            continue
        if object_type != "Text" and not text_content.strip():
            text_content = object_type

        context = _find_section_for_block(block.parent_id or block.id, section_by_block, parent_map, root_context)
        section_summary = summaries.get(context.section_id)

        unique_id_str = f"{source_pdf}_{context.section_id}_{object_type}_{len(ordered_objects)}"
        key = hashlib.md5(unique_id_str.encode()).hexdigest()
        trace_id = f"{doc_id}-{revision_id}-{len(ordered_objects):06d}"

        embedding = None
        if not skip_embeddings and text_content:
            if fast_embeddings:
                embedding = _fast_embedding(text_content)
            else:
                embedder = _ensure_embedder()
                if embedder is not None:
                    try:
                        embedding = embedder.encode(text_content).tolist()  # type: ignore[attr-defined]
                    except Exception as e:  # pragma: no cover - defensive
                        logger.warning(f"Failed to generate embedding: {e}")

        units_norm = _normalize_units_in_text(text_content)

        # Table typing heuristic: infer column types/units from the header line
        table_typing = None
        if object_type == "Table" and text_content:
            lines = [ln.strip() for ln in text_content.splitlines() if ln.strip()]
            if lines:
                headers = re.split(r"\s{2,}|\t|,|\|", lines[0])
                cols = []
                for h in headers:
                    hm = re.match(r"^(?P<name>[^()]+)\s*(?:\((?P<unit>[^)]+)\))?$", h)
                    name = (hm.group("name") if hm else h).strip()
                    unit = (hm.group("unit") if hm else None)
                    cols.append({"name": name, "unit": unit, "type": "number" if unit else "unknown"})
                table_typing = {"columns": cols}

        ordered_objects.append(
            {
                "_key": key,
                "doc_id": doc_id,
                "doc_set_id": doc_set_id,
                "revision_id": revision_id,
                "trace_id": trace_id,
                "source_pdf": source_pdf,
                "object_index_in_doc": len(ordered_objects),
                "page_num": block.metadata.page_number,
                "bbox": block.metadata.bbox,
                "object_type": object_type,
                "text_content": text_content,
                "embedding": embedding,
                "section_id": context.section_id,
                "section_title": context.title,
                "section_level": context.level,
                "section_breadcrumbs": context.breadcrumb,
                "section_summary": section_summary,
                "data": block.model_dump(mode="json"),
                "units": units_norm,
                **({"table_typing": table_typing} if table_typing else {}),
                # RTM v0: minimal traceability payload for downstream tools
                "rtm": {
                    "section_id": context.section_id,
                    "heading_block_id": context.heading_block_id,
                    "breadcrumb": context.breadcrumb,
                    "evidence": {
                        "page_num": block.metadata.page_number,
                        "bbox": block.metadata.bbox,
                    },
                    "lean4_status": None,
                },
            }
        )

    return ordered_objects


# --- Main Orchestration and CLI ---
def run(
    reflowed_json: Path,
    summaries_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    collection_name: str = "pdf_objects",
    skip_export: bool = False,
    skip_embeddings: bool = False,
    fast_embeddings: bool = False,
) -> Optional[Path]:
    """
    Flattens the processed document and loads it into ArangoDB.
    """
    console.print("[bold green]Starting ArangoDB Export (Stage 10)[/bold green]")

    stage_output_dir = output_dir / "10_arangodb_exporter"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(reflowed_json, "r") as f:
        reflowed_data = json.load(f)
    with open(summaries_json, "r") as f:
        summaries_data = json.load(f)

    pdf_objects_to_load = flatten_document_to_pdf_objects(
        reflowed_data,
        summaries_data,
        skip_embeddings=skip_embeddings,
        fast_embeddings=fast_embeddings,
    )
    if not pdf_objects_to_load:
        console.print("[yellow]No objects to load. Exiting.[/yellow]")
        return None

    # Enrich RTM with Lean4 status when Stage 08 theorems are present
    try:
        theorems_path = output_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
        if theorems_path.exists():
            tdata = json.loads(theorems_path.read_text(encoding="utf-8"))
            proofs = tdata.get("proof_results") if isinstance(tdata, dict) else None
            sec_stats = {}
            sec_analysis: Dict[str, Dict[str, Any]] = {}
            if isinstance(proofs, list):
                for pr in proofs:
                    item = pr.get("item") if isinstance(pr, dict) else {}
                    src = item.get("source_details", {}) if isinstance(item, dict) else {}
                    sec_id = src.get("section_id")
                    if not sec_id:
                        continue
                    st = sec_stats.setdefault(sec_id, {"total": 0, "ok": 0})
                    st["total"] += 1
                    # 'status' is preferred; 'success' maintained for backward-compat
                    status = pr.get("status")
                    if (status is None and pr.get("success")) or str(status).lower() in {"ok", "proved", "success", "true"}:
                        st["ok"] += 1
                    # Capture last seen analysis per section (best-effort)
                    ana = pr.get("analysis") if isinstance(pr, dict) else None
                    if isinstance(ana, dict):
                        sec_analysis[sec_id] = {
                            "lean4_norm": ana.get("normalized_prop"),
                            "lean4_polarity": ana.get("polarity"),
                            "lean4_shape": ana.get("shape"),
                        }
            for obj in pdf_objects_to_load:
                if not isinstance(obj, dict):
                    continue
                rtm = obj.get("rtm") if isinstance(obj.get("rtm"), dict) else None
                if not rtm:
                    continue
                sec_id = rtm.get("section_id")
                st = sec_stats.get(sec_id) if sec_id else None
                if not st:
                    continue
                rtm["lean4_status"] = "proved" if st["ok"] > 0 else "unproved"
                # Additive: pass through normalized proposition metadata when available
                ana = sec_analysis.get(sec_id)
                if ana:
                    rtm.update(ana)
    except Exception as e:
        logger.warning(f"RTM lean4_status enrichment failed: {e}")

    # Always materialize flattened JSON for downstream stages (Stage 11 and tooling)
    try:
        flat_path = json_output_dir / "10_flattened_data.json"
        with open(flat_path, "w") as f:
            json.dump(pdf_objects_to_load, f, indent=2)
        logger.info(f"Wrote flattened data for Stage 11 to: {flat_path}")
    except Exception as e:
        logger.warning(f"Failed to write flattened JSON (continuing): {e}")

    if skip_export:
        console.print(
            "[yellow]--skip-export flag is set. Skipping ArangoDB export (flattened JSON already saved).[/yellow]"
        )
        return None

    try:
        host = os.getenv("ARANGO_HOST", "localhost")
        port = int(os.getenv("ARANGO_PORT", 8529))
        user = os.getenv("ARANGO_USERNAME") or os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DB") or os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

        if not password or ArangoClient is None:
            console.print("[yellow]Arango not configured/available → export skipped; flattened JSON already saved.[/yellow]")
            return

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        console.print(f"[yellow]Arango connection failed → export skipped ({e}); flattened JSON already saved.[/yellow]")
        return None

    setup_arango_collection(db, collection_name)

    try:
        collection = db.collection(collection_name)
        result = collection.import_bulk(pdf_objects_to_load, on_duplicate="replace")

        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "documents_created": result["created"],
            "documents_updated": result["updated"],
            "errors": result["errors"],
        }
        output_path = json_output_dir / "10_export_confirmation.json"
        with open(output_path, "w") as f:
            json.dump(confirmation, f, indent=2)

        console.print("\n[bold green]✅ ArangoDB export complete.[/bold green]")
        console.print(f"   - Confirmation saved to: [cyan]{output_path}[/cyan]")

    except ArangoError as e:
        console.print(f"[yellow]Bulk import failed → export skipped ({e}); flattened JSON present.[/yellow]")
        return


def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    skip_export: bool = True,
    collection_name: str = "pdf_objects",
    skip_embeddings: bool = True,
    fast_embeddings: bool = False,
):
    """Run Stage 10 directly from a consolidated JSON bundle.

    The bundle should include either of:
      - unified_document: canonical structure (preferred)
      - reflowed_sections: list of sections (legacy PDF pipeline)

    Summaries are optional (pass under the ``summaries`` key).
    """
    stage_output_dir = output_dir / "10_arangodb_exporter"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        if not isinstance(data, dict):
            raise ValueError("Bundle root must be an object")
        has_unified = isinstance(data.get("unified_document"), dict)
        has_reflow = isinstance(data.get("reflowed_sections"), list) and data.get(
            "reflowed_sections"
        )
        if not (has_unified or has_reflow):
            raise ValueError(
                "Bundle must include 'unified_document' or non-empty 'reflowed_sections'"
            )
    except Exception as e:
        raise ValueError(f"Failed to load bundle: {e}")

    reflowed_data = data  # treat the bundle itself as the reflowed payload
    summaries_data = {"summaries": data.get("summaries") or []}

    pdf_objects_to_load = flatten_document_to_pdf_objects(
        reflowed_data,
        summaries_data,
        skip_embeddings=skip_embeddings,
        fast_embeddings=fast_embeddings,
    )
    if not pdf_objects_to_load:
        console.print("[yellow]No objects to flatten from bundle. Exiting.[/yellow]")
        return None

    if skip_export:
        output_path = json_output_dir / "10_flattened_data.json"
        output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
        console.print(
            f"[green]Debug bundle: saved {len(pdf_objects_to_load)} flattened objects to {output_path}"
        )
        return

    # Optional export path (rare for debug-bundle)
    try:
        host = os.getenv("ARANGO_HOST", "localhost")
        port = int(os.getenv("ARANGO_PORT", 8529))
        user = os.getenv("ARANGO_USERNAME") or os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DB") or os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

        if not password or ArangoClient is None:
            console.print("[yellow]Arango not configured/available → export skipped; flattened JSON written.[/yellow]")
            output_path = json_output_dir / "10_flattened_data.json"
            output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
            return None

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        console.print(f"[yellow]Arango connection failed → export skipped ({e}); flattened JSON written.[/yellow]")
        output_path = json_output_dir / "10_flattened_data.json"
        output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
        return None

    setup_arango_collection(db, collection_name)
    try:
        collection = db.collection(collection_name)
        result = collection.import_bulk(pdf_objects_to_load, on_duplicate="replace")

        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "documents_created": result["created"],
            "documents_updated": result["updated"],
            "errors": result["errors"],
        }
        output_path = json_output_dir / "10_export_confirmation.json"
        output_path.write_text(json.dumps(confirmation, indent=2))
        console.print(f"[green]Debug bundle: export complete. Confirmation saved to {output_path}")
    except ArangoError as e:
        console.print(f"[yellow]Bulk import failed → export skipped ({e}); flattened JSON available.[/yellow]")
        return


# Minimal __main__ for convenience: import-safe, tiny, and optional.
if __name__ == "__main__":
    # Load .env only for direct invocation
    try:
        load_dotenv(find_dotenv(), override=True)
    except Exception:
        pass
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        # Fail fast if DB env is missing; ensure upstream artifacts exist
        from extractor.pipeline.steps.sanity_helper import sanity_run
        sanity_run("07")
        ok_env = bool(os.getenv("ARANGO_URL") and os.getenv("ARANGO_DB") and (os.getenv("ARANGO_USER") or os.getenv("ARANGO_USERNAME")) and os.getenv("ARANGO_PASSWORD"))
        if not ok_env:
            print("Stage 10 sanity: missing Arango env; skipping DB export. Upstream OK.")
            sys.exit(0)
        print("Stage 10 sanity: Arango env present; run full export via unified runner.")
        sys.exit(0)
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.10_arangodb_exporter REFLOWED_JSON SUMMARIES_JSON [OUT_DIR]\n"
            "       Set SKIP_EXPORT=1 to avoid DB writes.\n",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        reflowed = Path(argv[0])
        summaries = Path(argv[1])
    except IndexError:
        print("Missing arguments. See --help.", file=sys.stderr)
        sys.exit(2)
    out_dir = Path(argv[2]) if len(argv) > 2 else Path("data/results/pipeline")

    skip_export = (os.getenv("SKIP_EXPORT", "0").lower() in {"1", "true", "yes"})
    collection = os.getenv("ARANGO_COLLECTION", "pdf_objects")
    try:
        run(
            reflowed_json=reflowed,
            summaries_json=summaries,
            output_dir=out_dir,
            collection_name=collection,
            skip_export=skip_export,
            skip_embeddings=False,
            fast_embeddings=False,
        )
    except Exception as e:
        logger.error(f"Stage 10 failed: {e}")
        sys.exit(1)
