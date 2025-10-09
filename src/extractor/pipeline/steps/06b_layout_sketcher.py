#!/usr/bin/env python3
"""
06b Layout Sketcher (skeleton)

Goal: build a deterministic, text-only layout sketch for each section so Stage 07
can be text-first and avoid images. This file is a minimal stub to let reviewers
propose concrete diffs. It should:
- Read Stage 04/05/06 artifacts from the results dir
- Produce 06b_layout_sketch.json with {sections: {id: {grid,elements,quick_summary}}}
- Be deterministic (no LLM/vision). Only bbox math + sorting.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

import typer

GRID = 12  # default grid granularity (rows = cols = GRID)


def _norm(v: float, a: float, b: float) -> float:
    if b <= a:
        return 0.0
    x = (v - a) / (b - a)
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _grid_bbox(bbox: List[float], page: List[float], grid: int) -> Dict[str, int]:
    x0, y0, x1, y1 = bbox or [0, 0, 0, 0]
    px0, py0, px1, py1 = page or [0, 0, 1, 1]
    gx0 = int(_norm(x0, px0, px1) * grid)
    gy0 = int(_norm(y0, py0, py1) * grid)
    gx1 = int(_norm(x1, px0, px1) * grid + 0.9999)
    gy1 = int(_norm(y1, py0, py1) * grid + 0.9999)
    # clamp
    gx0 = max(0, min(grid, gx0)); gx1 = max(0, min(grid, gx1))
    gy0 = max(0, min(grid, gy0)); gy1 = max(0, min(grid, gy1))
    return {"x0": gx0, "y0": gy0, "x1": gx1, "y1": gy1}


def _summ(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _build_section_sketch(sec: Dict[str, Any], grid: int) -> Dict[str, Any]:
    page_bbox = sec.get("bbox") or sec.get("page_bbox") or [0, 0, 1, 1]
    elements: List[Dict[str, Any]] = []
    # Text blocks
    for b in sec.get("blocks") or []:
        elements.append(
            {
                "kind": "text",
                "id": b.get("id"),
                "grid_bbox": _grid_bbox(b.get("bbox") or [0, 0, 0, 0], page_bbox, grid),
                "summary": _summ(b.get("text") or ""),
            }
        )
    # Tables
    for t in sec.get("tables") or []:
        hdr = t.get("header") or t.get("columns") or []
        elements.append(
            {
                "kind": "table",
                "id": t.get("id") or t.get("table_id"),
                "grid_bbox": _grid_bbox(t.get("bbox") or [0, 0, 0, 0], page_bbox, grid),
                "summary": _summ(" | ".join([str(h) for h in hdr]), 80),
                "confidence": float(t.get("confidence", 1.0)),
                "llm_assist": bool((t.get("llm_assist") or {}).get("patch")),
            }
        )
    # Figures
    for f in sec.get("figures") or []:
        elements.append(
            {
                "kind": "figure",
                "id": f.get("figure_id") or f.get("id"),
                "grid_bbox": _grid_bbox(f.get("bbox") or [0, 0, 0, 0], page_bbox, grid),
                "summary": _summ(f.get("caption") or ""),
            }
        )

    # quick summary: first text + first table header
    first_text = next((e["summary"] for e in elements if e["kind"] == "text" and e["summary"]), "")
    first_table = next((e["summary"] for e in elements if e["kind"] == "table" and e["summary"]), "")
    qs = " | ".join([s for s in (first_text, first_table) if s])
    return {"grid": grid, "elements": elements, "quick_summary": qs}


def run(input_path: str, output_path: str, **kwargs) -> Dict[str, Any]:
    """
    Build 06b_layout_sketch.json under 06b_layout_sketcher/json_output/.
    - input_path: base results dir (unused; for symmetry)
    - output_path: base results dir containing 04/05/06 outputs
    """
    base = Path(output_path)
    # Try to find Stage 04 sections file
    sec_json = base / "04_section_builder" / "json_output" / "04_sections.json"
    if not sec_json.exists():
        # fall back to a generic path if present
        alt = base / "06_sections.json"
        if alt.exists():
            sec_json = alt
        else:
            # nothing to do
            out = {"sections": {}}
            out_dir = base / "06b_layout_sketcher" / "json_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "06b_layout_sketch.json").write_text(json.dumps(out, indent=2))
            return out

    data = json.loads(sec_json.read_text(encoding="utf-8"))
    sections = data.get("sections") or []
    sketches: Dict[str, Any] = {"sections": {}}
    for sec in sections:
        sid = str(sec.get("id"))
        sketches["sections"][sid] = _build_section_sketch(sec, GRID)

    out_dir = base / "06b_layout_sketcher" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "06b_layout_sketch.json").write_text(json.dumps(sketches, ensure_ascii=False, indent=2))
    return sketches


app = typer.Typer(add_completion=False)


@app.command()
def main(
    results_dir: Path = typer.Option("data/results/pipeline", "-o", help="Results dir"),
) -> None:
    run(str(results_dir), str(results_dir))


if __name__ == "__main__":
    app()
