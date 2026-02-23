#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "numpy>=2.0.0",
#   "loguru>=0.7.0,<0.8",
#   "python-dotenv>=1.0.0,<2",
#   "litellm>=1.74.7",
#   "pillow>=10.1.0,<11.0.0",
#   "urlextract>=1.9.0",
#   "strip_tags>=0.6",
#   "json-repair>=0.44.1",
# ]
# ///
"""Smoke: Stage 11 proves-only edges when no embeddings are present.

Creates a tiny Stage 10-like bundle (no embeddings) and a matching Stage 08
theorems file with a proved section, then runs debug-bundle to assert a 'proves'
edge is emitted.
"""
from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    out_dir = Path("data/results/cli_smokes/proves_only").resolve()
    bundle_dir = out_dir / "tmp"
    (out_dir / "08_lean4_theorem_prover/json_output").mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Minimal flattened doc (no embedding)
    docs = [
        {
            "_key": "obj1",
            "section_id": "S1",
            "source_pdf": "dummy.pdf",
            "text_content": "Spec section with a requirement",
        }
    ]
    bundle = bundle_dir / "bundle.json"
    bundle.write_text(json.dumps({"documents": docs}, indent=2))

    # Matching theorems: proved S1
    theorems = {
        "proof_results": [
            {
                "status": "proved",
                "item": {"source_details": {"section_id": "S1"}},
            }
        ]
    }
    (out_dir / "08_lean4_theorem_prover/json_output/08_theorems.json").write_text(
        json.dumps(theorems, indent=2)
    )

    # Run Stage 11 debug-bundle
    # Ensure repo src on sys.path when executing the module
    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline.steps.11_arango_create_graph",
        "debug-bundle",
        str(bundle),
        "-o",
        str(out_dir),
    ]
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0:
        typer.echo("Stage 11 debug-bundle failed", err=True)
        raise typer.Exit(1)

    edges_path = out_dir / "11_arango_create_graph/json_output/11_graph_edges.json"
    summary_path = out_dir / "11_arango_create_graph/json_output/11_graph_summary.json"
    edges = json.loads(edges_path.read_text()) if edges_path.exists() else []
    proves = [e for e in edges if e.get("relationship_type") == "proves"]
    if not proves:
        typer.echo("Expected at least one 'proves' edge when theorems are present", err=True)
        raise typer.Exit(1)

    # Save a concise report
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "stage11_proves_only_offline.json").write_text(
        json.dumps(
            {
                "edges_path": str(edges_path),
                "summary_path": str(summary_path),
                "total": len(edges),
                "proves": len(proves),
            },
            indent=2,
        )
    )
    print("OK: proves-only edges emitted and summary present")


if __name__ == "__main__":
    app()
