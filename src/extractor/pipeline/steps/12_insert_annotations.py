#!/usr/bin/env python3
"""
Stage 12: Insert Annotations into ArangoDB and Bridge to pdf_objects

Purpose:
- Load Stage 01 annotations JSON into ArangoDB `annotations` collection
- Create bidirectional edges between annotations and pdf_objects on the same page
- Ensure the graph includes both vertex collections so Stage 07 can traverse

CLI:
  python 12_insert_annotations.py \
    --annotations data/results/pipeline/01_annotation_processor/json_output/01_annotations.json \
    -o data/results/pipeline

Env required:
  ARANGO_HOST, ARANGO_PORT, ARANGO_USER, ARANGO_PASS, ARANGO_DATABASE
  GRAPH_NAME (default pdf_knowledge_graph)
  GRAPH_EDGE_COLLECTION (default pdf_relationships)
  ARANGO_ANNOTATIONS_COLLECTION (default annotations)
  GRAPH_VERTEX_COLLECTION (default pdf_objects)
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import typer
from dotenv import load_dotenv, find_dotenv
from loguru import logger
from rich.console import Console

try:
    from arango.client import ArangoClient
    from arango.database import StandardDatabase
except ImportError:
    print(
        "python-arango is required for Stage 12. Please install it to use DB features.",
        file=sys.stderr,
    )
    raise

console = Console()


def ensure_graph(
    db: StandardDatabase, graph_name: str, edge_col: str, vertex_cols: List[str]
) -> None:
    if not db.has_graph(graph_name):
        db.create_graph(
            name=graph_name,
            edge_definitions=[
                {
                    "edge_collection": edge_col,
                    "from_vertex_collections": vertex_cols,
                    "to_vertex_collections": vertex_cols,
                }
            ],
        )
        logger.info(f"Created graph {graph_name} with vertices {vertex_cols}")
    else:
        g = db.graph(graph_name)
        # Try to add missing vertex collections to edge definition
        try:
            edefs = g.edge_definitions()
            if edefs:
                ed = edefs[0]
                changed = False
                fv = set(ed.get("from", []))
                tv = set(ed.get("to", []))
                for v in vertex_cols:
                    if v not in fv:
                        fv.add(v)
                        changed = True
                    if v not in tv:
                        tv.add(v)
                        changed = True
                if changed:
                    # Graph API in arango-python doesn't expose update edge def; recreate is safer for this utility
                    db.delete_graph(graph_name)
                    db.create_graph(
                        name=graph_name,
                        edge_definitions=[
                            {
                                "edge_collection": ed.get("collection", edge_col),
                                "from_vertex_collections": list(fv),
                                "to_vertex_collections": list(tv),
                            }
                        ],
                    )
                    logger.info(f"Recreated graph {graph_name} with updated vertices {list(fv)}")
        except Exception as e:
            logger.warning(f"Graph inspection failed (continuing): {e}")


def run(
    annotations: Path = typer.Option(
        ..., "--annotations", help="Path to Stage 01 annotations JSON", exists=True
    ),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Results base directory"),
    mode: str = typer.Option("both", "--mode", help="Operation: insert | bridge | both"),
):
    if not load_dotenv(find_dotenv(), override=True):
        console.print("[yellow].env not found; relying on process env.[/yellow]")

    host = os.getenv("ARANGO_HOST", "localhost")
    port = int(os.getenv("ARANGO_PORT", 8529))
    user = os.getenv("ARANGO_USERNAME") or os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")
    db_name = os.getenv("ARANGO_DB") or os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")
    vertex_col = os.getenv("GRAPH_VERTEX_COLLECTION", "pdf_objects")
    ann_col = os.getenv("ARANGO_ANNOTATIONS_COLLECTION", "annotations")
    edge_col = os.getenv("GRAPH_EDGE_COLLECTION", "pdf_relationships")
    graph_name = os.getenv("GRAPH_NAME", "pdf_knowledge_graph")

    if not password:
        console.print("[red]ARANGO_PASS / ARANGO_PASSWORD not set[/red]")
        raise typer.Exit(1)

    client = ArangoClient(hosts=f"http://{host}:{port}")
    # Ensure DB
    sys_db = client.db("_system", username=user, password=password)
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
        logger.info(f"Created DB {db_name}")
    db = client.db(db_name, username=user, password=password)

    # Ensure collections
    if not db.has_collection(ann_col):
        db.create_collection(ann_col)
        logger.info(f"Created collection {ann_col}")
    if not db.has_collection(vertex_col):
        db.create_collection(vertex_col)
        logger.info(f"Created collection {vertex_col}")
    if not db.has_collection(edge_col):
        db.create_collection(edge_col, edge=True)
        logger.info(f"Created edge collection {edge_col}")

    ensure_graph(db, graph_name, edge_col, [vertex_col, ann_col])

    with open(annotations, "r") as f:
        payload = json.load(f)
    anns = payload.get("annotations", [])
    source_pdf: Optional[str] = payload.get("source_pdf")
    if not anns:
        console.print("[yellow]No annotations to insert.[/yellow]")
        # still permit bridge mode to run using already inserted annotations
        if mode.lower() not in {"bridge", "both"}:
            return

    # Prepare annotation docs
    docs: List[Dict[str, Any]] = []
    for a in anns:
        aid = a.get("id") or a.get("_key")
        if not aid:
            continue

        # Simple text aggregation for BM25
        def _blocks_to_text(blocks: List[Dict[str, Any]], max_chars: int = 600) -> str:
            parts: List[str] = []
            for blk in blocks or []:
                for ln in blk.get("lines", []):
                    for sp in ln.get("spans", []):
                        t = (sp.get("text") or "").strip()
                        if t:
                            parts.append(t)
            s = " ".join(parts)
            s = " ".join(s.split())
            return s[:max_chars]

        inside = _blocks_to_text(a.get("inside_blocks", []))
        above = _blocks_to_text(a.get("above_blocks", []), 300)
        below = _blocks_to_text(a.get("below_blocks", []), 300)
        docs.append(
            {
                "_key": aid,
                "page": a.get("page"),
                "type": a.get("type"),
                "original_rect": a.get("original_rect"),
                "expanded_rect": a.get("expanded_rect"),
                "source_pdf": source_pdf,
                "text_inside": inside,
                "text_above": above,
                "text_below": below,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    mode_l = (mode or "both").lower().strip()
    if mode_l not in {"insert", "bridge", "both"}:
        console.print("[red]Invalid --mode. Use: insert | bridge | both[/red]")
        raise typer.Exit(2)

    # Upsert annotations
    if mode_l in {"insert", "both"} and docs:
        col = db.collection(ann_col)
        res = col.import_bulk(docs, on_duplicate="update")
        logger.info(
            f"Annotations upserted: created={res.get('created',0)}, updated={res.get('updated',0)}"
        )

    # Build edges annotation <-> pdf_objects on same page
    if mode_l in {"bridge", "both"}:
        # If we didn't insert in this run, fetch minimal docs for bridging
        docs_for_bridge = docs
        if not docs_for_bridge:
            try:
                aql_fetch = f"""
                FOR a IN {ann_col}
                  FILTER @src == null OR a.source_pdf == @src
                  RETURN {{ _key: a._key, page: a.page }}
                """
                rows = list(db.aql.execute(aql_fetch, bind_vars={"src": source_pdf}))
                docs_for_bridge = [
                    {"_key": r.get("_key"), "page": r.get("page")}
                    for r in rows
                    if r.get("_key") is not None
                ]
            except Exception as e:
                logger.warning(f"Failed to fetch annotations for bridging: {e}")
                docs_for_bridge = []

        edge_docs: List[Dict[str, Any]] = []
        for d in docs_for_bridge:
            page = d.get("page")
            if page is None:
                continue
            aql = f"""
                FOR o IN {vertex_col}
                  FILTER o.page_num == @p
                    AND (@src == null OR o.source_pdf == @src)
                  RETURN o._id
                """
            try:
                ids = list(db.aql.execute(aql, bind_vars={"p": int(page), "src": source_pdf}))
            except Exception:
                ids = []
            aid = f"{ann_col}/{d['_key']}"
            for oid in ids:
                edge_docs.append(
                    {
                        "_from": aid,
                        "_to": oid,
                        "relationship_type": "ann_to_object",
                        "weight": 0.2,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                edge_docs.append(
                    {
                        "_from": oid,
                        "_to": aid,
                        "relationship_type": "object_to_ann",
                        "weight": 0.2,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
        if edge_docs:
            ecol = db.collection(edge_col)
            edres = ecol.import_bulk(edge_docs, on_duplicate="ignore")
            logger.info(
                f"Edges inserted: created={edres.get('created',0)}, errors={edres.get('errors',0)}"
            )

    if mode_l == "insert":
        console.print("[bold green]✅ Annotations inserted.[/bold green]")
    elif mode_l == "bridge":
        console.print("[bold green]✅ Annotation↔pdf_object edges bridged.[/bold green]")
    else:
        console.print(
            "[bold green]✅ Annotations inserted and bridged to pdf_objects.[/bold green]"
        )


def debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle with keys 'annotations' and optional 'pdf_objects'",
    ),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Results base directory"),
):
    """Dry-run: validate bundle and estimate potential edges. No DB ops."""
    stage_output_dir = Path(output_dir) / "12_insert_annotations"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        annotations = data.get("annotations") or []
        pdf_objects = data.get("pdf_objects") or []
        if not isinstance(annotations, list) or not annotations:
            raise ValueError("Bundle must include non-empty 'annotations' list")
        if not isinstance(pdf_objects, list):
            pdf_objects = []
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    ann_pages = [a.get("page") for a in annotations if a.get("page") is not None]
    obj_pages = [o.get("page_num") for o in pdf_objects if o.get("page_num") is not None]
    potential_edges = 0
    if obj_pages:
        from collections import Counter

        c_ann = Counter(ann_pages)
        c_obj = Counter(obj_pages)
        for p, ca in c_ann.items():
            potential_edges += ca * c_obj.get(p, 0)

    result = {
        "timestamp": datetime.now().isoformat(),
        "status": "DryRun",
        "annotations_count": len(annotations),
        "pdf_objects_count": len(pdf_objects),
        "potential_edges": int(potential_edges),
        "note": "No DB operations performed in debug-bundle mode.",
    }
    out = json_output_dir / "12_insert_debug.json"
    out.write_text(json.dumps(result, indent=2))
    console.print(f"[green]Debug bundle: wrote {out}")


def build_cli():
    import typer as _typer

    app = _typer.Typer(help="Insert Stage 01 annotations into Arango and bridge to pdf_objects")
    app.command(name="run")(run)
    app.command(name="debug-bundle")(debug_bundle)
    return app


if __name__ == "__main__":
    build_cli()()
