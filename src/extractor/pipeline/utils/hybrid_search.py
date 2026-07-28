from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, cast
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error

from .embeddings import ensure_embedder


def hybrid_search_annotations(
    DB: Any, available: bool, section_text: str, page_num: int, top_k: int = 5
) -> List[Dict[str, Any]]:
    """Hybrid search for annotations using ArangoDB and local embeddings.

    - Returns on-page annotations
    - Augments with graph-connected annotations (if edges collection exists)
    - Optionally ranks by cosine similarity using local embeddings
    """
    if not available or DB is None:
        logger.debug("ArangoDB not available, returning empty annotations.")
        return []
    try:
        env_ann = None
        env_edge = None
        try:
            import os

            env_ann = os.getenv("ARANGO_ANNOTATIONS_COLLECTION", "").strip()
            env_edge = os.getenv("ARANGO_EDGES_COLLECTION", "").strip()
        except Exception as exc:
            log_stage_error("hybrid_search.py", exc, {"context": "hybrid_search.py"})
            raise

        ann_coll_candidates = ([env_ann] if env_ann else []) + [
            "annotations",
            "pdf_annotations",
            "doc_annotations",
        ]
        edge_coll_candidates = ([env_edge] if env_edge else []) + [
            "annotation_edges",
            "edges",
            "relationships",
        ]
        ann_coll = next((c for c in ann_coll_candidates if DB.has_collection(c)), None)  # type: ignore[attr-defined]
        edge_coll = next((c for c in edge_coll_candidates if DB.has_collection(c)), None)  # type: ignore[attr-defined]
        if not ann_coll:
            logger.warning("No annotations collection found in ArangoDB.")
            return []

        aql_on_page = f"""
        FOR a IN {ann_coll}
          FILTER a.page == @page
          LIMIT 200
          RETURN a
        """
        on_page = DB.aql.execute(aql_on_page, bind_vars={"page": int(page_num)})  # type: ignore[attr-defined]
        on_page_list = list(cast(Any, on_page))

        connected_list: List[Dict[str, Any]] = []
        weights_map: Dict[str, float] = {}
        if edge_coll and on_page_list:
            try:

                def _anchor_id(a: Dict[str, Any]) -> Optional[str]:
                    """Extracts an anchor ID from a dict using ordered key lookups."""
                    _id = a.get("_id")
                    if isinstance(_id, str) and _id:
                        return _id
                    aid = a.get("id") or a.get("_key")
                    if aid:
                        return f"{ann_coll}/{aid}"
                    return None

                a_keys = [k for k in (_anchor_id(a) for a in on_page_list) if k]
                if a_keys:
                    aql_w = f"""
                    FOR anchor IN DOCUMENT(@keys)
                      FOR v, e IN 1..2 ANY anchor {edge_coll}
                        FILTER IS_SAME_COLLECTION(@annColl, v)
                        COLLECT vid = v._id AGGREGATE w = MAX(e.weight)
                        RETURN {{ vid: vid, w: w }}
                    """
                    cur = DB.aql.execute(aql_w, bind_vars={"keys": a_keys, "annColl": ann_coll})
                    wrows = list(cast(Any, cur))
                    for r in wrows:
                        vid = r.get("vid")
                        w = r.get("w")
                        if isinstance(vid, str) and isinstance(w, (int, float)):
                            weights_map[vid] = float(w)
                    if weights_map:
                        vids = list(weights_map.keys())
                        aql_docs = """
                        FOR v IN DOCUMENT(@ids)
                          RETURN v
                        """
                        dc = DB.aql.execute(aql_docs, bind_vars={"ids": vids})
                        connected_list = list(cast(Any, dc))
            except Exception as exc:
                log_stage_error("hybrid_search.py", exc, {"context": "hybrid_search.py"})
                raise

        combined: Dict[str, Dict[str, Any]] = {}

        def _k(x: Dict[str, Any]) -> str:
            """Return an identifier from dict, or generate a stable one from content."""
            return str(
                x.get("_id") or x.get("_key") or x.get("id") or hash(json.dumps(x, sort_keys=True))
            )

        for a in on_page_list:
            combined[_k(a)] = a
        for a in connected_list:
            k = _k(a)
            if k not in combined:
                combined[k] = a

        if weights_map:
            for a in on_page_list:
                _id = a.get("_id") or (f"{ann_coll}/{a.get('id')}" if a.get("id") else None)
                if isinstance(_id, str) and _id in weights_map:
                    a["_rel_weight"] = weights_map[_id]
        results = list(combined.values())

        try:
            if results and ensure_embedder() is not None and section_text:
                embedder = ensure_embedder()
                q_vec = embedder.encode(section_text, normalize_embeddings=True)
                ann_texts = []
                for a in results:
                    parts = []
                    for field in ("text", "content", "summary", "title"):
                        v = a.get(field)
                        if isinstance(v, str) and v.strip():
                            parts.append(v.strip())
                    ann_texts.append(" ".join(parts) or (a.get("type") or ""))
                a_vecs = embedder.encode(ann_texts, normalize_embeddings=True)
                import numpy as _np

                sims = _np.dot(a_vecs, q_vec)
                for i, a in enumerate(results):
                    a["similarity"] = float(sims[i])
                results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
                if top_k and len(results) > top_k:
                    results = results[:top_k]
        except Exception as exc:
            log_stage_error("hybrid_search.py", exc, {"context": "hybrid_search.py"})
            raise
        return results
    except Exception as exc:
        log_stage_error("hybrid_search.py", exc, {"context": "hybrid_search.py"})
        raise
