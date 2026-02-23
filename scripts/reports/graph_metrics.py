#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-arango>=7.6.0",
# ]
# ///
from __future__ import annotations
import json
import os
from typing import Dict
import typer
from arango import ArangoClient  # type: ignore

app = typer.Typer(add_completion=False)


def _conn():
    url = os.getenv("ARANGODB_URL", "http://localhost:8529")
    user = os.getenv("ARANGODB_USERNAME", os.getenv("ARANGODB_USER", "root"))
    pwd = os.getenv("ARANGODB_PASSWORD")
    if not pwd:
        typer.secho("Set ARANGODB_PASSWORD", fg=typer.colors.RED)
        raise typer.Exit(2)
    return url, user, pwd


@app.command()
def main(db: str = typer.Option("lean4_prod", "--db")):
    url, user, pwd = _conn()
    client = ArangoClient(hosts=url)
    adb = client.db(db, username=user, password=pwd)
    coll_counts: Dict[str, int] = {}
    for name in (
        "sections",
        "lemmas",
        "theorems",
        "depends_on",
        "contradicts",
        "refines",
        "similar_knn",
    ):
        coll_counts[name] = adb.collection(name).count() if adb.has_collection(name) else 0

    # Simple graph coverage metrics
    q_dep_cov = """
    LET total = LENGTH(sections)
    LET with_dep = LENGTH(FOR s IN sections FILTER LENGTH(FOR e IN depends_on FILTER e._from == s._id LIMIT 1 RETURN 1) > 0 RETURN 1)
    RETURN { total, with_dep, coverage: with_dep / MAX(total, 1) }
    """
    dep_cov = (
        list(adb.aql.execute(q_dep_cov))[0]
        if adb.has_collection("sections")
        else {"total": 0, "with_dep": 0, "coverage": 0}
    )

    q_con_pairs = """
    RETURN LENGTH(
      FOR s1 IN sections FOR s2 IN sections
        FILTER s1._key < s2._key && s1.normalized_prop == s2.normalized_prop && s1.polarity != s2.polarity
        RETURN 1)
    """
    con_pairs = list(adb.aql.execute(q_con_pairs))[0] if adb.has_collection("sections") else 0

    # KNN average degree (simple)
    q_knn_deg = """
    LET deg = (
      FOR s IN sections
        RETURN LENGTH(FOR e IN similar_knn FILTER e._from == s._id RETURN 1)
    )
    RETURN { avg: AVERAGE(deg), max: MAX(deg) }
    """
    knn_deg = (
        list(adb.aql.execute(q_knn_deg))[0]
        if adb.has_collection("similar_knn")
        else {"avg": 0, "max": 0}
    )

    report = {
        "collections": coll_counts,
        "depends_on_coverage": dep_cov,
        "contradiction_pairs": con_pairs,
        "knn_degree": knn_deg,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
