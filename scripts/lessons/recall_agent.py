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
        typer.echo(
            f"{i}. {r['title']}  [tags: {', '.join(r.get('tags', []))}]  (scope: {r.get('scope')})"
        )
        prob = r.get("problem") or ""
        typer.echo(f"   {prob[:140].strip()}...")


if __name__ == "__main__":
    app()
