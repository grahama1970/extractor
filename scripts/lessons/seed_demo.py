#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import time
import uuid
import random
from typing import List
import typer
from scripts.lessons.arango_client import get_db

app = typer.Typer(add_completion=False)

TOPICS = [
    ("CDP discovery", ["cdp", "devtools", "puppeteer", "playwright"], "tabbed"),
    ("Vite proxy alignment", ["proxy", "vite", "backend", "api"], "tabbed"),
    ("pdf.js render cancelation", ["pdfjs", "render", "abort", "canvas"], "tabbed"),
    ("Thumbnails rail/filmstrip", ["thumbnails", "rail", "filmstrip", "cache"], "tabbed"),
    ("Resizable panes + ARIA", ["aria", "a11y", "resizer", "keyboard"], "tabbed"),
    ("Export dropdown rules", ["export", "json", "pdf", "zip"], "tabbed"),
    ("Exact JSON toggle", ["json", "strict", "canonical", "toggle"], "tabbed"),
    ("Pager placement", ["pager", "toolbar", "zoom"], "tabbed"),
    ("Lessons infra", ["codex", "uv", "docker", "arango", "redis"], "infra"),
    ("Gemini JSON reliability", ["gemini", "litellm", "json", "schema"], "pipeline"),
    ("Image attachments", ["image", "prompt", "stdin", "-i"], "pipeline"),
    ("LLM logging + smokes", ["smokes", "logging", "artifacts"], "pipeline"),
]

SUFFIXES = [
    "gotchas and fixes",
    "playbook",
    "stability guide",
    "troubleshooting",
    "pitfalls",
    "design notes",
]


def build_keywords(tags: List[str], scope: str) -> str:
    syn = {
        "cdp": ["chrome", "chromium", "devtools", "browserless", "puppeteer", "playwright"],
        "proxy": ["vite", "backend", "target", "api", "port", "8000", "8001"],
        "json": ["response_format", "schema", "structured", "wrap_json"],
        "smokes": ["smoke", "ci", "tests", "playwright", "puppeteer"],
        "timeout": ["hang", "stall", "latency"],
    }
    bag: List[str] = []
    for t in tags or []:
        bag.append(t)
        bag.extend(syn.get(t.lower(), []))
    if scope:
        bag.append(scope)
    # de-dupe
    seen = set()
    out: List[str] = []
    for w in bag:
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return " ".join(out)


@app.command()
def seed(
    count: int = typer.Option(50, help="How many demo lessons to insert"),
    scope: str = typer.Option("", help="Force scope for all; default mixes"),
    batch: str = typer.Option("", help="Demo batch id; default random UUID"),
):
    db = get_db()
    db.collection("lessons")
    ts = int(time.time())
    batch_id = batch or uuid.uuid4().hex[:12]
    inserted = 0
    for i in range(count):
        base, base_tags, base_scope = random.choice(TOPICS)
        sc = scope or base_scope
        title = f"DEMO[{batch_id}] {base} #{i+1} {random.choice(SUFFIXES)}"
        problem = f"Exploration of {base} within the extractor project: common pitfalls and how to avoid them."
        playbook = (
            f"- Identify root cause for {base}\n"
            f"- Apply stable settings and add smokes\n"
            f"- Document rationale and add graph edges"
        )
        tags = list(set(random.sample(base_tags, min(3, len(base_tags)))))
        keywords = build_keywords(tags, sc)
        doc = {
            "title": title,
            "problem": problem,
            "playbook": playbook,
            "tags": tags,
            "keywords": keywords,
            "scope": sc,
            "status": "active",
            "added_by": "agent",
            "updated_at": ts,
            "demo": True,
            "demo_batch": batch_id,
        }
        aql = (
            "UPSERT { title: @title, scope: @scope } "
            "INSERT @doc "
            "UPDATE @doc IN lessons RETURN NEW"
        )
        cur = db.aql.execute(aql, bind_vars={"title": title, "scope": sc, "doc": doc})
        _ = list(cur)[0]
        inserted += 1
    print(f"Seeded {inserted} demo lessons (batch={batch_id}).")


if __name__ == "__main__":
    app()
