#!/usr/bin/env python3
from __future__ import annotations
"""
Pipeline Stage 11: ArangoDB Graph Creation with FAISS

Purpose: Create weighted graph relationships between PDF objects stored in ArangoDB
using FAISS for efficient similarity search and section hierarchy for structural weighting.

This stage runs AFTER documents are loaded into ArangoDB and creates edges based on:
1. Semantic similarity (using FAISS for efficient k-NN search)
2. Section hierarchy relationships
3. Combined weighted scores
"""

import os  # noqa: E402
import sys  # noqa: E402
import json  # noqa: E402
import asyncio  # noqa: E402
import math  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Dict, List, Any, Optional, cast, Tuple  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import numpy as np  # noqa: E402
from numpy.typing import NDArray  # noqa: E402

# Third-party
from loguru import logger  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.progress import Progress, SpinnerColumn, TextColumn  # noqa: E402
from extractor.pipeline.utils.diagnostics import get_run_id  # noqa: E402,F401
from extractor.pipeline.utils.scillm_router import get_text_router  # noqa: E402
from extractor.pipeline.utils.debug_utils import log_timing  # noqa: E402

try:
    from arango import ArangoClient
    from arango.exceptions import ArangoError
    from arango.database import StandardDatabase
except Exception:  # allow import without python-arango for non-DB debug paths
    ArangoClient = None  # type: ignore

    class ArangoError(Exception): ...  # type: ignore

    class StandardDatabase: ...  # type: ignore


# Do not load .env at import time; caller/debug harness should load env.
# No litellm cache here; scillm calls use Chutes x-api-key path


logger.remove()
logger.add(sys.stderr, level="INFO")

console = Console()

# Optional FAISS dependency with NumPy fallback
try:
    import faiss  # type: ignore

    _HAVE_FAISS = True
except Exception:
    faiss = None  # type: ignore
    _HAVE_FAISS = False

