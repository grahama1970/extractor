#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///
"""
Glossary Recall CLI — Look up terms from the datalake-wide glossary.

Usage:
  python -m scripts.glossary.recall --term "REQ"
  python -m scripts.glossary.recall --term "electromagnetic" --fuzzy
  python -m scripts.glossary.recall --term "REQ" --json
"""

from __future__ import annotations

import hashlib
import json
import os

import typer
from arango import ArangoClient  # type: ignore

app = typer.Typer(add_completion=False)


def get_memory_db():
    """Connect to the memory database."""
    url = os.getenv("ARANGO_URL", "http://127.0.0.1:8529")
    db_name = os.getenv("MEMORY_ARANGO_DB", os.getenv("ARANGO_DB", "memory"))
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASS", os.getenv("ARANGO_PASSWORD", ""))

    client = ArangoClient(hosts=url)
    return client.db(db_name, username=user, password=password)


def recall_definition(term: str, db=None, fuzzy: bool = False) -> dict:
    """
    Look up a term in the glossary collection.

    Fast path: exact key lookup via md5(term.lower()).
    Fallback: BM25 search on glossary_search view (when fuzzy=True).

    Returns {"term", "definitions", "sources", "found"}.
    """
    if db is None:
        db = get_memory_db()

    # Fast path: exact lookup
    term_key = hashlib.md5(term.lower().encode()).hexdigest()
    try:
        col = db.collection("glossary")
        doc = col.get(term_key)
        if doc:
            sources = list({d["source_filename"] for d in doc.get("definitions", [])})
            return {
                "term": doc["term"],
                "definitions": doc["definitions"],
                "aliases": doc.get("aliases", []),
                "category": doc.get("category", ""),
                "sources": sources,
                "found": True,
            }
    except Exception:
        pass

    if not fuzzy:
        return {"term": term, "definitions": [], "sources": [], "found": False}

    # Fuzzy: BM25 search on glossary_search view
    aql = """
    FOR d IN glossary_search
      SEARCH ANALYZER(
        d.term IN TOKENS(@q, 'text_en') OR
        d.definitions[*].definition ANY IN TOKENS(@q, 'text_en')
      , 'text_en')
      SORT BM25(d) DESC
      LIMIT @k
      RETURN d
    """
    try:
        cur = db.aql.execute(aql, bind_vars={"q": term, "k": 5})
        results = list(cur)
        if results:
            return {
                "term": term,
                "definitions": results,
                "sources": [],
                "found": True,
                "fuzzy": True,
            }
    except Exception:
        pass

    return {"term": term, "definitions": [], "sources": [], "found": False}


@app.command()
def recall(
    term: str = typer.Option(..., help="Term to look up"),
    fuzzy: bool = typer.Option(False, help="Enable BM25 fuzzy search"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Look up a glossary term."""
    result = recall_definition(term, fuzzy=fuzzy)

    if json_out:
        print(json.dumps(result, ensure_ascii=False, default=str))
        raise typer.Exit(0)

    if not result["found"]:
        typer.echo(f"Term '{term}' not found in glossary.")
        raise typer.Exit(1)

    typer.echo(f"Term: {result['term']}")
    if result.get("category"):
        typer.echo(f"Category: {result['category']}")
    for i, d in enumerate(result["definitions"], 1):
        if isinstance(d, dict) and "definition" in d:
            src = d.get("source_filename", "unknown")
            typer.echo(f"  {i}. {d['definition']}  [source: {src}]")
        elif isinstance(d, dict) and "term" in d:
            # Fuzzy result — full doc
            typer.echo(f"  {i}. {d['term']}: {d.get('definitions', [{}])[0].get('definition', '')[:120]}")


if __name__ == "__main__":
    app()
