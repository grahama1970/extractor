#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations
import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    source: Path = typer.Argument(..., exists=True, readable=True, help="edge_hints.json or stage11 edges.json"),
    out_json: Path = typer.Argument(Path("graph.json"), help="Viewer-friendly graph JSON (nodes, edges)")
):
    obj = json.loads(source.read_text())
    # Accept either edge_hints (nodes: sections/lemmas, edges: depends_on/contradicts/...) or edges.json with same shape
    if "nodes" in obj and "edges" in obj:
        sections = obj["nodes"].get("sections") or []
        lemmas = obj["nodes"].get("lemmas") or []
        # Normalize nodes to include id and label
        vn_nodes = []
        for s in sections:
            key = s.get("key") or s.get("_key")
            if not key:
                continue
            vn_nodes.append({"id": f"sections/{key}", "label": key, "group": "section"})
        for l in lemmas:
            key = l.get("key") or l.get("_key")
            name = l.get("name") or key
            if not key:
                continue
            vn_nodes.append({"id": f"lemmas/{key}", "label": name, "group": "lemma"})
        vn_edges = []
        for k, arr in (obj["edges"] or {}).items():
            if not isinstance(arr, list):
                continue
            if k in ("depends_on",):
                for e in arr:
                    src = e.get("from"); dst = e.get("to")
                    if not src or not dst:
                        continue
                    vn_edges.append({"from": f"sections/{src}", "to": f"lemmas/{dst}", "label": k})
            elif k in ("contradicts", "contradicts_candidates", "refines", "refines_candidates"):
                for e in arr:
                    a = e.get("a") or e.get("refiner"); b = e.get("b") or e.get("refined")
                    if not a or not b:
                        continue
                    vn_edges.append({"from": f"sections/{a}", "to": f"sections/{b}", "label": k})
        out = {"nodes": vn_nodes, "edges": vn_edges}
        out_json.write_text(json.dumps(out, indent=2))
        typer.secho(f"OK: wrote {out_json}", fg=typer.colors.GREEN)
    else:
        typer.secho("Unrecognized source format; expected nodes+edges", fg=typer.colors.RED)
        raise typer.Exit(2)


if __name__ == "__main__":
    app()

