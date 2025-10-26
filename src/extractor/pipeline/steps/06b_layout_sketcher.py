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
from typing import Any

import typer

GRID = 12  # default grid granularity (rows = cols = GRID)
SCHEMA_VERSION = "0.2.0"


def _norm(v: float, a: float, b: float) -> float:
    if b <= a:
        return 0.0
    x = (v - a) / (b - a)
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _grid_bbox(bbox: list[float], page: list[float], grid: int) -> dict[str, int]:
    """Map page bbox → grid cells using half-open contract [x0,x1), [y0,y1).

    - floor for starts, ceil for ends
    - clamp to [0, grid]
    - ensure non-degenerate (at least 1x1 cell)
    """
    import math

    x0, y0, x1, y1 = bbox or [0.0, 0.0, 0.0, 0.0]
    px0, py0, px1, py1 = page or [0.0, 0.0, 1.0, 1.0]

    nx0 = _norm(float(x0), float(px0), float(px1))
    ny0 = _norm(float(y0), float(py0), float(py1))
    nx1 = _norm(float(x1), float(px0), float(px1))
    ny1 = _norm(float(y1), float(py0), float(py1))

    gx0 = max(0, min(grid, int(math.floor(nx0 * grid))))
    gy0 = max(0, min(grid, int(math.floor(ny0 * grid))))
    gx1 = max(0, min(grid, int(math.ceil(nx1 * grid))))
    gy1 = max(0, min(grid, int(math.ceil(ny1 * grid))))

    if gx1 <= gx0:
        gx1 = min(grid, gx0 + 1)
    if gy1 <= gy0:
        gy1 = min(grid, gy0 + 1)

    return {"x0": gx0, "y0": gy0, "x1": gx1, "y1": gy1}


def _summ(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _norm_text(s: str) -> str:
    return " ".join((s or "").split())


def _text_sha1(s: str) -> str:
    import hashlib

    return hashlib.sha1(_norm_text(s).encode("utf-8")).hexdigest()


def _area(b: list[float]) -> float:
    if not b or len(b) != 4:
        return 0.0
    return max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1]))


def _aspect(b: list[float]) -> float:
    w = max(1e-6, (b[2] - b[0]))
    h = max(1e-6, (b[3] - b[1]))
    return w / h


def _detect_columns(
    elements: list[dict[str, Any]],
    page_bbox: list[float],
    min_gap_ratio: float = 0.04,
) -> list[list[float]]:
    """Detect 1–3 columns deterministically using x-center gaps.

    Returns list of [x0,x1] in page coordinates.
    """
    pts: list[float] = []
    for e in elements:
        b = e.get("bbox")
        if not b or len(b) != 4:
            continue
        pts.append((float(b[0]) + float(b[2])) / 2.0)
    pts.sort()
    if len(pts) < 3:
        return [[page_bbox[0], page_bbox[2]]]
    gaps: list[tuple[float, int]] = []
    for i in range(len(pts) - 1):
        gaps.append((pts[i + 1] - pts[i], i))
    page_w = max(1e-6, (page_bbox[2] - page_bbox[0]))
    cuts = [i for g, i in gaps if g / page_w >= min_gap_ratio]
    if not cuts:
        return [[page_bbox[0], page_bbox[2]]]
    bounds: list[float] = [page_bbox[0]] + [
        (pts[i] + pts[i + 1]) / 2.0 for i in cuts
    ] + [page_bbox[2]]
    cols = [[bounds[j], bounds[j + 1]] for j in range(len(bounds) - 1)]
    # Cap at 3 columns to avoid fragmentation on noisy inputs
    return cols[:3]


def _col_id_for(xc: float, columns: list[list[float]]) -> int:
    for i, (a, b) in enumerate(columns):
        if a <= xc <= b:
            return i
    return 0


