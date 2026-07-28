#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "python-arango>=8.2.0",
# ]
# ///
from __future__ import annotations

import json
import os
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(
    add_completion=False, help="Smoke: Stage 12 annotations insert + bridge in Arango"
)


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline_db_smoke"), "-o")) -> None:
    """Run pipeline smoke test and save results to specified output path."""
    load_dotenv(find_dotenv() or None)
    source_pdf = "BHT_CV32A65X_marked.pdf"

    # Minimal annotations payload that matches page=0 and source_pdf
    anns = {
        "source_pdf": source_pdf,
        "annotations": [
            {
                "id": "ann1",
                "page": 0,
                "type": "section_header",
                "original_rect": [50, 50, 140, 90],
                "expanded_rect": [40, 40, 160, 120],
                "inside_blocks": [{"lines": [{"spans": [{"text": "Intro"}]}]}],
                "above_blocks": [],
                "below_blocks": [],
            }
        ],
    }

    tmp = results / "_smokes_tmp12_db"
    tmp.mkdir(parents=True, exist_ok=True)
    a01 = tmp / "01_annotations.json"
    a01.write_text(json.dumps(anns))

    spec = importlib.util.spec_from_file_location(
        "stage12", "src/extractor/pipeline/steps/12_insert_annotations.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 12 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    # Insert then bridge
    mod.run(annotations=a01, output_dir=results, mode="both")

    # Quick DB checks
    from arango import ArangoClient

    host = os.getenv("ARANGO_HOST", "localhost")
    port = int(os.getenv("ARANGO_PORT", 8529))
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASS")
    db_name = os.getenv("ARANGO_DATABASE", "pdf_knowledge_base_test")
    if not password:
        raise SystemExit("ARANGO_PASS not set")

    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db(db_name, username=user, password=password)
    if not db.has_collection("annotations"):
        raise SystemExit("annotations collection missing")
    ann_col = db.collection("annotations")
    if ann_col.count() < 1:
        raise SystemExit("no annotations present after insert")

    # Save artifact
    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "stage12_db_smoke.json").write_text(
        json.dumps({"ok": True, "annotations_count": ann_col.count()}, indent=2)
    )
    typer.echo("OK: Stage 12 annotations inserted and bridged")


if __name__ == "__main__":
    app()
