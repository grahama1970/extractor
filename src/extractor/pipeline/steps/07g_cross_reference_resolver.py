#!/usr/bin/env python3
from __future__ import annotations

"""
07g: Cross-Reference Resolver
- Scans paragraph blocks for references to figures, tables, sections, equations.
- Produces edges: paragraph_anchor_id -> target_anchor_id (or normalized_label).
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List

import typer
from loguru import logger

app = typer.Typer(help="Resolve cross-references (tables/figures/sections/equations).")

REF_PATTERNS = [
    (re.compile(r"\b(Fig(?:ure)?)[\s\-]*(\d+(?:[\.-]\d+)*)", re.I), "figure"),
    (re.compile(r"\b(Table)[\s\-]*(\d+(?:[\.-]\d+)*)", re.I), "table"),
    (re.compile(r"\b(Section)[\s\-]*(\d+(?:[\.-]\d+)*)", re.I), "section"),
    (re.compile(r"\bEq(?:uation)?\.?\s*\(?(\d+(?:[\.-]\d+)*)\)?", re.I), "equation"),
]


def normalize_label(kind: str, num: str) -> str:
    num_norm = re.sub(r"[.\-]+", "-", num.strip())
    return f"{kind.lower()}/{num_norm.lower()}"


@app.command()
def run(
    reflow_json: Path = typer.Option(..., "--reflow", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    data = json.loads(reflow_json.read_text())
    refs: List[Dict[str, Any]] = []
    # Build index of normalized labels to anchor ids
    label_index: Dict[str, str] = {}
    for s in data.get("reflowed_sections", data.get("sections", [])):
        for blk in s.get("reflowed_json", {}).get("blocks", []):
            if blk.get("type") in ("table", "figure") and blk.get("normalized_label"):
                label_index[blk["normalized_label"]] = blk.get("anchor_id")

    for s in data.get("reflowed_sections", data.get("sections", [])):
        for blk in s.get("reflowed_json", {}).get("blocks", []):
            if blk.get("type") != "paragraph":
                continue
            text = blk.get("text") or ""
            for pat, kind in REF_PATTERNS:
                for m in pat.finditer(text):
                    raw_num = m.group(2) if kind in ("figure", "table", "section") else m.group(1)
                    lbl = normalize_label(kind, raw_num)
                    target_anchor = label_index.get(lbl)
                    refs.append(
                        {
                            "source_paragraph": blk.get("anchor_id"),
                            "kind": kind,
                            "label": lbl,
                            "target_anchor": target_anchor,
                            "span": [m.start(), m.end()],
                        }
                    )

    out_dir = output_dir / "07g_cross_reference_resolver" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"references": refs, "count": len(refs), "deterministic": True, "hash_component": "07g"}
    out_path = out_dir / "07g_cross_refs.json"
    out_path.write_text(json.dumps(payload, indent=2))
    logger.success(f"07g: wrote {out_path} with {len(refs)} references")


if __name__ == "__main__":
    app()