def _iou(a: list[float], b: list[float]) -> float:
    try:
        ax0, ay0, ax1, ay1 = map(float, a)
        bx0, by0, bx1, by1 = map(float, b)
        ix0 = max(ax0, bx0)
        iy0 = max(ay0, by0)
        ix1 = min(ax1, bx1)
        iy1 = min(ay1, by1)
        iw = max(0.0, ix1 - ix0)
        ih = max(0.0, iy1 - iy0)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(0.0, (ax1 - ax0) * (ay1 - ay0))
        area_b = max(0.0, (bx1 - bx0) * (by1 - by0))
        union = max(1e-9, area_a + area_b - inter)
        return inter / union
    except Exception:
        return 0.0


def _build_flow_stream(
    elements: list[dict[str, Any]],
    columns_grid: list[dict[str, int]],
    *,
    exclude_header_footer: bool,
    place_floats: str = "inline",
) -> str:
    # Deterministic linearization with explicit dividers for LLM prompts
    lines: list[str] = []
    lines.append("[SECTION START]")
    col_count = len(columns_grid) if columns_grid else 1
    lines.append(f"[COLUMNS {col_count}]")

    # Group by column_id
    by_col: dict[int, list[dict[str, Any]]] = {}
    for e in elements:
        if exclude_header_footer and e.get("header_footer_candidate"):
            continue
        by_col.setdefault(int(e.get("column_id", 0)), []).append(e)

    def _emit_elem(e: dict[str, Any]) -> str:
        gid = e.get("id") or "?"
        if e.get("kind") == "text":
            return f"[PARA id={gid}] {e.get('summary','')}"
        if e.get("kind") == "table":
            hdr = e.get("summary", "").replace("\n", " ")
            return f"[TABLE id={gid} header=\"{hdr}\"]"
        if e.get("kind") == "figure":
            cap = e.get("summary", "").replace("\n", " ")
            anch = e.get("anchor_element_id")
            dist = e.get("anchor_distance")
            tail = f" [ANCHOR={anch} dist={dist}]" if anch else ""
            return f"[FIGURE id={gid} cap=\"{cap}\"]{tail}"
        return f"[ELEM id={gid} kind={e.get('kind')}]"

    # Place floats policy
    if place_floats not in {"inline", "sidebar", "append"}:
        place_floats = "inline"

    for cidx in sorted(by_col):
        lines.append(f"[COL {cidx} START]")
        col_elems = by_col[cidx]
        if place_floats == "inline":
            # Emit in reading_order; floats appear where they sort
            for e in col_elems:
                lines.append(_emit_elem(e))
        elif place_floats == "sidebar":
            # Emit non-floats first, then floats
            for e in col_elems:
                if e.get("kind") == "text":
                    lines.append(_emit_elem(e))
            for e in col_elems:
                if e.get("kind") in ("table", "figure"):
                    lines.append(_emit_elem(e))
        else:  # append
            for e in col_elems:
                if e.get("kind") != "figure" and e.get("kind") != "table":
                    lines.append(_emit_elem(e))
            for e in col_elems:
                if e.get("kind") in ("table", "figure"):
                    lines.append(_emit_elem(e))
        lines.append(f"[COL {cidx} END]")
    lines.append("[SECTION END]")
    return "\n".join(lines)


