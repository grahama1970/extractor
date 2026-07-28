#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12"]
# ///
from __future__ import annotations
import json
from pathlib import Path
import typer

TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Lean4 Graph Viewer</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    html, body, #graph { width: 100%; height: 100%; margin: 0; padding: 0; }
  </style>
</head>
<body>
  <div id="graph"></div>
  <script>
    const data = __DATA__;
    // Convert to vis format
    const nodes = new vis.DataSet(data.nodes.map(n => ({ id: n.id, label: n.label, group: n.group })));
    const edges = new vis.DataSet(data.edges.map(e => ({ from: e.from, to: e.to, label: e.label, arrows: 'to' })));
    const container = document.getElementById('graph');
    const network = new vis.Network(container, { nodes, edges }, {
      physics: { stabilization: true },
      interaction: { hover: true },
      edges: { smooth: { type: 'dynamic' } }
    });
  </script>
  </body>
  </html>
"""

app = typer.Typer(add_completion=False)


@app.command()
def main(
    viewer_json: Path = typer.Argument(..., exists=True, readable=True),
    out_html: Path = typer.Argument(Path("viewer.html")),
):
    """Generate HTML from JSON input and save to specified output path."""
    payload = json.loads(viewer_json.read_text())
    html = TEMPLATE.replace("__DATA__", json.dumps(payload))
    out_html.write_text(html)
    typer.secho(f"OK: wrote {out_html}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
