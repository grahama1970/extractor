#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
#   "pymupdf>=1.26.1",
# ]
# ///

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise SystemExit(f"PyMuPDF (fitz) is required: {e}")


app = typer.Typer(add_completion=False, help="Generate side-by-side verification bundles for extracted tables")


def _table_rows(table: Dict[str, Any]) -> List[List[str]]:
    # Prefer pandas_df (list[dict]) → rows with stable column order
    if isinstance(table.get("pandas_df"), list):
        rows: List[List[str]] = []
        # gather unique columns in stable order from first row
        cols: List[str] = []
        for r in table["pandas_df"]:
            if isinstance(r, dict):
                for k in r.keys():
                    if k not in cols:
                        cols.append(str(k))
        if cols:
            rows.append(cols)
        for r in table["pandas_df"]:
            if not isinstance(r, dict):
                continue
            rows.append([str(r.get(c, "")) for c in cols])
        return rows
    # Fallback: nested list under "data"
    if isinstance(table.get("data"), list):
        return [[str(c) for c in row] for row in table["data"] if isinstance(row, list)]
    # Fallback: no rows
    return []


def _write_csv(rows: List[List[str]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)


def _rows_to_html(rows: List[List[str]]) -> str:
    if not rows:
        return "<table class=empty><tbody><tr><td>(empty)</td></tr></tbody></table>"
    head = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    parts = ["<table class=grid>"]
    if head:
        parts.append("<thead><tr>" + "".join(f"<th>{html.escape(str(c))}</th>" for c in head) + "</tr></thead>")
    parts.append("<tbody>")
    for r in body:
        parts.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _crop_png(pdf_path: Path, page_index: int, bbox: List[float], out_path: Path, dpi: int = 200) -> None:
    doc = fitz.open(str(pdf_path))
    try:
        if page_index < 0 or page_index >= len(doc):
            return
        page = doc[page_index]
        rect = fitz.Rect(*[float(v) for v in bbox])
        rect = rect & page.rect
        if rect.width <= 1 or rect.height <= 1:
            return
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, clip=rect)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_path))
    finally:
        doc.close()


def _write_view_html(dst: Path, meta: Dict[str, Any], png_rel: str, table_html: str) -> None:
    css = """
    body{font-family:system-ui,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;margin:0}
    header{padding:8px 12px;background:#111;color:#fff;position:sticky;top:0}
    main{display:flex;gap:8px;padding:8px}
    .left{flex:1 1 50%;overflow:auto;background:#f7f7f7;border-right:1px solid #ddd}
    .right{flex:1 1 50%;overflow:auto;padding:8px}
    img{max-width:100%;height:auto;display:block}
    table.grid{border-collapse:collapse;width:100%;}
    table.grid td,table.grid th{border:1px solid #ccc;padding:4px 6px;font-size:12px}
    .meta{font-size:12px;opacity:0.8}
    """
    head = html.escape(str(meta.get("id", "table")))
    body = f"""
    <header>
      <div><strong>Table:</strong> {head} <span class=meta>page={meta.get('page')} bbox={html.escape(str(meta.get('bbox')))} hash={html.escape(str(meta.get('hash')))}</span></div>
    </header>
    <main>
      <div class=left><img src="{html.escape(png_rel)}" alt="crop"></div>
      <div class=right>{table_html}</div>
    </main>
    """
    dst.write_text(f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>", encoding="utf-8")


def _write_index(dst: Path, items: List[Dict[str, Any]]) -> None:
    rows = []
    for it in items:
        rows.append(
            f"<tr><td>{html.escape(str(it['id']))}</td><td>{it['page']}</td>"
            f"<td><a href='{html.escape(it['view_rel'])}'>view</a></td>"
            f"<td><a href='{html.escape(it['csv_rel'])}'>csv</a></td>"
            f"<td><a href='{html.escape(it['html_rel'])}'>html</a></td>"
            f"<td><img src='{html.escape(it['png_rel'])}' style='max-width:160px'></td></tr>"
        )
    index = """
    <html><head><meta charset='utf-8'>
    <style>body{font-family:system-ui;margin:12px} td,th{padding:6px;border:1px solid #ddd} table{border-collapse:collapse;width:100%}</style>
    </head><body>
    <h2>Table Verification</h2>
    <table>
      <thead><tr><th>ID</th><th>Page</th><th>View</th><th>CSV</th><th>HTML</th><th>Thumb</th></tr></thead>
      <tbody>
    """ + "\n".join(rows) + "</tbody></table></body></html>"
    dst.write_text(index, encoding="utf-8")


@app.command()
def run(
    clean_pdf: Path = typer.Argument(..., exists=True, dir_okay=False, help="Path to *_clean.pdf"),
    tables_json: Path = typer.Argument(..., exists=True, dir_okay=False, help="05_tables.json path"),
    out_dir: Path = typer.Option(Path("data/results/pipeline/05_table_extractor/verify"), "-o", help="Verify output folder"),
    dpi: int = typer.Option(200, help="Crop resolution"),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(tables_json.read_text())
    tables = data.get("tables") if isinstance(data, dict) else None
    if not isinstance(tables, list):
        raise SystemExit("tables_json must contain {\"tables\":[...]} at top level")
    items: List[Dict[str, Any]] = []
    for idx, t in enumerate(tables):
        page = int(t.get("page_index", t.get("page", t.get("page_number", 0))))
        bbox = t.get("bbox") or t.get("bounds") or t.get("rect")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        rows = _table_rows(t)
        tid = t.get("id") or f"T-{idx:04d}"
        base = out_dir / f"table_{idx:04d}"
        base.mkdir(parents=True, exist_ok=True)
        crop_png = base / "crop.png"
        _crop_png(clean_pdf, page, bbox, crop_png, dpi=dpi)
        csv_path = base / "table.csv"
        _write_csv(rows, csv_path)
        html_path = base / "table.html"
        html_path.write_text(_rows_to_html(rows), encoding="utf-8")
        meta = {"id": tid, "page": page, "bbox": bbox, "hash": t.get("content_hash")}
        view_path = base / "view.html"
        _write_view_html(view_path, meta, "crop.png", html_path.name)
        items.append(
            {
                "id": tid,
                "page": page,
                "view_rel": f"table_{idx:04d}/view.html",
                "csv_rel": f"table_{idx:04d}/table.csv",
                "html_rel": f"table_{idx:04d}/table.html",
                "png_rel": f"table_{idx:04d}/crop.png",
            }
        )
        (base / "meta.json").write_text(json.dumps(meta, indent=2))
    _write_index(out_dir / "index.html", items)
    typer.secho(f"Wrote table verification bundle: {out_dir}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()