def _build_section_sketch(
    sec: dict[str, Any],
    grid: int,
    *,
    summary_limit: int = 80,
    min_gap_ratio: float = 0.04,
    header_footer_band: float = 0.05,
    place_floats: str = "inline",
    include_flow: bool = True,
) -> dict[str, Any]:
    page_bbox = sec.get("bbox") or sec.get("page_bbox") or [0, 0, 1, 1]
    page_index = int(sec.get("page_index", 0))

    raw_elements: list[dict[str, Any]] = []
    # Text blocks
    for b in sec.get("blocks") or []:
        bbox = b.get("bbox") or [0, 0, 0, 0]
        text = (b.get("text") or "")
        raw_elements.append(
            {
                "kind": "text",
                "id": b.get("id") or b.get("block_id"),
                "bbox": bbox,
                "grid_bbox": _grid_bbox(bbox, page_bbox, grid),
                "summary": _summ(text, summary_limit),
                "text_sha1": _text_sha1(text),
                "page": int(b.get("page_index", page_index)),
                "area": _area(bbox),
                "aspect": _aspect(bbox),
                "char_count": len(text or ""),
                "role": b.get("role") or "para",
            }
        )
    # Tables
    for t in sec.get("tables") or []:
        bbox = t.get("bbox") or [0, 0, 0, 0]
        hdr = t.get("header") or t.get("columns") or []
        hdr_text = " | ".join([str(h) for h in hdr])
        raw_elements.append(
            {
                "kind": "table",
                "id": t.get("id") or t.get("table_id"),
                "bbox": bbox,
                "grid_bbox": _grid_bbox(bbox, page_bbox, grid),
                "summary": _summ(hdr_text, summary_limit),
                "page": int(t.get("page_index", page_index)),
                "area": _area(bbox),
                "aspect": _aspect(bbox),
                "confidence": float(t.get("confidence", 1.0)),
                "llm_assist": bool((t.get("llm_assist") or {}).get("patch")),
            }
        )
    # Figures
    for f in sec.get("figures") or []:
        bbox = f.get("bbox") or [0, 0, 0, 0]
        cap = f.get("caption") or f.get("ai_description") or ""
        raw_elements.append(
            {
                "kind": "figure",
                "id": f.get("figure_id") or f.get("id"),
                "bbox": bbox,
                "grid_bbox": _grid_bbox(bbox, page_bbox, grid),
                "summary": _summ(cap, summary_limit),
                "page": int(f.get("page_index", page_index)),
                "area": _area(bbox),
                "aspect": _aspect(bbox),
                "llm_assist": bool((f.get("ai_description") or "").strip()),
            }
        )

    # Column detection on page coordinates (configurable gap ratio)
    columns = _detect_columns(raw_elements, page_bbox, min_gap_ratio=min_gap_ratio)

    # Assign reading order deterministically (col → top → left → -area → id)
    enriched: list[dict[str, Any]] = []
    for e in raw_elements:
        b = e.get("bbox") or [0, 0, 0, 0]
        xc = (float(b[0]) + float(b[2])) / 2.0
        e["column_id"] = _col_id_for(xc, columns)
        e["_top"] = float(b[1])
        e["_left"] = float(b[0])
        e["_neg_area"] = -float(e.get("area", _area(b)))
        # Header/footer candidates: near top/bottom bands
        try:
            height = (page_bbox[3] - page_bbox[1]) or 1.0
            top_band = page_bbox[1] + height * header_footer_band
            bot_band = page_bbox[3] - height * header_footer_band
            y0 = float(b[1])
            y1 = float(b[3])
            e["header_footer_candidate"] = bool(y1 <= top_band or y0 >= bot_band)
        except Exception:
            e["header_footer_candidate"] = False
        enriched.append(e)
    enriched.sort(key=lambda x: (
        int(x.get("column_id", 0)),
        round(float(x.get("_top", 0.0)), 3),
        round(float(x.get("_left", 0.0)), 3),
        round(float(x.get("_neg_area", 0.0)), 1),
        str(x.get("id", "")),
    ))
    for i, e in enumerate(enriched):
        e["reading_order"] = i
        e.pop("_top", None)
        e.pop("_left", None)
        e.pop("_neg_area", None)

    # Overlap flag via pairwise IoU
    try:
        for i, a in enumerate(enriched):
            a_bbox = a.get("bbox") or [0, 0, 0, 0]
            overlapped = False
            for j, b in enumerate(enriched):
                if i == j:
                    continue
                if _iou(a_bbox, b.get("bbox") or [0, 0, 0, 0]) > 0.01:
                    overlapped = True
                    break
            a["overlapped"] = overlapped
    except Exception:
        pass

    # Anchor floats (figures/tables) to nearest text
    texts = [e for e in enriched if e.get("kind") == "text"]
    for f in enriched:
        if f.get("kind") not in ("figure", "table"):
            continue
        fb = f.get("bbox") or [0, 0, 0, 0]
        fx = (fb[0] + fb[2]) / 2.0
        fy = (fb[1] + fb[3]) / 2.0
        best = None
        for t in texts:
            tb = t.get("bbox") or [0, 0, 0, 0]
            tx = (tb[0] + tb[2]) / 2.0
            ty = (tb[1] + tb[3]) / 2.0
            d = abs(ty - fy) * 1.5 + abs(tx - fx)
            if best is None or d < best[0]:
                best = (d, t.get("id"))
        if best:
            f["anchor_element_id"] = best[1]
            f["anchor_distance"] = float(round(best[0], 3))

    # quick summary: prefer the topmost text (heading-ish), fallback to first table
    top_text = next((e for e in enriched if e.get("kind") == "text" and e.get("summary")), None)
    first_table = next((e for e in enriched if e.get("kind") == "table" and e.get("summary")), None)
    qs = " | ".join(
        [s for s in [top_text.get("summary", "") if top_text else "", first_table.get("summary", "") if first_table else ""] if s]
    )

    # Columns expressed in grid units for downstream uniformity
    grid_cols: list[dict[str, int]] = []
    for idx, (cx0, cx1) in enumerate(columns):
        gb = _grid_bbox([cx0, page_bbox[1], cx1, page_bbox[3]], page_bbox, grid)
        grid_cols.append({"id": idx, "x0": gb["x0"], "x1": gb["x1"]})

    # Stats and contract
    pages_present = sorted({int(e.get("page", page_index)) for e in enriched})
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "grid": grid,
        "grid_contract": {"cell": "half-open", "rounding": "floor/ceil", "eps": 1e-6},
        "columns": grid_cols,
        "elements": [
            {k: v for k, v in e.items() if k not in ("bbox",)} | {"grid_bbox": e["grid_bbox"]}
            for e in enriched
        ],
        # Keep original bboxes for audit
        "elements_original_bbox": [
            {"id": e.get("id"), "bbox": e.get("bbox")}
            for e in enriched
        ],
        "page_breaks": pages_present,
        "quick_summary": qs,
    }
    if include_flow:
        result["flow_stream"] = _build_flow_stream(result["elements"], grid_cols, exclude_header_footer=True, place_floats=place_floats)
    return result


