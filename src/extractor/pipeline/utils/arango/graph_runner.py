"""Stage 11 arango graph creation runner."""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import numpy as np
from numpy.typing import NDArray
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

try:
    import faiss  # type: ignore
except Exception:
    faiss = None  # type: ignore

try:
    from arango import ArangoClient
    from arango.exceptions import ArangoError
except Exception:  # pragma: no cover - optional dependency
    ArangoClient = None  # type: ignore
    ArangoError = Exception  # type: ignore

_HAVE_FAISS = faiss is not None

GRAPH_RELATIONSHIPS_ENABLED = os.getenv("GRAPH_RELATIONSHIPS_ENABLED", "1").lower() in {
    "1",
    "true",
    "yes",
    "y",
}
GRAPH_ENABLE_RATIONALES = os.getenv("GRAPH_ENABLE_RATIONALES", "0").lower() in {
    "1",
    "true",
    "yes",
    "y",
}
GRAPH_EDGE_COLLECTION = os.getenv("GRAPH_EDGE_COLLECTION", "pdf_relationships")
GRAPH_VERTEX_COLLECTION = os.getenv("GRAPH_VERTEX_COLLECTION", "pdf_objects")
GRAPH_GRAPH_NAME = os.getenv("GRAPH_GRAPH_NAME", "pdf_graph")
GRAPH_K = int(os.getenv("GRAPH_K", "10"))
GRAPH_SIM_THRESHOLD = float(os.getenv("GRAPH_SIM_THRESHOLD", "0.55"))


def sanity() -> int:
    return run_step_sanity("11_arango_create_graph")


def _vertex_id(doc: dict[str, Any]) -> str | None:
    vid = doc.get("_id")
    if isinstance(vid, str) and vid:
        return vid
    key = doc.get("_key") or doc.get("key") or doc.get("id")
    if key is None:
        return None
    return f"{GRAPH_VERTEX_COLLECTION}/{key}"


def _edge(
    doc_from: dict[str, Any],
    doc_to: dict[str, Any],
    *,
    rel_type: str,
    score: float | None = None,
) -> dict[str, Any] | None:
    v_from = _vertex_id(doc_from)
    v_to = _vertex_id(doc_to)
    if not v_from or not v_to or v_from == v_to:
        return None
    payload: dict[str, Any] = {"_from": v_from, "_to": v_to, "type": rel_type}
    if score is not None:
        payload["score"] = float(score)
    return payload


