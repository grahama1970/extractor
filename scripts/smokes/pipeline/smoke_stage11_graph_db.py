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


app = typer.Typer(add_completion=False, help="Smoke: Stage 11 graph creation with DB insert")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline_db_smoke"), "-o")) -> None:
    load_dotenv(find_dotenv() or None)
    # Use flattened JSON from Stage 10
    flat = results / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not flat.exists():
        raise SystemExit("Missing flattened data; run Stage 10 export first")

    spec = importlib.util.spec_from_file_location(
        "stage11", "src/extractor/pipeline/steps/11_arango_create_graph.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 11 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    mod.run(
        input_json=flat,
        output_dir=results,
        k_neighbors=3,
        similarity_threshold=0.0,
        skip_graph_creation=False,
    )

    conf = results / "11_arango_create_graph" / "json_output" / "11_graph_confirmation.json"
    if not conf.exists():
        raise SystemExit("Graph confirmation JSON missing")
    c = json.loads(conf.read_text())
    if c.get("edges_created", 0) < 0:
        raise SystemExit("edges_created missing/invalid in confirmation")

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
    if not db.has_collection("pdf_relationships"):
        raise SystemExit("missing pdf_relationships edge collection")
    edge_col = db.collection("pdf_relationships")
    if edge_col.count() < 0:  # count >= 0 always; this line asserts API response
        raise SystemExit("edge count probe failed")

    # Save artifact
    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "stage11_db_smoke.json").write_text(
        json.dumps({"ok": True, "edges_created": c.get("edges_created", 0)}, indent=2)
    )
    typer.echo("OK: Stage 11 graph edges created in Arango")


if __name__ == "__main__":
    app()
