#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import os
import glob
import re
import json
from pathlib import Path
import typer
from scripts.lessons.arango_client import get_db
import math

app = typer.Typer(add_completion=False)

STOP = set(
    "the a an and or of to for with in on at from by as is be are was were it this that these those into over under about your you we our their".split()
)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]{3,}", text.lower())
    return [w for w in words if w not in STOP][:50]


def latest_artifact() -> str | None:
    pat = str(Path("scripts/artifacts").resolve() / "*.log")
    files = sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


@app.command()
def recall(
    q: str = typer.Option("", help="Free-form query; if empty, use --from-latest-log"),
    tags: str = typer.Option("", help="Optional tags, comma-separated (e.g., 'cdp,proxy')"),
    scope: str = typer.Option("", help="Optional scope filter (e.g., 'tabbed' or 'pipeline')"),
    from_latest_log: bool = typer.Option(False, help="Derive query from latest artifacts/*.log"),
    k: int = typer.Option(5, help="Top K"),
    depth: int = typer.Option(2, help="Graph depth (1..4)"),
    use_graph: bool = typer.Option(True, help="Fuse BM25 with graph multihop"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON array"),
):
    if not q and from_latest_log:
        p = latest_artifact()
        if p and os.path.isfile(p):
            try:
                txt = Path(p).read_text(encoding="utf-8", errors="ignore")
                toks = tokenize(txt)
                if toks:
                    q = " ".join(toks[:20])
            except Exception:
                pass
    if not q:
        typer.echo("Provide --q or --from-latest-log to build a query.")
        raise typer.Exit(2)

    db = get_db()
    # Ensure view exists (best-effort)
    try:
        existing = [v.get("name") for v in db.views()]  # type: ignore[attr-defined]
    except Exception:
        existing = []
    if "lessons_search" not in existing:
        try:
            db.create_arangosearch_view(
                "lessons_search",
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
        except Exception:
            pass

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    bind = {"q": q, "k": k, "tags": tag_list, "scope": scope}
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
      RETURN KEEP(d, '_key','title','problem','playbook','tags','scope','status','updated_at')
    """
    cur = db.aql.execute(aql, bind_vars=bind)
    results = list(cur)
    if json_out:
        print(json.dumps(results, ensure_ascii=False))
        raise typer.Exit(0)
    if not results:
        typer.echo("No results.")
        raise typer.Exit(0)
    for i, r in enumerate(results, 1):
        typer.echo(f"{i}. {r['title']}  [tags: {', '.join(r.get('tags', []))}]  (scope: {r.get('scope')})")
        prob = (r.get('problem') or '')
        typer.echo(f"   {prob[:140].strip()}...")


if __name__ == "__main__":
    app()
cursor = db.aql.execute(aql, bind_vars=bind)
bm25 = list(cursor)
# Graph fusion (optional)
scores = {}
if use_graph and bm25:
    # Normalize BM25 by rank
    n = len(bm25)
    for idx, r in enumerate(bm25, start=1):
        scores[r['_key']] = {'bm25': (n - idx) / max(1,n-1), 'graph': 0.0}
    # Multihop per candidate
    depth = max(1, min(4, depth))
    import time as _t
    for r in bm25:
        seed = f"lessons/{r['_key']}"
        aqlg = ("""
            FOR v, e, p IN 1..@depth ANY @seed lesson_edges
              OPTIONS { bfs: true, uniqueVertices: 'path' }
              FILTER v._id != @seed
              LIMIT 50
              RETURN p.edges
            """)
        paths = list(db.aql.execute(aqlg, bind_vars={'seed': seed, 'depth': depth}))
        best = 0.0
        for edges in paths:
            logsum = 0.0
            for ed in edges or []:
                w = float(ed.get('weight') or 0)
                created = int(ed.get('last_verified_at') or ed.get('created_at') or 0)
                age_days = max(0.0, (_t.time() - created) / 86400.0)
                policy = ed.get('decay_policy') or 'standard'
                if policy == 'manual_exempt' and age_days <= 180:
                    dw = w
                else:
                    hl = 365.0 if policy == 'manual_exempt' else 90.0
                    dw = w * (0.5 ** (age_days / hl))
                dw = max(1e-6, min(1.0, dw))
                logsum += 0.9 * math.log(dw)
            score = math.exp(logsum) if edges else 0.0
            if score > best:
                best = score
        scores[r['_key']]['graph'] = best
    vals = [v['graph'] for v in scores.values()]
    mn, mx = (min(vals), max(vals)) if vals else (0.0, 0.0)
    for k2,v2 in scores.items():
        g = v2['graph']
        v2['graph'] = 0.0 if mx<=mn else (g - mn) / (mx - mn)
    fused = []
    for r in bm25:
        sc = scores[r['_key']]
        final = 0.6*sc['bm25'] + 0.4*sc['graph']
        fused.append((final, r))
    fused.sort(key=lambda x: x[0], reverse=True)
    out = [r for _, r in fused[:k]]
else:
    out = bm25
if json_out:
    print(json.dumps(out, ensure_ascii=False))
    raise typer.Exit(0)
if not out:
    typer.echo("No results.")
    raise typer.Exit(0)
for i, r in enumerate(out, 1):
    typer.echo(f"{i}. {r['title']}  [tags: {', '.join(r.get('tags', []))}]  (scope: {r.get('scope')})")
    prob = (r.get('problem') or '')
    typer.echo(f"   {prob[:140].strip()}...")
if __name__ == "__main__":
    app()

