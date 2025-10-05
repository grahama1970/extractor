#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from arango import ArangoClient


def load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def stable_doc_id(pdf_path: str) -> str:
    from hashlib import sha256

    p = Path(pdf_path)
    try:
        raw = p.read_bytes()
        h = sha256(raw).hexdigest()[:8]
        base = "".join(ch if ch.isalnum() else "_" for ch in p.stem.lower()).strip("_")
        return f"{base}__{h}"
    except Exception:
        return p.stem.lower()


@dataclass
class ExportContext:
    run_id: str
    stages: Path
    url: str
    db_name: str
    username: str
    password: str


def ensure_db(ctx: ExportContext):
    client = ArangoClient(hosts=ctx.url)
    sys_db = client.db("_system", username=ctx.username, password=ctx.password)
    if not sys_db.has_database(ctx.db_name):
        sys_db.create_database(ctx.db_name)
    db = client.db(ctx.db_name, username=ctx.username, password=ctx.password)
    # collections
    for c in ("documents", "sections", "tables", "figures", "entities"):
        if not db.has_collection(c):
            db.create_collection(c)
    for e in ("contains", "mentions", "references"):
        if not db.has_collection(e):
            db.create_collection(e, edge=True)
    return db


def upsert_docs(col, docs: List[Dict[str, Any]], key_field: str):
    if not docs:
        return
    for d in docs:
        key = d.get(key_field)
        if not key:
            continue
        d["_key"] = key
        if col.has(key):
            col.update(d)
        else:
            col.insert(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--stages", required=True)
    ap.add_argument("--db", default="extractor")
    ap.add_argument("--url", default="http://127.0.0.1:8529")
    ap.add_argument("--username", default=os.environ.get("ARANGO_USERNAME", "root"))
    ap.add_argument("--password", default=os.environ.get("ARANGO_PASSWORD", os.environ.get("ARANGO_ROOT_PASSWORD", "openSesame")))
    args = ap.parse_args()

    ctx = ExportContext(
        run_id=args.run_id,
        stages=Path(args.stages),
        url=args.url,
        db_name=args.db,
        username=args.username,
        password=args.password,
    )

    sections = load_json(ctx.stages / "04_section_builder" / "json_output" / "04_sections.json")
    tables = load_json(ctx.stages / "05_table_extractor" / "json_output" / "05_tables.json")
    figures = load_json(ctx.stages / "06_figure_extractor" / "json_output" / "06_figures.json")
    # Optional curated overlay
    curated = load_json(Path("data/runs") / ctx.run_id / "curated.json")
    # fallbacks
    doc_id = (
        sections.get("doc_id")
        or tables.get("doc_id")
        or stable_doc_id(sections.get("source_pdf") or tables.get("source_pdf") or figures.get("source_pdf") or "document.pdf")
    )

    db = ensure_db(ctx)
    col_docs = db.collection("documents")
    col_secs = db.collection("sections")
    col_tabs = db.collection("tables")
    col_figs = db.collection("figures")
    edge_contains = db.collection("contains")

    # Upsert document record
    doc_record = {
        "_key": doc_id,
        "doc_id": doc_id,
        "run_id": ctx.run_id,
        "source_pdf": sections.get("source_pdf") or tables.get("source_pdf") or figures.get("source_pdf"),
        "meta": {
            "section_count": len(sections.get("sections", [])),
            "table_count": len(tables.get("tables", [])),
            "figure_count": len(figures.get("figures", [])),
        },
    }
    if col_docs.has(doc_id):
        col_docs.update(doc_record)
    else:
        col_docs.insert(doc_record)

    # Build curated lookup maps by id/object_id
    cur_sections = {str(x.get("id") or x.get("object_id") or ""): x for x in (curated.get("sections") or [])}
    cur_tables   = {str(x.get("object_id") or x.get("id") or ""): x for x in (curated.get("tables") or [])}
    cur_figures  = {str(x.get("figure_id") or x.get("object_id") or x.get("id") or ""): x for x in (curated.get("figures") or [])}

    # Upsert sections (merge curated if match)
    sec_docs: List[Dict[str, Any]] = []
    for s in sections.get("sections", []):
        key = s.get("id") or f"sec_{s.get('level','0')}_{s.get('page',0)}_{len(sec_docs)+1}"
        out = {
            "_key": key,
            "doc_id": doc_id,
            "object_id": key,
            "title": s.get("title"),
            "level": s.get("level"),
            "page": s.get("page"),
            "bbox": s.get("bbox") or s.get("rect"),
        }
        if key in cur_sections:
            cs = cur_sections[key]
            out["title"] = cs.get("title", out["title"])
            out["page"] = cs.get("page", out["page"])
            out["bbox"] = cs.get("bbox") or cs.get("rect") or out["bbox"]
        sec_docs.append(out)
    upsert_docs(col_secs, sec_docs, "_key")

    # Upsert tables
    tab_docs: List[Dict[str, Any]] = []
    for t in tables.get("tables", []):
        key = t.get("object_id") or f"table_p{t.get('page_index',0):03d}_t{t.get('table_index',0):02d}"
        out = {
            "_key": key,
            "doc_id": doc_id,
            "object_id": key,
            "page": t.get("page_index"),
            "bbox": t.get("bbox"),
            "rank_features": (t.get("fusion") or {}).get("rank_features"),
        }
        if key in cur_tables:
            ct = cur_tables[key]
            out["page"] = ct.get("page", out["page"])
            out["bbox"] = ct.get("bbox") or ct.get("rect") or out["bbox"]
        tab_docs.append(out)
    upsert_docs(col_tabs, tab_docs, "_key")

    # Upsert figures
    fig_docs: List[Dict[str, Any]] = []
    for f in figures.get("figures", []):
        key = f.get("figure_id") or f"fig_p{f.get('page',0):03d}_{len(fig_docs)+1:03d}"
        out = {
            "_key": key,
            "doc_id": doc_id,
            "object_id": key,
            "page": f.get("page"),
            "bbox": f.get("bbox"),
            "section_id": f.get("section_id"),
        }
        if key in cur_figures:
            cf = cur_figures[key]
            out["page"] = cf.get("page", out["page"])
            out["bbox"] = cf.get("bbox") or cf.get("rect") or out["bbox"]
            out["section_id"] = cf.get("section_id", out.get("section_id"))
        fig_docs.append(out)
    upsert_docs(col_figs, fig_docs, "_key")

    # contains edges: document -> sections/tables/figures
    def upsert_contains(col, from_key: str, to_col_name: str, to_keys: List[str]):
        for tk in to_keys:
            edge_key = f"{from_key}__{to_col_name}__{tk}"
            edge_doc = {"_key": edge_key, "_from": f"documents/{from_key}", "_to": f"{to_col_name}/{tk}"}
            if col.has(edge_key):
                col.update(edge_doc)
            else:
                col.insert(edge_doc)

    upsert_contains(edge_contains, doc_id, "sections", [d["_key"] for d in sec_docs])
    upsert_contains(edge_contains, doc_id, "tables", [d["_key"] for d in tab_docs])
    upsert_contains(edge_contains, doc_id, "figures", [d["_key"] for d in fig_docs])

    summary = {
        "ok": True,
        "url": ctx.url,
        "db": ctx.db_name,
        "run_id": ctx.run_id,
        "doc_id": doc_id,
        "counts": {
            "sections": len(sec_docs),
            "tables": len(tab_docs),
            "figures": len(fig_docs),
        },
    }
    out = Path("arango_export")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{ctx.run_id}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
