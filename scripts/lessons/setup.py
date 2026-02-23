#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
# ]
# ///

from __future__ import annotations
from scripts.lessons.arango_client import get_db


def ensure_collections_and_view():
    db = get_db()
    # Collections
    if not db.has_collection("lessons"):
        db.create_collection("lessons")
    if not db.has_collection("incidents"):
        db.create_collection("incidents")
    # Graph edges between lessons
    if not db.has_collection("lesson_edges"):
        db.create_collection("lesson_edges", edge=True)
    # Rejected pairs cache
    if not db.has_collection("rejected_pairs"):
        db.create_collection("rejected_pairs")
    # ArangoSearch view
    view_name = "lessons_search"
    try:
        existing = [v.get("name") for v in db.views()]  # type: ignore[attr-defined]
    except Exception:
        existing = []
    if view_name not in existing:
        db.create_arangosearch_view(
            view_name,
            properties={
                "links": {
                    "lessons": {
                        "includeAllFields": False,
                        "analyzers": ["text_en"],
                        "fields": {
                            "title": {"analyzers": ["text_en"]},
                            "problem": {"analyzers": ["text_en"]},
                            "playbook": {"analyzers": ["text_en"]},
                            "tags": {"analyzers": ["text_en", "identity"]},
                            "keywords": {"analyzers": ["text_en", "identity"]},
                            "scope": {"analyzers": ["identity"]},
                        },
                    }
                }
            },
        )

    # Best-effort indexes for edges
    try:
        col = db.collection("lesson_edges")
        try:
            col.add_hash_index(["_from"])  # type: ignore[attr-defined]
            col.add_hash_index(["_to"])  # type: ignore[attr-defined]
            col.add_hash_index(["pair_id"])  # type: ignore[attr-defined]
            col.add_hash_index(["type", "approved", "status"])  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass


print("ArangoDB lessons setup complete")


if __name__ == "__main__":
    ensure_collections_and_view()