def _build_section_sketch_llm(
    sec: dict[str, Any],
    base_results_dir: Path,
    *,
    grid: int = GRID,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """Optional VLM-assisted layout sketch using scillm on the section visual.

    - Uses scillm.completion with explicit x-api-key (no Bearer) for Chutes.
    - Model: STAGE06B_VLM_MODEL or LITELLM_LARGE_VLLM_MODEL or LITELLM_VLM_MODEL.
    - Returns a dict with keys {grid,elements,quick_summary} or None on failure.
    """
    try:
        import json as _json
        import os

        from extractor.pipeline.utils.model_params import image_file_to_data_url

        base = os.getenv("CHUTES_API_BASE", "").strip()
        key = os.getenv("CHUTES_API_KEY", "").strip()
        if not (base and key):
            return None
        # Single-source VLM model only
        from extractor.pipeline.utils.model_select import get_vlm_model
        model = get_vlm_model()
        if not model:
            return None
        # Resolve visual path; require an image to attach
        vrel = sec.get("visual_path")
        if not vrel:
            return None
        vpath = (base_results_dir / vrel).resolve()
        if not vpath.exists():
            return None
        data_url = image_file_to_data_url(vpath)
        sys_prompt = (
            "You analyze a PDF section image and return a STRICT JSON layout sketch. "
            "No prose, no code fences. Grid is an integer (default 12). Elements is an array of objects: "
            "{kind: 'text'|'table'|'figure', grid_bbox:{x0:int,y0:int,x1:int,y1:int}, summary:string}."
        )
        user_text = (
            f"Return only this JSON: {{grid:int,elements:[{{kind:'text'|'table'|'figure',grid_bbox:{{x0:int,y0:int,x1:int,y1:int}},summary:string}}],quick_summary:string}}. "
            f"Use grid={grid}. Clamp grid_bbox to [0,{grid}]."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        from scillm import acompletion as sc_acompletion
        resp = asyncio.run(sc_acompletion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=base,
            api_key=None,
            extra_headers={"x-api-key": key},
            messages=messages,
            response_format={"type":"json_object"},
            temperature=0,
            timeout=timeout,
        ))
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            return None
        out = _json.loads(content)
        if not isinstance(out, dict) or "elements" not in out:
            return None
        # Enrich LLM result with schema and contract to align with deterministic path
        if isinstance(out, dict):
            out.setdefault("schema_version", SCHEMA_VERSION)
            out.setdefault("grid_contract", {"cell": "half-open", "rounding": "floor/ceil", "eps": 1e-6})
        return out
    except Exception:
        return None


def run(input_path: str, output_path: str, **kwargs) -> dict[str, Any]:
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
    sketches: dict[str, Any] = {"sections": {}}
    for sec in sections:
        sid = str(sec.get("id"))
        # Try VLM-assisted sketch first when CHUTES_* and a VLM model are set; else use deterministic
        vlm = _build_section_sketch_llm(sec, base, grid=GRID) or _build_section_sketch(sec, GRID)
        sketches["sections"][sid] = vlm

    out_dir = base / "06b_layout_sketcher" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "06b_layout_sketch.json").write_text(json.dumps(sketches, ensure_ascii=False, indent=2))
    return sketches