def _conflict_edges_from_docs(_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def _duplicates_edges_from_docs(_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def _contradicts_edges_from_docs(_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def _proves_edges_from_docs(
    docs: list[dict[str, Any]], proved_section_ids: set
) -> list[dict[str, Any]]:
    return []


def _supersedes_edges_from_docs(_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def _refers_to_edges_from_docs(_: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def _validate_edges(edges: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for e in edges:
        t = str(e.get("type") or "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return {"total": len(edges), "by_type": by_type}


def _save_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "11_graph_summary.json").write_text(json.dumps(summary, indent=2))


def ensure_graph_and_edge_collection(
    db, graph_name: str, edge_collection: str, vertex_collection: str
):
    if db is None:
        return edge_collection
    if not db.has_collection(vertex_collection):
        db.create_collection(vertex_collection)
    if not db.has_collection(edge_collection):
        db.create_collection(edge_collection, edge=True)
    if not db.has_graph(graph_name):
        db.create_graph(
            graph_name,
            edge_definitions=[
                {
                    "edge_collection": edge_collection,
                    "from_vertex_collections": [vertex_collection],
                    "to_vertex_collections": [vertex_collection],
                }
            ],
            orphan_collections=[vertex_collection],
        )
    return edge_collection


def build_faiss_index(embeddings: NDArray[np.float32]):
    emb = embeddings.astype("float32", copy=True)
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
    emb = emb / norms
    if _HAVE_FAISS and faiss is not None:
        index = faiss.IndexFlatIP(emb.shape[1])
        index.add(emb)
        return ("faiss", index)
    logger.warning("FAISS not available; using NumPy similarity search fallback.")
    return ("numpy", emb)


def index_search(index_obj, query_embedding: NDArray[np.float32], k: int):
    kind, idx = index_obj
    if kind == "faiss":
        _, fa = index_obj
        return fa.search(query_embedding, k)
    q = query_embedding.copy()
    q /= np.linalg.norm(q, axis=1, keepdims=True) + 1e-12
    sims = (idx @ q.T).T
    order = np.argsort(-sims, axis=1)
    topk_idx = order[:, :k]
    topk_sim = np.take_along_axis(sims, topk_idx, axis=1)
    return topk_sim, topk_idx


def find_and_create_relationships(
    *,
    documents: list[dict[str, Any]],
    embeddings: NDArray[np.float32],
    index,
    k_neighbors: int,
    similarity_threshold: float,
    skip_db_insert: bool,
    db,
    edge_collection: str | None,
    proved_section_ids: set | None = None,
) -> list[dict[str, Any]]:
    if embeddings.size == 0:
        return []
    emb = embeddings.astype("float32", copy=False)
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
    emb = emb / norms
    sims, idxs = index_search(index, emb, max(1, int(k_neighbors)) + 1)
    edges: list[dict[str, Any]] = []
    for i, row in enumerate(idxs):
        for j_idx, sim in zip(row, sims[i]):
            j = int(j_idx)
            if j == i:
                continue
            if float(sim) < similarity_threshold:
                continue
            edge = _edge(documents[i], documents[j], rel_type="similarity", score=float(sim))
            if edge:
                edges.append(edge)
    if proved_section_ids:
        edges.extend(_proves_edges_from_docs(documents, proved_section_ids))
    if not skip_db_insert and db is not None and edge_collection is not None:
        db.collection(edge_collection).import_bulk(edges, on_duplicate="ignore")
    return edges

console = Console(stderr=True)


def run(
    input_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    k_neighbors: int = 10,
    similarity_threshold: float = 0.55,
    skip_graph_creation: bool = False,
):
    """Builds graph relationships between PDF objects using FAISS and hierarchy."""
    console.print("[bold green]Building PDF Knowledge Graph (Stage 11)[/bold green]")
    step_name = "graph_runner"

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

    if GRAPH_ENABLE_RATIONALES:
        try:
            require_scillm_preflight()
        except RuntimeError as exc:
            console.print(f"[red]Stage 11 SciLLM preflight failed: {exc}[/red]")
            raise

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
                            if sid and (
                                status is None
                                or str(status).lower() in {"ok", "proved", "success", "true"}
                            ):
                                proved.add(sid)
                        if proved:
                            proved_sec_ids = proved
        except Exception as exc:
            log_stage_error(step_name, exc, {"context": step_name})
            raise

        if skip_graph_creation:
            edges: list[dict] = []
            # Conflicts (units) first
            try:
                edges.extend(_conflict_edges_from_docs(documents))
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
            # Duplicates
            try:
                edges.extend(_duplicates_edges_from_docs(documents))
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
            # Contradicts
            try:
                edges.extend(_contradicts_edges_from_docs(documents))
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
            # Duplicates
            try:
                edges.extend(_duplicates_edges_from_docs(documents))
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
            # Proves
            if proved_sec_ids:
                edges.extend(_proves_edges_from_docs(documents, proved_sec_ids))
            # Supersedes
            try:
                edges.extend(_supersedes_edges_from_docs(documents))
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
            # Refers-to
            try:
                edges.extend(_refers_to_edges_from_docs(documents))
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
            output_path = json_output_dir / "11_graph_edges.json"
            with open(output_path, "w") as f:
                json.dump(edges, f, indent=2)
            summary = _validate_edges(edges)
            _save_summary(json_output_dir, summary)
            console.print(
                f"[yellow]No embeddings found; wrote {len(edges)} edges to: {output_path}[/yellow]"
            )
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
                            if sid and (
                                status is None
                                or str(status).lower() in {"ok", "proved", "success", "true"}
                            ):
                                proved.add(sid)
                        except Exception as exc:
                            log_stage_error(step_name, exc, {"context": step_name})
                            raise
                    if proved:
                        proved_sec_ids = proved
    except Exception as exc:
        log_stage_error(step_name, exc, {"context": step_name})
        raise

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
            except Exception as exc:
                log_stage_error(step_name, exc, {"context": step_name})
                raise
    except Exception as exc:
        log_stage_error(step_name, exc, {"context": step_name})
        raise
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
                except Exception as exc:
                    log_stage_error(step_name, exc, {"context": step_name})
                    raise
    except Exception as exc:
        log_stage_error(step_name, exc, {"context": step_name})
        raise

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
    step_name = "graph_runner_debug"
    stage_output_dir = output_dir / "11_arango_create_graph"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        documents = data.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ValueError("Bundle must include non-empty 'documents' list")
    except Exception as exc:
        log_stage_error(step_name, exc, {"context": step_name})
        raise

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
                            if sid and (
                                status is None
                                or str(status).lower() in {"ok", "proved", "success", "true"}
                            ):
                                proved.add(sid)
                        if proved:
                            proved_sec_ids = proved
        except Exception as exc:
            log_stage_error(step_name, exc, {"context": step_name})
            raise

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
                            if sid and (
                                status is None
                                or str(status).lower() in {"ok", "proved", "success", "true"}
                            ):
                                proved.add(sid)
                        except Exception as exc:
                            log_stage_error(step_name, exc, {"context": step_name})
                            raise
                    if proved:
                        proved_sec_ids = proved
    except Exception as exc:
        log_stage_error(step_name, exc, {"context": step_name})
        raise

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
    except Exception as exc:
        log_stage_error(step_name, exc, {"context": step_name})
        raise
    console.print(f"[green]Debug bundle: saved {len(edges)} graph edges to {output_path}")


## CLI removed: import and call run(...), or use a debug harness.


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    print("Usage: python -m extractor.pipeline.steps.11_arango_create_graph sanity")
