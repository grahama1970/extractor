from __future__ import annotations
import time, hashlib, random
from typing import List
import numpy as np
import typer

from ..arango_client import get_db

app = typer.Typer(add_completion=False)


def l2_normalize(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True) + 1e-8
    return x / n


def pair_id(a_id: str, b_id: str) -> str:
    a, b = (a_id, b_id) if a_id <= b_id else (b_id, a_id)
    return hashlib.sha1((a + '|' + b).encode('utf-8')).hexdigest()


def doc_text(d) -> str:
    parts: List[str] = []
    for k in ("title", "problem", "playbook"):
        v = d.get(k)
        if v:
            parts.append(str(v))
    tags = d.get("tags") or []
    if tags:
        parts.append(" ".join(tags))
    return "\n".join(parts)


def tags_overlap(a: List[str], b: List[str]) -> float:
    A, B = set([t.lower() for t in a or []]), set([t.lower() for t in b or []])
    if not A and not B:
        return 0.0
    inter = len(A & B)
    uni = len(A | B)
    return inter / max(1, uni)


@app.command()
def propose(
    k: int = typer.Option(12, help="K neighbors"),
    sim_thresh: float = typer.Option(0.55, help="Min cosine sim"),
    min_top: int = typer.Option(3, help="Ensure at least top-N evaluate"),
    scope: str = typer.Option("", help="Optional scope filter for candidates"),
    dry_run: bool = typer.Option(False, help="Do not write edges; just print candidates"),
):
    try:
        import faiss  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as e:
        typer.echo(f"FAISS or sentence-transformers not available: {e}")
        raise typer.Exit(2)

    db = get_db()
    lessons = list(db.collection("lessons"))
    if scope:
        lessons = [d for d in lessons if (d.get("scope") or "") == scope]
    if not lessons:
        typer.echo("No lessons found.")
        raise typer.Exit(0)

    texts = [doc_text(d) for d in lessons]
    ids = [f"lessons/{d['_key']}" for d in lessons]
    tags_list = [d.get("tags") or [] for d in lessons]
    scopes = [d.get("scope") or "" for d in lessons]

    model = SentenceTransformer('all-MiniLM-L6-v2')
    emb = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    emb = l2_normalize(emb.astype('float32'))

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    D, I = index.search(emb, k + 1)

    ts = int(time.time())
    wrote = 0
    for i, (sims, idxs) in enumerate(zip(D, I)):
        src_id = ids[i]
        src_tags = tags_list[i]
        src_scope = scopes[i]
        cands = []
        for j, sim in zip(idxs[1:], sims[1:]):
            cand_id = ids[j]
            if cand_id == src_id:
                continue
            cands.append((cand_id, float(sim), j))
        cands = sorted(cands, key=lambda x: x[1], reverse=True)
        cands_eval = [c for c in cands if c[1] >= sim_thresh]
        if len(cands_eval) < min_top:
            cands_eval = cands[: min_top]

        for cand_id, sim, j in cands_eval:
            pid = pair_id(src_id, cand_id)
            # skip if rejected
            try:
                rej = db.collection("rejected_pairs").get(pid)
                if rej:
                    continue
            except Exception:
                pass
            tgt = lessons[j]
            tgt_tags = tags_list[j]
            tgt_scope = scopes[j]
            tovl = tags_overlap(src_tags, tgt_tags)
            scope_match = 1.0 if src_scope and (src_scope == tgt_scope) else 0.0
            overlaps = []
            if tovl >= 0.01:
                overlaps.append(f"{int(tovl*100)}% tag overlap")
            if scope_match:
                overlaps.append("scope match")
            src_title = (lessons[i].get("title") or "").lower().split()
            tgt_title = (tgt.get("title") or "").lower().split()
            tok_overlap = len(set(src_title) & set(tgt_title))
            if tok_overlap >= 2:
                overlaps.append(f"{tok_overlap} title tokens overlap")
            if len(overlaps) < 2:
                try:
                    db.collection("rejected_pairs").insert({
                        "_key": pid,
                        "pair_id": pid,
                        "reason": "insufficient concrete overlap",
                        "last_checked_at": ts,
                        "attempts": 1,
                    })
                except Exception:
                    pass
                continue
            weight = 0.60 * sim + 0.15 * tovl + 0.15 * scope_match
            weight = max(0.0, min(1.0, weight))
            rationale = f"Related because: {', '.join(overlaps)}"
            approved = (weight >= 0.60) and (scope_match == 1.0) and (sim >= 0.55)
            if dry_run:
                print(f"PAIR {src_id} ~ {cand_id} sim={sim:.2f} weight={weight:.2f} approved={approved} :: {rationale}")
                continue
            for frm, to in ((src_id, cand_id), (cand_id, src_id)):
                aql = (
                    "UPSERT { _from: @from, _to: @to, type: 'related' } "
                    "INSERT { _from: @from, _to: @to, type: 'related', source: 'faiss', weight: @w, raw_sim: @sim, confidence: @conf, approved: @appr, rationale: @rat, rationales: [ { by: 'agent', text: @rat, at: @ts } ], status: @status, created_at: @ts, updated_at: @ts, last_verified_at: @ts, pair_id: @pid, decay_policy: 'standard' } "
                    "UPDATE { source: 'faiss', weight: @w, raw_sim: @sim, confidence: @conf, approved: @appr, rationale: @rat, updated_at: @ts, last_verified_at: @ts, status: @status, pair_id: @pid } IN lesson_edges"
                )
                db.aql.execute(aql, bind_vars={
                    'from': frm, 'to': to, 'w': weight, 'sim': sim, 'conf': weight, 'appr': approved, 'rat': rationale, 'ts': ts, 'status': 'active' if approved else 'pending', 'pid': pid
                })
            wrote += 1
    print(f"Proposed/updated {wrote} edges.")
