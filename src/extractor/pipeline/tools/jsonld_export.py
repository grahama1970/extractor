#!/usr/bin/env python3
"""
JSON‑LD Export (v0)

Purpose
- Convert Stage 10 flattened objects (+ optional Stage 11 edges) to a compact
  JSON‑LD graph for downstream consumption without DB dependencies.

Notes
- Keeps surface minimal: file-in, file-out. No pipeline flags changed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _context() -> Dict[str, Any]:
    return {
        "@vocab": "https://schema.org/",
        "id": "@id",
        "type": "@type",
        "PdfObject": "https://example.org/PdfObject",
        "Edge": "https://example.org/Edge",
        "docId": "identifier",
        "sectionId": "identifier",
        "text": "text",
        "relationship_type": "additionalType",
        "source": {"@id": "https://example.org/source", "@type": "@id"},
        "target": {"@id": "https://example.org/target", "@type": "@id"},
    }


def _node_for_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    key = obj.get("_key") or f"obj-{obj.get('object_index_in_doc', 0)}"
    text = obj.get("text_content") or ""
    if len(text) > 200:
        text = text[:200] + "…"
    return {
        "id": f"pdf_objects/{key}",
        "type": "PdfObject",
        "docId": obj.get("doc_id"),
        "sectionId": obj.get("section_id"),
        "text": text,
    }


def _edge_for_edge(e: Dict[str, Any], idx: int) -> Dict[str, Any]:
    return {
        "id": f"edge/{idx}",
        "type": "Edge",
        "source": e.get("_from"),
        "target": e.get("_to"),
        "relationship_type": e.get("relationship_type"),
        "weight": e.get("weight"),
    }


def export_jsonld(stage10_json: Path, edges_json: Optional[Path], out_file: Path) -> Dict[str, Any]:
    objs = json.loads(stage10_json.read_text(encoding="utf-8"))
    if not isinstance(objs, list):
        raise ValueError("Stage 10 JSON must be a list of objects")
    nodes = [_node_for_object(o) for o in objs]
    edges: List[Dict[str, Any]] = []
    if edges_json and edges_json.exists():
        es = json.loads(edges_json.read_text(encoding="utf-8"))
        if isinstance(es, list):
            edges = [_edge_for_edge(e, i) for i, e in enumerate(es)]
    graph = nodes + edges
    payload = {"@context": _context(), "@graph": graph}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return {"ok": True, "nodes": len(nodes), "edges": len(edges), "path": str(out_file)}


if __name__ == "__main__":
    import typer

    app = typer.Typer(add_completion=False)

    @app.command()
    def main(
        stage10: Path,
        edges: Optional[Path] = None,
        out: Path = Path("scripts/artifacts/graph.jsonld"),
    ):
        res = export_jsonld(stage10, edges, out)
        print(json.dumps(res, indent=2))

    app()