## CLI removed: call run(...) or main(...) from Python.
def main(
    results_dir: Path = typer.Option("data/results/pipeline", "-o", help="Results dir"),
    grid: int = typer.Option(GRID, "--grid", min=4, max=64, help="Grid granularity (NxN)"),
    summary_limit: int = typer.Option(80, "--summary-limit", min=16, max=400, help="Max chars for element summaries"),
    flow_text: bool = typer.Option(False, "--flow-text", help="Also emit flow_stream *.txt files"),
    min_gap_ratio: float = typer.Option(0.04, "--min-gap-ratio", help="Column gap fraction (0–1)"),
    header_footer_band: float = typer.Option(0.05, "--header-footer-band", help="Top/bottom band as fraction (0–0.2)"),
    place_floats: str = typer.Option("inline", "--place-floats", help="Float placement in flow: inline|sidebar|append"),
) -> None:
    # Run and, if generated deterministically, re-map grid/summary settings by rebuilding per-section
    run(str(results_dir), str(results_dir))
    # If caller requested non-default grid or summary_limit, rebuild deterministic sections in-memory and write file back
    if True:  # Always rebuild deterministically with requested knobs for predictability
        base = Path(results_dir)
        sec_json = base / "04_section_builder" / "json_output" / "04_sections.json"
        if sec_json.exists():
            data = json.loads(sec_json.read_text(encoding="utf-8"))
            sections = data.get("sections") or []
            rebuilt: dict[str, Any] = {"sections": {}}
            for sec in sections:
                sid = str(sec.get("id"))
                sketch = _build_section_sketch(
                    sec,
                    grid,
                    summary_limit=summary_limit,
                    min_gap_ratio=min_gap_ratio,
                    header_footer_band=header_footer_band,
                    place_floats=place_floats,
                    include_flow=True,
                )
                rebuilt["sections"][sid] = sketch
                if flow_text and isinstance(sketch.get("flow_stream"), str):
                    txt_dir = base / "06b_layout_sketcher" / "text_output"
                    txt_dir.mkdir(parents=True, exist_ok=True)
                    (txt_dir / f"flow_{sid}.txt").write_text(sketch["flow_stream"], encoding="utf-8")
            out_dir = base / "06b_layout_sketcher" / "json_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "06b_layout_sketch.json").write_text(
                json.dumps(rebuilt, ensure_ascii=False, indent=2)
            )


if __name__ == "__main__":
    app()
