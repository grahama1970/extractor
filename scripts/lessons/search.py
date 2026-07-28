#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import typer
from scripts.lessons.arango_client import get_db

app = typer.Typer(add_completion=False)


@app.command()
def search(
    q: str = typer.Option(..., help="Search query"),
    k: int = typer.Option(10, help="Top K"),
    tags: str = typer.Option("", help="Optional tags (comma)"),
    scope: str = typer.Option("", help="Optional scope filter"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON array"),
):
    """Search for lessons based on query, tags, and scope filters."""
    db = get_db()
    view = "lessons_search"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    # BM25/TFIDF over linked fields; filter tags if provided
    bind = {"q": q, "k": k, "tags": tag_list, "scope": scope}
    aql = f"""
    FOR d IN {view}
      SEARCH ANALYZER(
        d.title IN TOKENS(@q, 'text_en') OR
        d.problem IN TOKENS(@q, 'text_en') OR
        d.playbook IN TOKENS(@q, 'text_en') OR
        d.tags IN TOKENS(@q, 'text_en') OR
        d.keywords IN TOKENS(@q, 'text_en')
      , 'text_en')
      {"FILTER LENGTH(@tags)==0 OR d.tags ANY IN @tags"}
      {"FILTER @scope=='' OR d.scope==@scope"}
      SORT BM25(d) DESC, TFIDF(d) DESC
      LIMIT @k
      RETURN KEEP(d, '_key','title','problem','playbook','tags','scope','status','updated_at')
    """
    # the FILTER expression is injected, but @tags still used for binding
    cursor = db.aql.execute(aql, bind_vars=bind)
    results = list(cursor)
    if json_out:
        import json as _json

        print(_json.dumps(results, ensure_ascii=False))
    else:
        for i, r in enumerate(results, 1):
            print(
                f"{i}. {r['title']}  [tags: {', '.join(r.get('tags', []))}]  (scope: {r.get('scope')})"
            )
            prob = r.get("problem") or ""
            print(f"   {prob[:120].strip()}...")
        if not results:
            print("No results.")


if __name__ == "__main__":
    app()