# (duplicate config block removed)
# Stage 11 configuration via environment (toggleable)
GRAPH_K = int(os.getenv("GRAPH_K_NEIGHBORS", 10))
GRAPH_SIM_THRESHOLD = float(os.getenv("GRAPH_SIMILARITY_THRESHOLD", 0.55))
GRAPH_SEMANTIC_WEIGHT = float(os.getenv("GRAPH_SEMANTIC_WEIGHT", 0.7))
GRAPH_HIERARCHY_WEIGHT = float(os.getenv("GRAPH_HIERARCHY_WEIGHT", 0.3))
GRAPH_EDGE_COLLECTION = os.getenv("GRAPH_EDGE_COLLECTION", "pdf_relationships")
GRAPH_GRAPH_NAME = os.getenv("GRAPH_NAME", "pdf_knowledge_graph")
GRAPH_VERTEX_COLLECTION = os.getenv("GRAPH_VERTEX_COLLECTION", "pdf_objects")
GRAPH_ENABLE_RATIONALES = os.getenv("GRAPH_ENABLE_RATIONALES", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
# Prefer the project's default LLM for rationales unless explicitly overridden
GRAPH_RATIONALE_MODEL = (
    os.getenv("GRAPH_RATIONALE_MODEL")
    or os.getenv("CHUTES_TEXT_MODEL")
    or "gemini/gemini-2.5-flash"
)
GRAPH_RATIONALE_CONCURRENCY = int(os.getenv("GRAPH_RATIONALE_CONCURRENCY", 8))
GRAPH_RATIONALE_MAX_TOKENS = int(os.getenv("GRAPH_RATIONALE_MAX_TOKENS", 256))
GRAPH_RELATIONSHIPS_ENABLED = os.getenv("GRAPH_RELATIONSHIPS_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)

# --- Simple Edge Schema/Invariants (v1) ---
EDGE_SCHEMA_VERSION = "edge_v1"
EDGE_ALLOWED_TYPES = {"semantic_similarity", "proves", "conflicts_with", "contradicts", "duplicates", "supersedes", "refers_to"}

def _validate_edges(edges: list[dict]) -> dict:
    violations: list[dict] = []
    counts_by_type: dict[str,int] = {}
    for e in edges:
        try:
            rtype = str(e.get("relationship_type", ""))
            counts_by_type[rtype] = counts_by_type.get(rtype, 0) + 1
            if rtype not in EDGE_ALLOWED_TYPES:
                violations.append({"edge": e, "reason": "invalid_relationship_type"})
            _from = e.get("_from")
            _to = e.get("_to")
            if not (isinstance(_from, str) and isinstance(_to, str)):
                violations.append({"edge": e, "reason": "from_to_not_str"})
            if not (str(_from).startswith("pdf_objects/") and str(_to).startswith("pdf_objects/")):
                violations.append({"edge": e, "reason": "bad_vertex_prefix"})
            # Self-edge only allowed for 'proves'
            if _from == _to and rtype != "proves":
                violations.append({"edge": e, "reason": "self_edge_not_allowed"})
            # Numeric bounds (best-effort)
            w = float(e.get("weight", 0.0))
            if not (0.0 <= w <= 1.0):
                violations.append({"edge": e, "reason": "weight_out_of_range"})
            if rtype == "semantic_similarity":
                s = float(e.get("semantic_score", 0.0))
                if not (0.0 <= s <= 1.0):
                    violations.append({"edge": e, "reason": "score_out_of_range"})
        except Exception:
            violations.append({"edge": e, "reason": "exception_validating"})
    return {
        "schema_version": EDGE_SCHEMA_VERSION,
        "total_edges": len(edges),
        "counts_by_type": counts_by_type,
        "violations_count": len(violations),
        "violations_sample": violations[:10],
    }

def _save_summary(json_output_dir: Path, summary: dict) -> None:
    try:
        out = json_output_dir / "11_graph_summary.json"
        out.write_text(json.dumps(summary, indent=2))
    except Exception:
        pass

def _proves_edges_from_docs(documents: list[dict], proved_section_ids: set[str]) -> list[dict]:
    edges: list[dict] = []
    for doc in documents:
        sid = doc.get("section_id")
        if sid and sid in proved_section_ids:
            try:
                edges.append({
                    "_from": f"pdf_objects/{doc['_key']}",
                    "_to": f"pdf_objects/{doc['_key']}",
                    "relationship_type": "proves",
                    "semantic_score": 1.0,
                    "hierarchy_distance": 0.0,
                    "weight": 1.0,
                    "source_pdf": doc.get("source_pdf"),
                    "discovery_method": "lean4_stage08",
                    "knn_rank": 0,
                    "neighbor_index": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                continue
    return edges


def _conflict_edges_from_docs(documents: list[dict], tolerance_ratio: float = 0.1) -> list[dict]:
    """Create 'conflicts_with' edges when normalized units disagree beyond tolerance.

    Buckets by (doc_id, section_id, dimensionality). Creates one edge between
    min and max when delta exceeds tolerance_ratio.
    """
    edges: list[dict] = []
    buckets: dict[tuple[str,str,str], list[tuple[str,float]]] = {}
    for d in documents:
        key = d.get("_key")
        doc_id = d.get("doc_id")
        sec = d.get("section_id")
        for u in d.get("units", []) or []:
            dim = str(u.get("dim"))
            val = u.get("value_si")
            if key and doc_id and sec and isinstance(val, (int, float)) and dim:
                buckets.setdefault((doc_id, sec, dim), []).append((key, float(val)))
    for (doc_id, sec, dim), items in buckets.items():
        if len(items) < 2:
            continue
        items_sorted = sorted(items, key=lambda t: t[1])
        kmin, vmin = items_sorted[0]
        kmax, vmax = items_sorted[-1]
        if vmax <= 0:
            continue
        if (vmax - vmin) / max(vmax, 1e-9) > tolerance_ratio:
            edges.append({
                "_from": f"pdf_objects/{kmax}",
                "_to": f"pdf_objects/{kmin}",
                "relationship_type": "conflicts_with",
                "semantic_score": 0.0,
                "hierarchy_distance": 0.0,
                "weight": 1.0,
                "source_pdf": None,
                "discovery_method": "units_conflict_v1",
                "dimensionality": dim,
                "delta_si": float(vmax - vmin),
                "tolerance_ratio": tolerance_ratio,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    return edges


def _duplicates_edges_from_docs(documents: list[dict]) -> list[dict]:
    """Create 'duplicates' edges for identical text within the same doc_id/section_id."""
    edges: list[dict] = []
    buckets: dict[tuple[str, str], dict[str, str]] = {}
    for d in documents:
        doc_id = d.get("doc_id")
        sec = d.get("section_id")
        key = d.get("_key")
        txt = (d.get("text_content") or "").strip().lower()
        if not (doc_id and sec and key and txt):
            continue
        bkey = (str(doc_id), str(sec))
        seen = buckets.setdefault(bkey, {})
        if txt in seen:
            kprev = seen[txt]
            edges.append({
                "_from": f"pdf_objects/{key}",
                "_to": f"pdf_objects/{kprev}",
                "relationship_type": "duplicates",
                "semantic_score": 1.0,
                "hierarchy_distance": 0.0,
                "weight": 1.0,
                "discovery_method": "text_eq_v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            seen[txt] = key
    return edges


def _contradicts_edges_from_docs(documents: list[dict]) -> list[dict]:
    """Create 'contradicts' edges when two blocks in the same document assert opposite polarity over the same lean4_norm.

    Requirements:
      - doc_id matches
      - rtm.lean4_norm identical (best-effort string equality)
      - rtm.lean4_polarity differs ("assert" vs "deny")
    """
    edges: list[dict] = []
    buckets: dict[tuple[str, str], list[dict]] = {}
    for d in documents:
        rtm = d.get("rtm") if isinstance(d.get("rtm"), dict) else None
        if not rtm:
            continue
        norm = rtm.get("lean4_norm")
        pol = rtm.get("lean4_polarity")
        doc_id = d.get("doc_id")
        key = d.get("_key")
        if not (doc_id and key and isinstance(norm, str) and isinstance(pol, str)):
            continue
        buckets.setdefault((str(doc_id), norm.strip()), []).append(d)
    for (_doc, norm), items in buckets.items():
        # find one assert and one deny
        a = [x for x in items if (x.get("rtm") or {}).get("lean4_polarity") == "assert"]
        dny = [x for x in items if (x.get("rtm") or {}).get("lean4_polarity") == "deny"]
        if not a or not dny:
            continue
        # Create a single edge between first assert and first deny
        try:
            ka = a[0]["_key"]
            kd = dny[0]["_key"]
            edges.append({
                "_from": f"pdf_objects/{ka}",
                "_to": f"pdf_objects/{kd}",
                "relationship_type": "contradicts",
                "semantic_score": 0.0,
                "hierarchy_distance": 0.0,
                "weight": 1.0,
                "discovery_method": "lean4_norm_polarity_v1",
                "normalized_prop": norm,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return edges


def _supersedes_edges_from_docs(documents: list[dict]) -> list[dict]:
    """Create 'supersedes' edges between revisions of the same doc/section.

    Expects objects to carry 'doc_id', 'section_id', and optional 'revision_id'.
    Edges point from newer (max lexicographic revision_id) to older.
    """
    edges: list[dict] = []
    buckets: dict[tuple[str, str], list[dict]] = {}
    for d in documents:
        doc_id = d.get("doc_id")
        sec = d.get("section_id")
        rev = d.get("revision_id")
        if not (doc_id and sec and rev and d.get("_key")):
            continue
        buckets.setdefault((str(doc_id), str(sec)), []).append(d)
    for (doc_id, sec), items in buckets.items():
        if len(items) < 2:
            continue
        items_sorted = sorted(items, key=lambda x: str(x.get("revision_id")))
        older = items_sorted[0]
        newer = items_sorted[-1]
        if str(older.get("revision_id")) == str(newer.get("revision_id")):
            continue
        edges.append({
            "_from": f"pdf_objects/{newer['_key']}",
            "_to": f"pdf_objects/{older['_key']}",
            "relationship_type": "supersedes",
            "semantic_score": 0.0,
            "hierarchy_distance": 0.0,
            "weight": 1.0,
            "discovery_method": "revision_supersedes_v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return edges


def _refers_to_edges_from_docs(documents: list[dict]) -> list[dict]:
    """Create 'refers_to' edges for simple inline references.

    Heuristics:
    - Detect tokens like 'see section <ID>' or 'See <ID>' where <ID> matches a known section_id.
    - Link from the referencing object to the first object found in the referenced section.
    """
    import re
    edges: list[dict] = []
    # Build map to first object key per section
    first_key_by_sec: dict[str, str] = {}
    for d in documents:
        sec = d.get("section_id")
        key = d.get("_key")
        if sec and key and sec not in first_key_by_sec:
            first_key_by_sec[str(sec)] = str(key)
    known_secs = set(first_key_by_sec.keys())
    if not known_secs:
        return edges
    # Build regex that searches for any known section id explicitly
    # Also detect generic numeric refs like 3.1 that exist in known_secs
    pattern = re.compile(r"\b(?:see\s+(?:section\s+)?)?(?P<sid>[A-Za-z0-9_.-]+)\b", re.IGNORECASE)
    for d in documents:
        key = d.get("_key")
        txt = (d.get("text_content") or "")
        if not (key and txt):
            continue
        for m in pattern.finditer(txt):
            sid = m.group("sid")
            if sid in known_secs and first_key_by_sec.get(sid):
                target_key = first_key_by_sec[sid]
                if target_key == key:
                    continue
                edges.append({
                    "_from": f"pdf_objects/{key}",
                    "_to": f"pdf_objects/{target_key}",
                    "relationship_type": "refers_to",
                    "semantic_score": 0.0,
                    "hierarchy_distance": 0.0,
                    "weight": 1.0,
                    "discovery_method": "refers_to_v1",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
    return edges


def ensure_graph_and_edge_collection(
    db: StandardDatabase,
    graph_name: str = "pdf_knowledge_graph",
    edge_collection: str = "pdf_relationships",
    vertex_collection: str = "pdf_objects",
) -> str:
    """Ensure graph and edge collection exist in ArangoDB.

    Returns:
        Name of the edge collection
    """
    try:
        # Create edge collection if it doesn't exist
        if not db.has_collection(edge_collection):
            db.create_collection(edge_collection, edge=True)
            logger.info(f"Created edge collection: {edge_collection}")

        # Create graph if it doesn't exist
        if not db.has_graph(graph_name):
            db.create_graph(
                name=graph_name,
                edge_definitions=[
                    {
                        "edge_collection": edge_collection,
                        "from_vertex_collections": [vertex_collection],
                        "to_vertex_collections": [vertex_collection],
                    }
                ],
            )
            logger.info(f"Created graph: {graph_name}")

        # Add indexes for efficient queries
        edge_col = db.collection(edge_collection)
        edge_col.add_persistent_index(fields=["relationship_type"], unique=False)
        edge_col.add_persistent_index(fields=["weight"], unique=False)
        edge_col.add_persistent_index(fields=["source_pdf"], unique=False)

        return edge_collection

    except ArangoError as e:
        logger.error(f"Failed to set up graph structures: {e}")
        sys.exit(1)


def build_faiss_index(embeddings: NDArray[np.float32]) -> Tuple[str, Any]:
    """Build FAISS index with normalized embeddings for cosine similarity.

    Args:
        embeddings: Array of embeddings

    Returns:
        FAISS index ready for search
    """
    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    # Use inner product (equivalent to cosine similarity after normalization)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(cast(Any, embeddings))  # type: ignore[arg-type]

    logger.info(f"Built FAISS index with {index.ntotal} vectors")
    return ("faiss", index)


def calculate_hierarchy_distance(doc1: Dict[str, Any], doc2: Dict[str, Any]) -> float:
    """Calculate normalized hierarchical distance between two documents.

    Returns:
        Normalized distance between 0 and 1
    """
    # If not from same PDF, max distance
    if doc1.get("source_pdf") != doc2.get("source_pdf"):
        return 1.0

    # Calculate section level difference
    level1 = doc1.get("section_level", 0)
    level2 = doc2.get("section_level", 0)
    _level_diff = abs(level1 - level2)

    # Check if in same section hierarchy
    breadcrumbs1 = doc1.get("section_breadcrumbs", [])
    breadcrumbs2 = doc2.get("section_breadcrumbs", [])

    # Find common ancestor depth
    common_depth = 0
    for i, (b1, b2) in enumerate(zip(breadcrumbs1, breadcrumbs2)):
        if b1 == b2:
            common_depth = i + 1
        else:
            break

    # Calculate tree distance
    tree_distance = (len(breadcrumbs1) - common_depth) + (len(breadcrumbs2) - common_depth)

    # Normalize (assuming max depth of 10)
    max_possible_distance = 10
    normalized_distance = min(tree_distance / max_possible_distance, 1.0)

    return normalized_distance


def calculate_combined_weight(
    semantic_similarity: float,
    hierarchy_distance: float,
    semantic_weight: float = 0.7,
    hierarchy_weight: float = 0.3,
) -> float:
    """Calculate combined weight using semantic similarity and hierarchy.

    Args:
        semantic_similarity: FAISS similarity score (0-1)
        hierarchy_distance: Normalized hierarchy distance (0-1)
        semantic_weight: Weight for semantic similarity
        hierarchy_weight: Weight for hierarchy

    Returns:
        Combined weight between 0 and 1
    """
    # Convert hierarchy distance to similarity using exponential decay
    hierarchy_similarity = math.exp(-3 * hierarchy_distance)

    # Combine weights
    combined = semantic_weight * semantic_similarity + hierarchy_weight * hierarchy_similarity

    return combined


# -------- Rationale generation helpers (concurrent) --------


async def _rationale_for_pair(text_a: str, text_b: str, model: str, max_tokens: int) -> str:
    """Generate a short rationale explaining why two pdf_objects are related."""
    try:
        a_snip = (text_a or "").strip()
        b_snip = (text_b or "").strip()
        if len(a_snip) > 800:
            a_snip = a_snip[:800] + " ..."
        if len(b_snip) > 800:
            b_snip = b_snip[:800] + " ..."
        system = "You explain concisely why two document snippets are related. Use one or two sentences. Avoid quoting long text."
        user = (
            f"Snippet A:\n{a_snip}\n\nSnippet B:\n{b_snip}\n\nExplain the relationship succinctly."
        )

        # If the selected model is an OpenAI model but no OPENAI_API_KEY is present,
        # fall back to the default LLM configured for the project.
        _mdl = model
        try:
            if (model or "").startswith("openai/") and not os.getenv("OPENAI_API_KEY"):
                _mdl = (
                    os.getenv("LITELLM_DEFAULT_MODEL")
                    or os.getenv("DEFAULT_LITELLM_MODEL")
                    or os.getenv("LITELLM_MODEL")
                    or "gemini/gemini-2.5-flash"
                )
        except Exception:
            pass

        params: Dict[str, Any] = {
            "model": _mdl,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "stream": False,
            "timeout": 60,
        }
        params["temperature"] = 1.0 if "gpt-5" in (_mdl or "").lower() else 0.1
        router = get_text_router()
        timeout_s = int(os.getenv("GRAPH_RATIONALE_TIMEOUT", "60"))
        import time as _t
        _t0 = _t.monotonic()
        try:
            resp = await router.acompletion(
                model="chutes/text",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"} if os.getenv("GRAPH_RATIONALE_JSON", "0") in ("1","true","yes") else None,
                temperature=1.0 if "gpt-5" in (_mdl or "").lower() else 0.1,
                timeout=timeout_s,
                max_tokens=max_tokens,
            )
            _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
            if isinstance(resp, dict):
                choices = resp.get("choices") or [{}]
                served_model = resp.get("model")
                usage = resp.get("usage") or {}
            else:
                choices = getattr(resp, "choices", [{}])
                served_model = getattr(resp, "model", None)
                usage = getattr(resp, "usage", None) or {}
            content = (choices[0].get("message", {}) or {}).get("content", "")
            log_timing(
                "11_arango_create_graph",
                {
                    "attempt": "rationale",
                    "outcome": "ok",
                    "route_name": "chutes/text",
                    "model": served_model,
                    "latency_ms": _elapsed_ms,
                    "timeout_s": timeout_s,
                    "tokens_in": usage.get("prompt_tokens"),
                    "tokens_out": usage.get("completion_tokens"),
                },
            )
            return (content or "").strip()[:600]
        except Exception as e:
            _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
            log_timing(
                "11_arango_create_graph",
                {
                    "attempt": "rationale",
                    "outcome": "exception",
                    "exception": type(e).__name__,
                    "exception_msg": str(e)[:300],
                    "latency_ms": _elapsed_ms,
                    "timeout_s": timeout_s,
                },
            )
            raise
    except Exception:
        return ""


async def enrich_edges_with_rationales(
    edges: List[Dict[str, Any]], doc_text_map: Dict[str, str]
) -> None:
    """Attach rationale text to each edge using concurrent LLM calls."""
    if not edges:
        return
    sem = asyncio.Semaphore(GRAPH_RATIONALE_CONCURRENCY)

    async def _task(edge: Dict[str, Any]) -> None:
        try:
            from_id = str(edge.get("_from", ""))
            to_id = str(edge.get("_to", ""))
            ta = doc_text_map.get(from_id, "")
            tb = doc_text_map.get(to_id, "")
            if not ta or not tb:
                edge["rationale"] = ""
                edge["rationale_model"] = GRAPH_RATIONALE_MODEL
                return
            async with sem:
                rationale = await _rationale_for_pair(
                    ta, tb, GRAPH_RATIONALE_MODEL, GRAPH_RATIONALE_MAX_TOKENS
                )
                edge["rationale"] = rationale
                edge["rationale_model"] = GRAPH_RATIONALE_MODEL
        except Exception:
            edge["rationale"] = ""
            edge["rationale_model"] = GRAPH_RATIONALE_MODEL

    await asyncio.gather(*(_task(e) for e in edges))


async def find_and_create_relationships(
    documents: List[Dict[str, Any]],
    embeddings: NDArray[np.float32],
    index: Any,
    k_neighbors: int = 10,
    similarity_threshold: float = 0.55,
    batch_size: int = 100,
    skip_db_insert: bool = False,
    db: Optional[StandardDatabase] = None,
    edge_collection: Optional[str] = None,
    proved_section_ids: Optional[set] = None,
):
    """Find similar documents and create edge relationships."""
    edge_buffer = []
    total_edges = 0

    # Pre-compute text lookup map for rationales
    doc_text_map: Dict[str, str] = {
        f"pdf_objects/{d.get('_key')}": (d.get("text_content") or "") for d in documents
    }

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Finding relationships...", total=len(documents))

        # Optionally emit 'proves' self-edges for sections with successful proofs
        if proved_section_ids:
            for doc in documents:
                try:
                    sec_id = doc.get("section_id")
                    if sec_id and sec_id in proved_section_ids:
                        edge_doc = {
                            "_from": f"pdf_objects/{doc['_key']}",
                            "_to": f"pdf_objects/{doc['_key']}",
                            "relationship_type": "proves",
                            "semantic_score": 1.0,
                            "hierarchy_distance": 0.0,
                            "weight": 1.0,
                            "source_pdf": doc.get("source_pdf"),
                            "discovery_method": "lean4_stage08",
                            "knn_rank": 0,
                            "neighbor_index": 0,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                        edge_buffer.append(edge_doc)
                except Exception:
                    # Keep graph building resilient; skip malformed docs
                    continue

        for idx, doc in enumerate(documents):
            query_embedding = embeddings[idx : idx + 1]
            similarities, indices = index_search(index, query_embedding, k_neighbors + 1)  # type: ignore[misc]

            for rank, (sim_idx, similarity) in enumerate(
                zip(indices[0][1:], similarities[0][1:]), start=1
            ):
                if similarity < similarity_threshold:
                    continue

                neighbor_doc = documents[int(sim_idx)]
                hierarchy_dist = calculate_hierarchy_distance(doc, neighbor_doc)
                combined_weight = calculate_combined_weight(
                    similarity,
                    hierarchy_dist,
                    semantic_weight=GRAPH_SEMANTIC_WEIGHT,
                    hierarchy_weight=GRAPH_HIERARCHY_WEIGHT,
                )

                edge_doc = {
                    "_from": f"pdf_objects/{doc['_key']}",
                    "_to": f"pdf_objects/{neighbor_doc['_key']}",
                    "relationship_type": "semantic_similarity",
                    "semantic_score": float(similarity),
                    "hierarchy_distance": hierarchy_dist,
                    "weight": float(combined_weight),
                    "source_pdf": doc["source_pdf"],
                    "discovery_method": "faiss_hierarchical",
                    "knn_rank": int(rank),
                    "neighbor_index": int(sim_idx),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                edge_buffer.append(edge_doc)

                if not skip_db_insert and len(edge_buffer) >= batch_size:
                    try:
                        if GRAPH_ENABLE_RATIONALES:
                            await enrich_edges_with_rationales(edge_buffer, doc_text_map)
                        assert db is not None and edge_collection is not None
                        edge_col = db.collection(edge_collection)
                        result = edge_col.import_bulk(edge_buffer, on_duplicate="ignore")
                        created = 0
                        try:
                            created = int(result.get("created", 0))  # type: ignore[attr-defined]
                        except Exception:
                            created = 0
                        total_edges += created
                        edge_buffer.clear()
                    except ArangoError as e:
                        logger.error(f"Failed to insert edges: {e}")

            progress.update(task, advance=1)

    if not skip_db_insert and edge_buffer:
        try:
            if GRAPH_ENABLE_RATIONALES:
                await enrich_edges_with_rationales(edge_buffer, doc_text_map)
            assert db is not None and edge_collection is not None
            edge_col = db.collection(edge_collection)
            result = edge_col.import_bulk(edge_buffer, on_duplicate="ignore")
            created = 0
            try:
                created = int(result.get("created", 0))  # type: ignore[attr-defined]
            except Exception:
                created = 0
            total_edges += created
        except ArangoError as e:
            logger.error(f"Failed to insert final edges: {e}")

    if skip_db_insert and GRAPH_ENABLE_RATIONALES and edge_buffer:
        await enrich_edges_with_rationales(edge_buffer, doc_text_map)

    if not skip_db_insert:
        logger.success(f"Created {total_edges} edge relationships")

    return edge_buffer if skip_db_insert else total_edges


def run(
    input_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    k_neighbors: int = 10,
    similarity_threshold: float = 0.55,
    skip_graph_creation: bool = False,
):
    """Builds graph relationships between PDF objects using FAISS and hierarchy."""
    console.print("[bold green]Building PDF Knowledge Graph (Stage 11)[/bold green]")

    # --- Directory and Data Setup ---
    stage_output_dir = output_dir / "11_arango_create_graph"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(input_json, "r") as f:
        documents = json.load(f)

    if not documents:
        console.print("[yellow]No documents to process. Exiting.[/yellow]")
        return

    # Global toggle to disable relationship building entirely
    if not GRAPH_RELATIONSHIPS_ENABLED:
        if skip_graph_creation:
            output_path = json_output_dir / "11_graph_edges.json"
            with open(output_path, "w") as f:
                json.dump([], f, indent=2)
            console.print(
                f"[yellow]Relationships disabled (GRAPH_RELATIONSHIPS_ENABLED=false). Wrote 0 edges to: {output_path}[/yellow]"
            )
        else:
            confirmation = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "Skipped",
                "edges_created": 0,
                "reason": "GRAPH_RELATIONSHIPS_ENABLED=false",
            }
            output_path = json_output_dir / "11_graph_confirmation.json"
            with open(output_path, "w") as f:
                json.dump(confirmation, f, indent=2)
            console.print(
                f"[yellow]Relationships disabled (GRAPH_RELATIONSHIPS_ENABLED=false). Confirmation saved to: {output_path}[/yellow]"
            )
        return

    docs_with_embed = [doc for doc in documents if doc.get("embedding")]
    if not docs_with_embed:
        # Try proves/conflicts-only offline path when proofs/normalized units exist
        proved_sec_ids: Optional[set] = None
        try:
            tpath = output_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
            if tpath.exists():
                tdata = json.loads(tpath.read_text(encoding="utf-8"))
                if isinstance(tdata, dict):
                    prs = tdata.get("proof_results")
                    if isinstance(prs, list):
                        proved: set[str] = set()
                        for pr in prs:
                            item = (pr or {}).get("item") or {}
                            sid = (item.get("source_details") or {}).get("section_id")
                            status = (pr or {}).get("status")
                            if sid and (status is None or str(status).lower() in {"ok", "proved", "success", "true"}):
                                proved.add(sid)
                        if proved:
                            proved_sec_ids = proved
        except Exception as e:
            logger.warning(f"Stage 11: proves-only detection failed: {e}")

        if skip_graph_creation:
            edges: list[dict] = []
            # Conflicts (units) first
            try:
                edges.extend(_conflict_edges_from_docs(documents))
            except Exception:
                pass
            # Duplicates
            try:
                edges.extend(_duplicates_edges_from_docs(documents))
            except Exception:
                pass
            # Contradicts
            try:
                edges.extend(_contradicts_edges_from_docs(documents))
            except Exception:
                pass
            # Duplicates
            try:
                edges.extend(_duplicates_edges_from_docs(documents))
            except Exception:
                pass
            # Proves
            if proved_sec_ids:
                edges.extend(_proves_edges_from_docs(documents, proved_sec_ids))
            # Supersedes
            try:
                edges.extend(_supersedes_edges_from_docs(documents))
            except Exception:
                pass
            # Refers-to
            try:
                edges.extend(_refers_to_edges_from_docs(documents))
            except Exception:
                pass
            output_path = json_output_dir / "11_graph_edges.json"
            with open(output_path, "w") as f:
                json.dump(edges, f, indent=2)
            summary = _validate_edges(edges)
            _save_summary(json_output_dir, summary)
            console.print(f"[yellow]No embeddings found; wrote {len(edges)} edges to: {output_path}[/yellow]")
            return
        else:
            confirmation = {
                "timestamp": datetime.now().isoformat(),
                "status": "Completed",
                "edges_created": 0,
                "note": "No embeddings; DB path did not insert proves-only edges.",
            }
            output_path = json_output_dir / "11_graph_confirmation.json"
            with open(output_path, "w") as f:
                json.dump(confirmation, f, indent=2)
            console.print(
                f"[yellow]No embeddings found; confirmation saved to: {output_path}[/yellow]"
            )
            return
    embeddings = np.array([doc["embedding"] for doc in docs_with_embed], dtype="float32")

    # --- FAISS Indexing ---
    console.print("Building FAISS index...")
    index = build_faiss_index(embeddings)

    # --- Relationship Calculation ---
    console.print("Finding and creating relationships...")

    db = None
    edge_collection = GRAPH_EDGE_COLLECTION
    if not skip_graph_creation:
        try:
            host = os.getenv("ARANGO_HOST", "localhost")
            port = int(os.getenv("ARANGO_PORT", 8529))
            user = os.getenv("ARANGO_USER", "root")
            password = os.getenv("ARANGO_PASS")
            db_name = os.getenv("ARANGO_DATABASE", "pdf_knowledge_base")

            if not password:
                raise ValueError("ARANGO_PASS environment variable is not set.")

            client = ArangoClient(hosts=f"http://{host}:{port}")
            db = client.db(db_name, username=user, password=password)
            db.version()
            logger.success(f"Connected to ArangoDB database '{db_name}'.")
            edge_collection = ensure_graph_and_edge_collection(
                db,
                graph_name=GRAPH_GRAPH_NAME,
                edge_collection=GRAPH_EDGE_COLLECTION,
                vertex_collection=GRAPH_VERTEX_COLLECTION,
            )
        except (ArangoError, ValueError) as e:
            logger.error(f"Failed to connect to ArangoDB: {e}")
            raise RuntimeError("Failed to connect to ArangoDB")

    # Detect proved section ids from Stage 08 (if present)
    proved_sec_ids: Optional[set] = None
    try:
        tpath = output_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
        if tpath.exists():
            tdata = json.loads(tpath.read_text(encoding="utf-8"))
            if isinstance(tdata, dict):
                proof_results = tdata.get("proof_results")
                if isinstance(proof_results, list):
                    proved: set = set()
                    for pr in proof_results:
                        try:
                            item = (pr or {}).get("item") or {}
                            src = item.get("source_details") or {}
                            sid = src.get("section_id")
                            status = (pr or {}).get("status")
                            if sid and (status is None or str(status).lower() in {"ok", "proved", "success", "true"}):
                                proved.add(sid)
                        except Exception:
                            continue
                    if proved:
                        proved_sec_ids = proved
    except Exception as e:
        logger.warning(f"Stage 11: failed to read Stage 08 theorems for 'proves' edges: {e}")

    edges = asyncio.run(
        find_and_create_relationships(
            documents=docs_with_embed,
            embeddings=embeddings,
            index=index,
            k_neighbors=k_neighbors if k_neighbors else GRAPH_K,
            similarity_threshold=(
                similarity_threshold if similarity_threshold else GRAPH_SIM_THRESHOLD
            ),
            skip_db_insert=skip_graph_creation,
            db=db,
            edge_collection=edge_collection,
            proved_section_ids=proved_sec_ids,
        )
    )
    # Append contradictions based on Lean4 normalized polarity (additive)
    try:
        contr = _contradicts_edges_from_docs(documents)
        if isinstance(edges, list):
            edges.extend(contr)
        elif contr and not skip_graph_creation and db is not None and edge_collection is not None:
            try:
                edge_col = db.collection(edge_collection)
                edge_col.import_bulk(contr, on_duplicate="ignore")
            except Exception:
                pass
    except Exception:
        pass
    # Also append conflicts edges when embeddings path ran
    try:
        conflicts = _conflict_edges_from_docs(docs_with_embed)
        dups = _duplicates_edges_from_docs(docs_with_embed)
        sups = _supersedes_edges_from_docs(docs_with_embed)
        refs = _refers_to_edges_from_docs(docs_with_embed)
        if isinstance(edges, list):
            edges.extend(conflicts + dups + sups + refs)
        else:
            # DB path: insert now if available
            ins = conflicts + dups + sups + refs
            if ins and not skip_graph_creation and db is not None and edge_collection is not None:
                try:
                    edge_col = db.collection(edge_collection)
                    edge_col.import_bulk(ins, on_duplicate="ignore")
                except Exception:
                    pass
    except Exception:
        pass

    # --- Final Output ---
    if skip_graph_creation:
        console.print(
            "[yellow]--skip-graph-creation flag is set. Saving graph edges to JSON.[/yellow]"
        )
        output_path = json_output_dir / "11_graph_edges.json"
        with open(output_path, "w") as f:
            json.dump(edges, f, indent=2)
        edges_list = cast(List[Dict[str, Any]], edges)
        console.print(f"📄 Saved {len(edges_list)} graph edges to: {output_path}")
        # Write summary/invariants
        summary = _validate_edges(edges_list)
        _save_summary(json_output_dir, summary)
    else:
        confirmation = {
            "timestamp": datetime.now().isoformat(),
            "status": "Completed",
            "edges_created": edges,
        }
        output_path = json_output_dir / "11_graph_confirmation.json"
        with open(output_path, "w") as f:
            json.dump(confirmation, f, indent=2)
        console.print(f"✅ Graph creation complete. Confirmation saved to: {output_path}")
        # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
        return output_path


def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    k_neighbors: int = 10,
    similarity_threshold: float = 0.55,
):
    """Run Stage 11 from a single JSON bundle, emitting edges JSON without DB access."""
    stage_output_dir = output_dir / "11_arango_create_graph"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        documents = data.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ValueError("Bundle must include non-empty 'documents' list")
    except Exception as e:
        print(f"Failed to load bundle: {e}")
        raise ValueError(f"Failed to load bundle: {e}")

    docs_with_embed = [doc for doc in documents if doc.get("embedding")]
    if not docs_with_embed:
        # Proves-only offline path for debug-bundle
        proved_sec_ids: Optional[set] = None
        try:
            tpath = output_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
            if tpath.exists():
                tdata = json.loads(tpath.read_text(encoding="utf-8"))
                if isinstance(tdata, dict):
                    prs = tdata.get("proof_results")
                    if isinstance(prs, list):
                        proved: set[str] = set()
                        for pr in prs:
                            item = (pr or {}).get("item") or {}
                            sid = (item.get("source_details") or {}).get("section_id")
                            status = (pr or {}).get("status")
                            if sid and (status is None or str(status).lower() in {"ok", "proved", "success", "true"}):
                                proved.add(sid)
                        if proved:
                            proved_sec_ids = proved
        except Exception as e:
            logger.warning(f"Stage 11 debug-bundle: proves-only detection failed: {e}")

        edges: list[dict] = []
        if proved_sec_ids:
            edges = _proves_edges_from_docs(documents, proved_sec_ids)
        output_path = json_output_dir / "11_graph_edges.json"
        output_path.write_text(json.dumps(edges, indent=2))
        # Summary
        summary = _validate_edges(edges)
        _save_summary(json_output_dir, summary)
        console.print(f"[yellow]Saved {len(edges)} edges to {output_path} (proves-only path)")
        return

    embeddings = np.array([doc["embedding"] for doc in docs_with_embed], dtype="float32")
    index = build_faiss_index(embeddings)

    # Detect proved sections from a standard Stage 08 location under output_dir
    proved_sec_ids: Optional[set] = None
    try:
        tpath = output_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
        if tpath.exists():
            tdata = json.loads(tpath.read_text(encoding="utf-8"))
            if isinstance(tdata, dict):
                proof_results = tdata.get("proof_results")
                if isinstance(proof_results, list):
                    proved: set = set()
                    for pr in proof_results:
                        try:
                            item = (pr or {}).get("item") or {}
                            src = item.get("source_details") or {}
                            sid = src.get("section_id")
                            status = (pr or {}).get("status")
                            if sid and (status is None or str(status).lower() in {"ok", "proved", "success", "true"}):
                                proved.add(sid)
                        except Exception:
                            continue
                    if proved:
                        proved_sec_ids = proved
    except Exception as e:
        logger.warning(f"Stage 11 debug-bundle: failed to read Stage 08 theorems: {e}")

    edges = asyncio.run(
        find_and_create_relationships(
            documents=docs_with_embed,
            embeddings=embeddings,
            index=index,
            k_neighbors=k_neighbors,
            similarity_threshold=similarity_threshold,
            skip_db_insert=True,
            db=None,
            edge_collection=GRAPH_EDGE_COLLECTION,
            proved_section_ids=proved_sec_ids,
        )
    )

    output_path = json_output_dir / "11_graph_edges.json"
    output_path.write_text(json.dumps(edges, indent=2))
    # Write summary/invariants for debug-bundle
    try:
        summary = _validate_edges(edges)
        _save_summary(json_output_dir, summary)
    except Exception:
        pass
    console.print(f"[green]Debug bundle: saved {len(edges)} graph edges to {output_path}")


## CLI removed: import and call run(...), or use a debug harness.


# Fallback NumPy search helpers when FAISS unavailable
if not _HAVE_FAISS:

    def build_faiss_index(embeddings: NDArray[np.float32]):
        emb = embeddings.copy()
        norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
        emb = emb / norms
        logger.warning("FAISS not available; using NumPy similarity search fallback.")
        return ("numpy", emb)

    def index_search(index_obj, query_embedding: NDArray[np.float32], k: int):
        kind, idx = index_obj
        q = query_embedding.copy()
        q /= np.linalg.norm(q, axis=1, keepdims=True) + 1e-12
        sims = (idx @ q.T).T
        order = np.argsort(-sims, axis=1)
        topk_idx = order[:, :k]
        topk_sim = np.take_along_axis(sims, topk_idx, axis=1)
        return topk_sim, topk_idx

else:

    def index_search(index_obj, query_embedding: NDArray[np.float32], k: int):
        _, fa = index_obj
        return fa.search(query_embedding, k)


if __name__ == "__main__":
    import sys, os
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        # Fail fast on missing Arango env; ensure upstream artifacts exist
        from extractor.pipeline.steps.sanity_helper import sanity_run
        sanity_run("10") if False else sanity_run("07")  # minimal prereqs
        ok_env = bool(os.getenv("ARANGO_URL") and os.getenv("ARANGO_DB") and (os.getenv("ARANGO_USER") or os.getenv("ARANGO_USERNAME")) and os.getenv("ARANGO_PASSWORD"))
        if not ok_env:
            print("Stage 11 sanity: missing Arango env; skipping graph creation. Upstream OK.")
            sys.exit(0)
        print("Stage 11 sanity: Arango env present; run via pipeline to create graph.")
        sys.exit(0)
    print("Usage: python -m extractor.pipeline.steps.11_arango_create_graph sanity")
