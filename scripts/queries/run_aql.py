#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=7.6.0",
# ]
# ///
from __future__ import annotations

import json
import os
from pathlib import Path
import typer

from arango import ArangoClient  # type: ignore

app = typer.Typer(add_completion=False)


def _conn():
    url = os.getenv("ARANGODB_URL", "http://localhost:8529")
    user = os.getenv("ARANGODB_USERNAME", os.getenv("ARANGODB_USER", "root"))
    pwd = os.getenv("ARANGODB_PASSWORD")
    if not pwd:
        typer.secho("Set ARANGODB_PASSWORD to run queries", fg=typer.colors.RED)
        raise typer.Exit(2)
    return url, user, pwd


@app.command()
def main(
    database: str = typer.Option(..., "--db", help="Database name"),
    query_file: Path = typer.Argument(..., exists=True, readable=True),
    params: str = typer.Option("{}", "--params", help="JSON string of bind vars"),
    pretty: bool = typer.Option(True, "--pretty/--raw"),
):
    url, user, pwd = _conn()
    client = ArangoClient(hosts=url)
    db = client.db(database, username=user, password=pwd)
    q = query_file.read_text()
    try:
        bind = json.loads(params) if params else {}
    except Exception:
        bind = {}
    cursor = db.aql.execute(q, bind_vars=bind)
    out = list(cursor)
    if pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    app()
