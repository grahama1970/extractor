#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "faiss-cpu>=1.7.4",
#   "sentence-transformers>=2.2.0",
# ]
# ///
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List
import numpy as np
import typer

app = typer.Typer(add_completion=False)


def _load_items(p: Path) -> List[dict]:
    data = json.loads(p.read_text())
    if isinstance(data, dict):
        return data.get("items") or []
    return data if isinstance(data, list) else []


@app.command()
def main(
    stage10_flat: Path = typer.Argument(
        ..., exists=True, readable=True, help="Stage 10 flattened JSON with items[]"
    ),
    out_edges: Path = typer.Argument(..., help="Output edges JSON for similar_knn"),
    model_name: str = typer.Option("sentence-transformers/all-MiniLM-L6-v2", "--model"),
    knn_k: int = typer.Option(5, "--knn-k", min=1),
    arango_db: str = typer.Option(
        "",
        "--arangodb",
        help="If set, upsert similar_knn edges into this DB (requires ARANGODB_URL/USERNAME/PASSWORD)",
    ),
):
    items = _load_items(stage10_flat)
    # Extract texts and ids
    ids: List[str] = []
    texts: List[str] = []
    for it in items:
        sid = str(it.get("section_id") or "").strip()
        txt = str(it.get("requirement_text") or it.get("rtm", {}).get("lean4_norm") or "").strip()
        if sid and txt:
            ids.append(sid)
            texts.append(txt)
    if not ids:
        out_edges.write_text(json.dumps({"edges": {"similar_knn": []}}, indent=2))
        typer.secho("No items to embed", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    # Encode embeddings
    from sentence_transformers import SentenceTransformer  # type: ignore
    import faiss  # type: ignore

    model = SentenceTransformer(model_name)
    X = model.encode(texts, normalize_embeddings=True)
    X = np.asarray(X, dtype="float32")
    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)
    D, I = index.search(X, min(knn_k + 1, len(ids)))

    edges = []
    for i, sid in enumerate(ids):
        for j, nbr_idx in enumerate(I[i]):
            if nbr_idx == i:  # skip self
                continue
            score = float(D[i][j])
            edges.append({"from": sid, "to": ids[nbr_idx], "score": score})

    # Simple stats
    stats = {
        "total_nodes": len(ids),
        "total_edges": len(edges),
        "knn_k": knn_k,
        "model": model_name,
    }
    payload = {"edges": {"similar_knn": edges}, "statistics": stats}
    out_edges.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    typer.secho(f"OK: wrote KNN edges to {out_edges}", fg=typer.colors.GREEN)

    if arango_db:
        try:
            from arango import ArangoClient  # type: ignore
        except Exception:
            typer.secho("python-arango not installed; skipping DB upsert", fg=typer.colors.YELLOW)
            raise typer.Exit(0)
        url = os.getenv("ARANGODB_URL", "http://localhost:8529")
        user = os.getenv("ARANGODB_USERNAME", os.getenv("ARANGODB_USER", "root"))
        pwd = os.getenv("ARANGODB_PASSWORD")
        if not pwd:
            typer.secho("Set ARANGODB_PASSWORD", fg=typer.colors.RED)
            raise typer.Exit(2)
        client = ArangoClient(hosts=url)
        sysdb = client.db("_system", username=user, password=pwd)
        if not sysdb.has_database(arango_db):
            sysdb.create_database(arango_db)
        db = client.db(arango_db, username=user, password=pwd)
        if not db.has_collection("similar_knn"):
            db.create_collection("similar_knn", edge=True)
        coll = db.collection("similar_knn")
        for e in edges:
            coll.insert(
                {
                    "_from": f"sections/{e['from']}",
                    "_to": f"sections/{e['to']}",
                    "score": e["score"],
                }
            )
        typer.secho(
            f"OK: upserted {len(edges)} edges into {arango_db}.similar_knn", fg=typer.colors.GREEN
        )


if __name__ == "__main__":
    app()
