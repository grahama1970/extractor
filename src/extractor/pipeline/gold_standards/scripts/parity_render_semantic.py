#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Render semantic HTML/MD/etc from canonical flattened blocks.

Input: flattened JSON (Stage 10 style, from PDF). Outputs:
  - semantic HTML (block-order, real tables)
  - markdown (pipe tables)
  - rst
  - docx/rst/html/epub/pptx/xml via pandoc (optional)

Keep content aligned: one block in → one block out.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any


def load_blocks(flat_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(flat_path.read_text())
    return data if isinstance(data, list) else []


def write_semantic_html(out: Path, blocks: List[Dict[str, Any]]):
    parts = ["<html><body>"]
    for blk in blocks:
        if blk.get("type") == "table" and blk.get("cells"):
            parts.append("<table border=1>")
            for row in blk["cells"]:
                vals = list(row.values()) if isinstance(row, dict) else row
                parts.append("<tr>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>")
            parts.append("</table>")
        else:
            parts.append(f"<p>{blk.get('text') or blk.get('content') or ''}</p>")
    parts.append("</body></html>")
    out.write_text("\n".join(parts), encoding="utf-8")


def write_markdown(out: Path, blocks: List[Dict[str, Any]]):
    lines = []
    for blk in blocks:
        if blk.get("type") == "table" and blk.get("cells"):
            for row in blk["cells"]:
                vals = list(row.values()) if isinstance(row, dict) else row
                lines.append(" | ".join(str(v) for v in vals))
        else:
            lines.append(blk.get("text") or blk.get("content") or "")
    out.write_text("\n\n".join(lines), encoding="utf-8")


def run_pandoc(src_md: Path, fmt: str, dest: Path):
    cmd = ["pandoc", str(src_md), "-o", str(dest)]
    if fmt == "rst":
        cmd = ["pandoc", str(src_md), "-t", "rst", "-o", str(dest)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--pandoc", action="store_true", help="Also emit docx/epub/pptx/xml via pandoc")
    args = ap.parse_args()

    blocks = load_blocks(args.flat)
    args.outdir.mkdir(parents=True, exist_ok=True)

    html = args.outdir / "semantic.html"
    md = args.outdir / "semantic.md"
    rst = args.outdir / "semantic.rst"

    write_semantic_html(html, blocks)
    write_markdown(md, blocks)
    run_pandoc(md, "rst", rst)

    if args.pandoc:
        run_pandoc(md, "docx", args.outdir / "semantic.docx")
        run_pandoc(md, "epub", args.outdir / "semantic.epub")
        run_pandoc(md, "pptx", args.outdir / "semantic.pptx")
        run_pandoc(md, "xml", args.outdir / "semantic.xml")
        run_pandoc(md, "html", args.outdir / "semantic_pandoc.html")

    print(f"Wrote semantic artifacts to {args.outdir} ({len(blocks)} blocks)")


if __name__ == "__main__":
    main()
