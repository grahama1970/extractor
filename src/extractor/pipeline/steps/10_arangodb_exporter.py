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

# Direct, non-abstracted, top-level imports for core functionality
import typer
from dotenv import load_dotenv, find_dotenv
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

if not load_dotenv(find_dotenv(), override=True):
    print("Warning: .env not found; proceeding with process environment only.", file=sys.stderr)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> - <level>{message}</level>",
)

console = Console()

# Initialize embedding model lazily
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
EMBEDDING_MODEL: Optional[object] = None


def _ensure_embedder():
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        try:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            from sentence_transformers import SentenceTransformer

            EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.success("Embedding model loaded")
        except Exception as e:
            logger.warning(f"Embedding model unavailable; continuing without embeddings: {e}")
    return EMBEDDING_MODEL


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


def _collect_section_contexts(
    hierarchy: Optional[HierarchyNode],
) -> Tuple[Dict[str, SectionContext], Dict[str, SectionContext]]:
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

        ordered_objects.append(
            {
                "_key": key,
                "doc_id": doc_id,
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
            }
        )

    return ordered_objects


# --- Main Orchestration and CLI ---
def run(
    reflowed_json: Path = typer.Option(
        ..., "--reflowed", help="Path to Stage 07 reflowed sections JSON.", exists=True
    ),
    summaries_json: Path = typer.Option(
        ..., "--summaries", help="Path to Stage 09 summaries JSON.", exists=True
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    collection_name: str = typer.Option("pdf_objects", help="Name of the ArangoDB collection."),
    skip_export: bool = typer.Option(
        False, "--skip-export", help="Prepare data but do not export to ArangoDB."
    ),
    skip_embeddings: bool = typer.Option(
        False,
        "--skip-embeddings/--no-skip-embeddings",
        help="Offline mode: do not compute sentence embeddings; write null in 'embedding' field",
    ),
    fast_embeddings: bool = typer.Option(
        False,
        "--fast-embeddings/--no-fast-embeddings",
        help="Use deterministic 8D hash-based embeddings (fast, CI-safe)",
    ),
):
    """
    Flattens the processed document and loads it into ArangoDB.
    """
    console.print(f"[bold green]Starting ArangoDB Export (Stage 10)[/bold green]")

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
        return

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
        return

    try:
        host = os.getenv("ARANGO_HOST", "localhost")
        port = int(os.getenv("ARANGO_PORT", 8529))
        user = os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

        if not password:
            raise ValueError("ARANGO_PASSWORD environment variable is not set.")

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        logger.error(f"Failed to connect to ArangoDB: {e}")
        raise typer.Exit(1)

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

        console.print(f"\n[bold green]✅ ArangoDB export complete.[/bold green]")
        console.print(f"   - Confirmation saved to: [cyan]{output_path}[/cyan]")

    except ArangoError as e:
        console.print(f"[bold red]Fatal error during bulk import: {e}[/bold red]")
        raise typer.Exit(1)


def debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle with key 'reflowed_sections' and optional 'summaries'",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    skip_export: bool = typer.Option(
        True, "--skip-export/--no-skip-export", help="Flatten and optionally export to ArangoDB."
    ),
    collection_name: str = typer.Option(
        "pdf_objects", help="Name of the ArangoDB collection when exporting."
    ),
    skip_embeddings: bool = typer.Option(
        True,
        "--skip-embeddings/--no-skip-embeddings",
        help="Offline mode: do not compute embeddings in debug bundle path",
    ),
    fast_embeddings: bool = typer.Option(
        False,
        "--fast-embeddings/--no-fast-embeddings",
        help="Use deterministic 8D hash-based embeddings (fast, CI-safe)",
    ),
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
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

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
        return

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
        user = os.getenv("ARANGO_USER", "root")
        password = os.getenv("ARANGO_PASSWORD")
        db_name = os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

        if not password:
            raise ValueError("ARANGO_PASSWORD environment variable is not set.")

        client = ArangoClient(hosts=f"http://{host}:{port}")
        db = client.db(db_name, username=user, password=password)
        db.version()
        logger.success(f"Connected to ArangoDB database '{db_name}'.")
    except (ArangoError, ValueError) as e:
        logger.error(f"Failed to connect to ArangoDB: {e}")
        raise typer.Exit(1)

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
        console.print(f"[bold red]Fatal error during bulk import: {e}[/bold red]")
        raise typer.Exit(1)


def build_cli():
    import typer as _typer

    app = _typer.Typer(
        help="Flattens and exports final processed sections into ArangoDB, preserving document order."
    )
    app.command(name="run")(run)
    app.command(name="debug-bundle")(debug_bundle)
    return app


if __name__ == "__main__":
    build_cli()()
