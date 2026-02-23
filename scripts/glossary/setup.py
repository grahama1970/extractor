#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
# ]
# ///
"""
Setup ArangoDB collections and ArangoSearch view for the datalake-wide glossary.

Database: memory (env var MEMORY_ARANGO_DB)

Collections:
  - glossary          — term documents (keyed by md5(term_lower))
  - glossary_edges    — edge collection linking terms to source documents

View:
  - glossary_search   — ArangoSearch view for BM25 + identity lookups
"""

from __future__ import annotations

import os

from arango import ArangoClient  # type: ignore


def get_memory_db():
    """Connect to the memory database."""
    url = os.getenv("ARANGO_URL", "http://127.0.0.1:8529")
    db_name = os.getenv("MEMORY_ARANGO_DB", os.getenv("ARANGO_DB", "memory"))
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASS", os.getenv("ARANGO_PASSWORD", ""))

    client = ArangoClient(hosts=url)
    sys_db = client.db("_system", username=user, password=password)
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    return client.db(db_name, username=user, password=password)


def ensure_glossary_collections(db):
    """Create glossary collection + edge collection if they don't exist."""
    if not db.has_collection("glossary"):
        db.create_collection("glossary")
    if not db.has_collection("glossary_edges"):
        db.create_collection("glossary_edges", edge=True)

    # Indexes for fast lookups
    try:
        col = db.collection("glossary")
        col.add_hash_index(["term_lower"], unique=True)  # type: ignore[attr-defined]
        col.add_hash_index(["category"])  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        edge_col = db.collection("glossary_edges")
        edge_col.add_hash_index(["_from"])  # type: ignore[attr-defined]
        edge_col.add_hash_index(["_to"])  # type: ignore[attr-defined]
        edge_col.add_hash_index(["type"])  # type: ignore[attr-defined]
    except Exception:
        pass


def ensure_glossary_search_view(db):
    """Create ArangoSearch view for glossary full-text search."""
    view_name = "glossary_search"
    try:
        existing = [v.get("name") for v in db.views()]  # type: ignore[attr-defined]
    except Exception:
        existing = []

    if view_name not in existing:
        db.create_arangosearch_view(
            view_name,
            properties={
                "links": {
                    "glossary": {
                        "includeAllFields": False,
                        "analyzers": ["text_en"],
                        "fields": {
                            "term": {"analyzers": ["text_en", "identity"]},
                            "term_lower": {"analyzers": ["identity"]},
                            "definitions[*].definition": {"analyzers": ["text_en"]},
                            "aliases": {"analyzers": ["identity"]},
                            "category": {"analyzers": ["identity"]},
                        },
                    }
                }
            },
        )


def setup():
    """Run full glossary setup."""
    db = get_memory_db()
    ensure_glossary_collections(db)
    ensure_glossary_search_view(db)
    print("ArangoDB glossary setup complete")


if __name__ == "__main__":
    setup()
