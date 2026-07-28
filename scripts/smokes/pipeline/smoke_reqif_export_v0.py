#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: ReqIF export v0

Purpose
- Exercise the minimal ReqIF exporter against a synthetic Stage 10 flattened JSON payload.
- Verify a .reqif file is produced and non-empty; save a short summary artifact.

Artifacts
- scripts/artifacts/reqif_export_v0.json (summary)
- scripts/artifacts/export.reqif (ReqIF file)
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import typer

from extractor.pipeline.tools.reqif_export import export_reqif

app = typer.Typer(add_completion=False)


def _synthetic_stage10(flattened_path: Path) -> None:
    """Generate synthetic document objects and write to path."""
    data = [
        {
            "_key": "obj-0001",
            "doc_id": "doc-sample",
            "object_index_in_doc": 1,
            "section_id": "sec-1",
            "section_title": "Introduction",
            "text_content": "The system shall operate between -40C and +85C.",
            "rtm": {
                "section_id": "sec-1",
                "breadcrumb": ["1", "Introduction"],
                "evidence": {"page": 1},
                "lean4_status": "unknown",
            },
        }
    ]
    flattened_path.parent.mkdir(parents=True, exist_ok=True)
    flattened_path.write_text(json.dumps(data, indent=2))


@app.command()
def main(
    out_dir: Path = Path("scripts/artifacts"),
):
    """Generate and export synthetic data to ReqIF."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stage10 = out_dir / "synthetic_stage10_flattened.json"
    _synthetic_stage10(stage10)
    out_file = out_dir / "export.reqif"
    res = export_reqif(stage10, out_file)
    ok = bool(res.get("ok") and out_file.exists() and out_file.stat().st_size > 50)
    summary = {
        "ok": ok,
        "count": res.get("count", 0),
        "path": str(out_file),
        "stage10": str(stage10),
    }
    (out_dir / "reqif_export_v0.json").write_text(json.dumps(summary, indent=2))
    typer.echo(json.dumps(summary, indent=2))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    app()
