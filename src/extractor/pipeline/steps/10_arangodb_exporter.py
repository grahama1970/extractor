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
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import hashlib

# Direct, non-abstracted, top-level imports for core functionality
try:
    try:
        import typer
        _HAS_TYPER = True
    except Exception:
        _HAS_TYPER = False
        class _TyperShim:
            def __init__(self,*a,**k): pass
            def command(self,*a,**k): return lambda f: f
            def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
        def _opt(*a,**k): return None
        def _arg(*a,**k): return None
        typer = _TyperShim()  # type: ignore
        typer.Typer = _TyperShim  # type: ignore
        typer.Option = _opt  # type: ignore
        typer.Argument = _arg  # type: ignore
        typer.secho = print  # type: ignore

    _HAS_TYPER = True
except Exception:  # allow import without Typer for agent debugging
    _HAS_TYPER = False
    class _TyperShim:
        def __init__(self,*a,**k): pass
        def command(self,*a,**k): return lambda f: f
        def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
    def _opt(*a,**k): return None
    def _arg(*a,**k): return None
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Option = _opt  # type: ignore
    typer.Argument = _arg  # type: ignore
    typer.secho = print  # type: ignore

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

from typing import Optional

# --- Initialization & Configuration ---

if not load_dotenv(find_dotenv(), override=True):
    print("FATAL: .env file not found. Please create one.", file=sys.stderr)
    sys.exit(1)

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> - <level>{message}</level>")

app = typer.Typer(help="Flattens and exports final processed sections into ArangoDB, preserving document order.")
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

def setup_arango_collection(db: StandardDatabase, collection_name: str):
    """Ensures the target collection and necessary indexes exist."""
    try:
        collection = db.collection(collection_name) if db.has_collection(collection_name) else db.create_collection(collection_name)
        
        # Add indexes for common query patterns and ORDERING
        collection.add_persistent_index(fields=["source_pdf", "object_type"], unique=False)
        collection.add_persistent_index(fields=["section_id"], unique=False)
        # *** CRITICAL: Add an index on the ordering field for fast document reconstruction ***
        collection.add_persistent_index(fields=["object_index_in_doc"], unique=False)
        collection.add_fulltext_index(fields=["text_content"], min_length=3)
        
        logger.info(f"Collection '{collection_name}' is ready with all necessary indexes.")
    except ArangoError as e:
        logger.error(f"Failed to set up ArangoDB collection '{collection_name}': {e}"); sys.exit(1)

# --- Flattening and Enrichment Logic ---

def generate_breadcrumbs(sections_map: Dict, section: Dict) -> List[str]:
    """Recursively generates a breadcrumb trail for a section."""
    breadcrumbs = [section.get("title", "Untitled")]
    parent_id = section.get("parent_id")
    while parent_id and parent_id in sections_map:
        parent_section = sections_map[parent_id]
        breadcrumbs.insert(0, parent_section.get("title", "Untitled"))
        parent_id = parent_section.get("parent_id")
    return breadcrumbs

def flatten_document_to_pdf_objects(
    pipeline_data: Dict,
    summaries_data: Dict,
) -> List[Dict]:
    """
    Transforms the hierarchical section structure back into a single, ordered,
    flat list of enriched pdf_object documents.
    """
    
    sections = pipeline_data.get("reflowed_sections", [])
    # Prefer consistent source_pdf propagated from Stage 07 (via Stage 01 annotations)
    source_pdf = "unknown.pdf"
    try:
        candidates = [s.get("source_pdf") for s in sections if isinstance(s, dict) and s.get("source_pdf")]
        if candidates:
            from collections import Counter
            c = Counter(candidates)
            source_pdf = c.most_common(1)[0][0]
        else:
            source_pdf = pipeline_data.get("source_files", {}).get("sections", "unknown.pdf")
    except Exception:
        source_pdf = pipeline_data.get("source_files", {}).get("sections", "unknown.pdf")
    summaries = {s["section_id"]: s["summary_data"] for s in summaries_data.get("summaries", []) if s.get("success")}

    if not sections:
        return []

    sections_map = {s['id']: s for s in sections}
    all_elements_for_sorting = []

    # --- Step 1: Consolidate all elements from all sections ---
    for section in sections:
        # Accept fallback reflows as valid text containers for export
        if section.get('reflow_status') not in ['success', 'success_placeholder', 'fallback']:
            continue

        section_summary = summaries.get(section.get("id"))
        section_context = {
            "section_id": section.get("id"),
            "section_title": section.get("title"),
            "section_level": section.get("level"),
            "section_breadcrumbs": generate_breadcrumbs(sections_map, section),
            "section_summary": section_summary,
        }
        
        if section.get("reflowed_text"):
            all_elements_for_sorting.append({
                "page_num": section.get("page_start"),
                "bbox": section.get("bbox"),
                "object_type": "Text",
                "content": {"text": section.get("reflowed_text")},
                "context": section_context
            })
            
        for table in section.get("tables", []):
            all_elements_for_sorting.append({
                "page_num": table.get("page_index"),
                "bbox": table.get("bbox"),
                "object_type": "Table",
                "content": table,
                "context": section_context
            })

        for figure in section.get("figures", []):
            all_elements_for_sorting.append({
                "page_num": figure.get("page"),
                "bbox": figure.get("bbox"),
                "object_type": "Figure",
                "content": figure,
                "context": section_context
            })
    
    all_elements_for_sorting.sort(key=lambda x: (x.get('page_num', 0), (x.get('bbox') or [0,0,0,0])[1]))

    final_pdf_objects = []
    for i, element in enumerate(all_elements_for_sorting):
        content = element["content"]
        context = element["context"]
        
        if element["object_type"] == "Text":
            text_content = content.get("text", "")
        elif element["object_type"] == "Table":
            text_content = f"Table: {content.get('title')}\nHeaders: {content.get('headers')}"
        elif element["object_type"] == "Figure":
            text_content = f"Figure: {content.get('title')}\nDescription: {content.get('ai_description')}"
        else:
            text_content = ""

        unique_id_str = f"{source_pdf}_{context['section_id']}_{element['object_type']}_{i}"
        key = hashlib.md5(unique_id_str.encode()).hexdigest()
        
        embedding = None
        if text_content and _ensure_embedder() is not None:
            try:
                embedding = EMBEDDING_MODEL.encode(text_content).tolist()
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        final_pdf_objects.append({
            "_key": key,
            "source_pdf": source_pdf,
            "object_index_in_doc": i,
            "page_num": element.get("page_num"),
            "bbox": element.get("bbox"),
            "object_type": element["object_type"],
            "text_content": text_content,
            "embedding": embedding,
            "data": content,
            **context
        })
        
    return final_pdf_objects

