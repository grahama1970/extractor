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
    add_completion=False, help="Smoke: Stage 10 export to Arango with fast embeddings"
)


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline_db_smoke"), "-o")) -> None:
    load_dotenv(find_dotenv() or None)
    # Prepare minimal Stage 07/09 payloads
    pdf_name = "BHT_CV32A65X_marked.pdf"
    reflow = {
        "reflowed_sections": [
            {
                "id": "s1",
                "title": "Intro",
                "level": 1,
                "reflow_status": "success",
                "reflowed_text": "Hello world.",
                "page_start": 0,
                "page_end": 0,
                "bbox": [0, 0, 100, 100],
                "tables": [],
                "figures": [],
            }
        ],
        "source_files": {"sections": pdf_name},
    }
    summaries = {"summaries": []}

    tmp = results / "_smokes_tmp10_db"
    tmp.mkdir(parents=True, exist_ok=True)
    s07 = tmp / "07_reflowed.json"
    s09 = tmp / "09_summaries.json"
    s07.write_text(json.dumps(reflow))
    s09.write_text(json.dumps(summaries))

    # Run Stage 10 (export path)
    spec = importlib.util.spec_from_file_location(
        "stage10", "src/extractor/pipeline/steps/10_arangodb_exporter.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 10 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    mod.run(
        reflowed_json=s07,
        summaries_json=s09,
        output_dir=results,
        collection_name="pdf_objects",
        skip_export=False,
        skip_embeddings=False,
        fast_embeddings=True,
    )

    # Confirmation JSON and DB query
    out = results / "10_arangodb_exporter" / "json_output" / "10_export_confirmation.json"
    if not out.exists():
        raise SystemExit("export confirmation JSON missing")
    data = json.loads(out.read_text())
    if data.get("errors") not in (0, None):
        raise SystemExit(f"export errors: {data.get('errors')}")

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
    if not db.has_collection("pdf_objects"):
        raise SystemExit("missing pdf_objects collection after export")
    col = db.collection("pdf_objects")
    count = col.count()
    # Should have at least one document
    if count < 1:
        raise SystemExit("no documents in pdf_objects after export")

    # Write a small artifact
    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "stage10_db_smoke.json").write_text(
        json.dumps({"ok": True, "pdf_objects_count": count}, indent=2)
    )
    typer.echo("OK: Stage 10 exported to Arango (fast embeddings)")


if __name__ == "__main__":
    app()
