#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12"]
# ///
from __future__ import annotations
import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)

@app.command()
def main(source: Path = typer.Argument(..., exists=True, readable=True), out_json: Path = typer.Argument(Path("graph.json"))):
    """Best-effort adapter for doc-gen4 style JSON (nodes with _key and edges with _from/_to)
    to viewer graph.json (nodes: id/label/group; edges: from/to/label).
    """
    obj = json.loads(source.read_text())
    nodes = obj.get("nodes") or []
    edges = obj.get("edges") or []
    vn_nodes = []
    for n in nodes:
        key = n.get("_key") or n.get("key") or n.get("id")
        coll = n.get("_id", "").split("/")[0] if n.get("_id") else n.get("collection") or "node"
        if not key:
            # Try deriving from _id
            _id = n.get("_id")
            if _id and "/" in _id:
                coll, key = _id.split("/", 1)
        if not key:
            continue
        label = n.get("label") or n.get("title") or key
        group = coll if coll in ("sections","lemmas","theorems") else "node"
        vn_nodes.append({"id": f"{coll}/{key}", "label": label, "group": group})
    vn_edges = []
    for e in edges:
        _from = e.get("_from"); _to = e.get("_to")
        if not _from or not _to:
            continue
        label = e.get("type") or e.get("label") or "edge"
        vn_edges.append({"from": _from, "to": _to, "label": label})
    out_json.write_text(json.dumps({"nodes": vn_nodes, "edges": vn_edges}, indent=2))
    typer.secho(f"OK: wrote {out_json}", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()