# --- Main Orchestration and CLI ---
@app.command()
def run(
    reflowed_json: Path = typer.Option(..., "--reflowed", help="Path to Stage 07 reflowed sections JSON.", exists=True),
    summaries_json: Path = typer.Option(..., "--summaries", help="Path to Stage 09 summaries JSON.", exists=True),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    collection_name: str = typer.Option("pdf_objects", help="Name of the ArangoDB collection."),
    skip_export: bool = typer.Option(False, "--skip-export", help="Prepare data but do not export to ArangoDB."),
):
    """
    Flattens the processed document and loads it into ArangoDB.
    """
    console.print(f"[bold green]Starting ArangoDB Export (Stage 10)[/bold green]")

    stage_output_dir = output_dir / "10_arangodb_exporter"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(reflowed_json, 'r') as f:
        reflowed_data = json.load(f)
    with open(summaries_json, 'r') as f:
        summaries_data = json.load(f)

    pdf_objects_to_load = flatten_document_to_pdf_objects(reflowed_data, summaries_data)
    if not pdf_objects_to_load:
        console.print("[yellow]No objects to load. Exiting.[/yellow]")
        return

    if skip_export:
        console.print("[yellow]--skip-export flag is set. Saving flattened data to JSON instead of exporting.[/yellow]")
        output_path = json_output_dir / "10_flattened_data.json"
        with open(output_path, 'w') as f:
            json.dump(pdf_objects_to_load, f, indent=2)
        console.print(f"📄 Saved {len(pdf_objects_to_load)} flattened objects to: {output_path}")
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
        result = collection.import_bulk(pdf_objects_to_load, on_duplicate='replace')
        
        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "documents_created": result['created'],
            "documents_updated": result['updated'],
            "errors": result['errors'],
        }
        output_path = json_output_dir / "10_export_confirmation.json"
        with open(output_path, 'w') as f:
            json.dump(confirmation, f, indent=2)

        console.print(f"\n[bold green]✅ ArangoDB export complete.[/bold green]")
        console.print(f"   - Confirmation saved to: [cyan]{output_path}[/cyan]")

    except ArangoError as e:
        console.print(f"[bold red]Fatal error during bulk import: {e}[/bold red]")
        raise typer.Exit(1)

 

@app.command("debug-bundle")
def debug_bundle(
    bundle: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Bundle with key 'reflowed_sections' and optional 'summaries'"),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    skip_export: bool = typer.Option(True, "--skip-export/--no-skip-export", help="Flatten and optionally export to ArangoDB."),
    collection_name: str = typer.Option("pdf_objects", help="Name of the ArangoDB collection when exporting."),
):
    """Run Stage 10 directly from a consolidated JSON bundle.

    The bundle should include:
      - reflowed_sections: list of sections (required)
      - summaries: list of section summaries (optional)
    """
    stage_output_dir = output_dir / "10_arangodb_exporter"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        if not isinstance(data, dict):
            raise ValueError("Bundle root must be an object")
        if not isinstance(data.get("reflowed_sections"), list) or not data.get("reflowed_sections"):
            raise ValueError("Bundle must include non-empty 'reflowed_sections' list")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    reflowed_data = data  # treat the bundle itself as the reflowed payload
    summaries_data = {"summaries": data.get("summaries") or []}

    pdf_objects_to_load = flatten_document_to_pdf_objects(reflowed_data, summaries_data)
    if not pdf_objects_to_load:
        console.print("[yellow]No objects to flatten from bundle. Exiting.[/yellow]")
        return

    if skip_export:
        output_path = json_output_dir / "10_flattened_data.json"
        output_path.write_text(json.dumps(pdf_objects_to_load, indent=2))
        console.print(f"[green]Debug bundle: saved {len(pdf_objects_to_load)} flattened objects to {output_path}")
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
        result = collection.import_bulk(pdf_objects_to_load, on_duplicate='replace')

        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "documents_created": result['created'],
            "documents_updated": result['updated'],
            "errors": result['errors'],
        }
        output_path = json_output_dir / "10_export_confirmation.json"
        output_path.write_text(json.dumps(confirmation, indent=2))
        console.print(f"[green]Debug bundle: export complete. Confirmation saved to {output_path}")
    except ArangoError as e:
        console.print(f"[bold red]Fatal error during bulk import: {e}[/bold red]")
        raise typer.Exit(1)
 
if __name__ == "__main__":
    app()
