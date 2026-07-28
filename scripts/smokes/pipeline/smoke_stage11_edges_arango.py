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
    """Load ArangoDB connection config from environment, or None if password missing."""
    url = os.getenv("ARANGODB_URL", "http://localhost:8529")
    user = os.getenv("ARANGODB_USERNAME", os.getenv("ARANGODB_USER", "root"))
    pwd = os.getenv("ARANGODB_PASSWORD")
    if not pwd:
        return None
    return url, user, pwd


@app.command()
def main(db_name: str = typer.Option("lean4_test", "--db")):
    """Connect to ArangoDB and validate database existence."""
    cfg = _cfg()
    if not cfg:
        typer.secho("ARANGODB_* env not set; skipping", fg=typer.colors.YELLOW)
        raise typer.Exit(0)
    url, user, pwd = cfg
    client = ArangoClient(hosts=url)  # type: ignore
    sysdb = client.db("_system", username=user, password=pwd)
    if not sysdb.has_database(db_name):
        sysdb.create_database(db_name)
    db = client.db(db_name, username=user, password=pwd)

    # Prepare a simple edges JSON like from stage11_build_edges
    edges = {
        "nodes": {
            "sections": [{"key": "S1"}, {"key": "S2"}],
            "lemmas": [{"key": "Nat_add_comm", "name": "Nat.add_comm"}],
        },
        "edges": {
            "depends_on": [{"from": "S1", "to": "Nat_add_comm", "source": "used_lemmas"}],
            "contradicts": [{"a": "S1", "b": "S2", "reason": "opposite_polarity_same_prop"}],
            "refines": [],
        },
    }

    for col in ("sections", "lemmas"):
        if not db.has_collection(col):
            db.create_collection(col)
    for ecol in ("depends_on", "contradicts", "refines"):
        if not db.has_collection(ecol):
            db.create_collection(ecol, edge=True)
    sec = db.collection("sections")
    lem = db.collection("lemmas")
    for s in edges["nodes"]["sections"]:
        s2 = dict(s)
        s2["_key"] = s2.pop("key")
        sec.insert(s2, overwrite=True)
    for l in edges["nodes"]["lemmas"]:
        l2 = dict(l)
        l2["_key"] = l2.pop("key")
        lem.insert(l2, overwrite=True)
    dep = db.collection("depends_on")
    con = db.collection("contradicts")
    for e in edges["edges"]["depends_on"]:
        dep.insert(
            {
                "_from": f"sections/{e['from']}",
                "_to": f"lemmas/{e['to']}",
                "source": e.get("source"),
            }
        )
    for e in edges["edges"]["contradicts"]:
        con.insert(
            {"_from": f"sections/{e['a']}", "_to": f"sections/{e['b']}", "reason": e.get("reason")}
        )

    # Verify counts
    assert db.collection("depends_on").count() >= 1
    assert db.collection("contradicts").count() >= 1
    typer.secho("OK: Stage 11 Arango upsert smoke passed", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
