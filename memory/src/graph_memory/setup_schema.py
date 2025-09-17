from __future__ import annotations
from .arango_client import get_db

def ensure_collections_and_view():
    db = get_db()
    if not db.has_collection("lessons"):
        db.create_collection("lessons")
    if not db.has_collection("incidents"):
        db.create_collection("incidents")
    if not db.has_collection("lesson_edges"):
        db.create_collection("lesson_edges", edge=True)
    if not db.has_collection("rejected_pairs"):
        db.create_collection("rejected_pairs")
    view_name = "lessons_search"
    try:
        existing = [v.get("name") for v in db.views()]
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
    # indexes (best-effort)
    try:
        col = db.collection("lesson_edges")
        try:
            col.add_index({"type":"hash","fields":["_from"]})
            col.add_index({"type":"hash","fields":["_to"]})
            col.add_index({"type":"hash","fields":["pair_id"]})
            col.add_index({"type":"hash","fields":["type","approved","status"]})
        except Exception:
            pass
    except Exception:
        pass
