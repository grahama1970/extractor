#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import math
import time
import json
from typing import List, Dict, Any
import typer

from scripts.lessons.arango_client import get_db

app = typer.Typer(add_completion=False)


def bm25_rank(db, q: str, scope: str, tags: List[str], k: int) -> List[Dict[str, Any]]:
    bind = {"q": q, "k": max(1, k), "tags": tags, "scope": scope or ""}
    aql = """
    FOR d IN lessons_search
      SEARCH ANALYZER(
        d.title IN TOKENS(@q, 'text_en') OR
        d.problem IN TOKENS(@q, 'text_en') OR
        d.playbook IN TOKENS(@q, 'text_en') OR
        d.tags IN TOKENS(@q, 'text_en') OR
        d.keywords IN TOKENS(@q, 'text_en')
      , 'text_en')
      FILTER LENGTH(@tags)==0 OR d.tags ANY IN @tags
      FILTER @scope=='' OR d.scope==@scope
      SORT BM25(d) DESC, TFIDF(d) DESC
      LIMIT @k
      RETURN KEEP(d, '_key','title','scope','tags')
    """
    return list(db.aql.execute(aql, bind_vars=bind))


def graph_score_for_seed(db, seed_id: str, depth: int) -> float:
    aqlg = """
    FOR v, e, p IN 1..@depth ANY @seed lesson_edges
      OPTIONS { bfs: true, uniqueVertices: 'path' }
      FILTER v._id != @seed
      LIMIT 50
      RETURN p.edges
    """
    paths = list(db.aql.execute(aqlg, bind_vars={"seed": seed_id, "depth": depth}))
    best = 0.0
    for edges in paths:
        logsum = 0.0
        for ed in edges or []:
            w = float(ed.get("weight") or 0)
            created = int(ed.get("last_verified_at") or ed.get("created_at") or 0)
            age_days = max(0.0, (time.time() - created) / 86400.0)
            policy = ed.get("decay_policy") or "standard"
            if policy == "manual_exempt" and age_days <= 180:
                dw = w
            else:
                hl = 365.0 if policy == "manual_exempt" else 90.0
                dw = w * (0.5 ** (age_days / hl))
            dw = max(1e-6, min(1.0, dw))
            logsum += 0.9 * math.log(dw)
        score = math.exp(logsum) if edges else 0.0
        if score > best:
            best = score
    return best


def fuse_bm25_graph(db, bm25: List[Dict[str, Any]], depth: int, k: int) -> List[Dict[str, Any]]:
    if not bm25:
        return []
    # Normalize BM25 by reciprocal rank
    n = len(bm25)
    scores = {
        r["_key"]: {"bm25": (n - idx) / max(1, n - 1), "graph": 0.0}
        for idx, r in enumerate(bm25, start=1)
    }
    # Graph per candidate
    depth = max(1, min(4, depth))
    for r in bm25:
        seed = f"lessons/{r['_key']}"
        scores[r["_key"]]["graph"] = graph_score_for_seed(db, seed, depth)
    # Normalize graph
    gvals = [v["graph"] for v in scores.values()]
    mn, mx = (min(gvals), max(gvals)) if gvals else (0.0, 0.0)
    for key, sc in scores.items():
        g = sc["graph"]
        sc["graph"] = 0.0 if mx <= mn else (g - mn) / (mx - mn)
    fused = []
    for r in bm25:
        sc = scores[r["_key"]]
        final = 0.6 * sc["bm25"] + 0.4 * sc["graph"]
        fused.append((final, r))
    fused.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in fused[:k]]


@app.command()
def diff(
    q: str = typer.Option(..., help="Search query"),
    scope: str = typer.Option("", help="Optional scope filter"),
    tags: str = typer.Option("", help="Optional tags (comma)"),
    k: int = typer.Option(5, help="Top K"),
    depth: int = typer.Option(2, help="Graph depth (1..4)"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON with bm25 and fused arrays"),
):
    db = get_db()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    bm25 = bm25_rank(db, q=q, scope=scope, tags=tag_list, k=k)
    fused = fuse_bm25_graph(db, bm25=bm25, depth=depth, k=k)
    if json_out:
        print(json.dumps({"bm25": bm25, "fused": fused}, ensure_ascii=False))
        raise typer.Exit(0)
    # Pretty side-by-side output
    print(f"Query: {q}  | scope={scope or '(any)'}  tags={','.join(tag_list) or '(none)'}")
    print("\nRank  BM25 Title                                 | Fused Title")
    print("----- ------------------------------------------+-------------------------------")
    for i in range(max(len(bm25), len(fused))):
        b = bm25[i]["title"][:42] if i < len(bm25) else ""
        f = fused[i]["title"][:29] if i < len(fused) else ""
        print(f"{i+1:>4}  {b:<42} | {f}")


if __name__ == "__main__":
    app()
