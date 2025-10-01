#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-arango>=7.6.0",
# ]
# ///
from __future__ import annotations
import os
import typer
from arango import ArangoClient  # type: ignore

app = typer.Typer(add_completion=False)


def _cfg():
    url = os.getenv("ARANGODB_URL", "http://localhost:8529")
    user = os.getenv("ARANGODB_USERNAME", os.getenv("ARANGODB_USER", "root"))
    pwd = os.getenv("ARANGODB_PASSWORD")
    if not pwd:
        typer.secho("Set ARANGODB_PASSWORD in environment", fg=typer.colors.RED)
        raise typer.Exit(2)
    return url, user, pwd


@app.command()
def main(db: str = typer.Argument("lean4_test")):
    url, user, pwd = _cfg()
    client = ArangoClient(hosts=url)
    sysdb = client.db("_system", username=user, password=pwd)
    if not sysdb.has_database(db):
        sysdb.create_database(db)
    adb = client.db(db, username=user, password=pwd)

    # Create vertex and edge collections if missing
    for col in ("sections", "theorems", "lemmas"):
        if not adb.has_collection(col):
            adb.create_collection(col)
    for ecol in ("depends_on", "contradicts", "refines", "similar_knn"):
        if not adb.has_collection(ecol):
            adb.create_collection(ecol, edge=True)

    # Create a simple named graph if missing
    gname = "lean4_g"
    if not adb.has_graph(gname):
        adb.create_graph(
            gname,
            edge_definitions=[
                {"edge_collection": "depends_on", "from_vertex_collections": ["sections", "theorems"], "to_vertex_collections": ["lemmas"]},
                {"edge_collection": "contradicts", "from_vertex_collections": ["sections"], "to_vertex_collections": ["sections"]},
                {"edge_collection": "refines", "from_vertex_collections": ["sections"], "to_vertex_collections": ["sections"]},
                {"edge_collection": "similar_knn", "from_vertex_collections": ["sections", "theorems"], "to_vertex_collections": ["sections", "theorems"]},
            ],
        )

    # Create ArangoSearch view for BM25 on sections.text
    if not adb.has_view("v_sections"):
        adb.create_view(
            name="v_sections",
            view_type="arangosearch",
            properties={
                "links": {
                    "sections": {
                        "fields": {
                            "text": {"analyzers": ["text_en"]},
                            "normalized_prop": {"analyzers": ["text_en"]},
                        }
                    }
                }
            },
        )
    typer.secho(f"OK: ArangoDB bootstrap complete for db={db}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()

