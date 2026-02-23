#!/usr/bin/env python3
"""
Deprecated: Generate JSON vs Camelot (litellm). Extractor is SciLLM-only; keep as no-op.

Steps
- Prefer a synthetic table PDF fixture (vector grid with text) for determinism; fall back to project PDFs
- Find a table via Camelot (lattice -> stream)
- Render that page with PyMuPDF, crop a 20% expanded bbox around the table
- Send the crop to litellm_call (gemini/gemini-2.5-flash) with the strict schema prompt
- Compare LLM JSON vs Camelot df: columns similarity and non-empty data
- Save artifacts: crop PNG and JSON report with both results and pass/fail status

Run
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  python scripts/smokes/generate_json_vs_camelot.py
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import camelot
import fitz  # PyMuPDF
from dotenv import load_dotenv, find_dotenv
from PIL import Image


print("SKIP: generate_json_vs_camelot smoke deprecated (SciLLM-only)")
raise SystemExit(0)


# Optional synthetic PDF generator (reportlab). If unavailable, skip.
def _maybe_generate_synthetic_pdf(path: Path, rows: int = 6, cols: int = 5) -> bool:
    try:
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.pagesizes import letter  # type: ignore
    except Exception:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    margin = 50
    table_w = width - 2 * margin
    table_h = height - 2 * margin
    cell_w = table_w / cols
    cell_h = table_h / rows
    # grid
    c.setLineWidth(1)
    for i in range(cols + 1):
        x = margin + i * cell_w
        c.line(x, margin, x, margin + table_h)
    for j in range(rows + 1):
        y = margin + j * cell_h
        c.line(margin, y, margin + table_w, y)
    # headers
    c.setFont("Helvetica-Bold", 10)
    for i in range(cols):
        tx = margin + i * cell_w + 5
        ty = margin + table_h - cell_h + cell_h / 2 - 4
        c.drawString(tx, ty, f"Col {i+1}")
    # data
    c.setFont("Helvetica", 10)
    for r in range(1, rows):
        for i in range(cols):
            tx = margin + i * cell_w + 5
            ty = margin + table_h - (r + 1) * cell_h + cell_h / 2 - 4
            c.drawString(tx, ty, f"R{r}C{i+1}")
    c.showPage()
    c.save()
    return True


def _expand_bbox(
    bbox: tuple[float, float, float, float], factor: float, page_w: float, page_h: float
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    w = (x2 - x1) * factor
    h = (y2 - y1) * factor
    nx1 = max(0.0, cx - w / 2)
    ny1 = max(0.0, cy - h / 2)
    nx2 = min(page_w, cx + w / 2)
    ny2 = min(page_h, cy + h / 2)
    return nx1, ny1, nx2, ny2


def _crop_pixmap_to_pil(pix: fitz.Pixmap, rect: fitz.Rect) -> Image.Image:
    # Crop via PIL in pixel space
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    left = max(0, int(rect.x0))
    top = max(0, int(rect.y0))
    right = min(pix.width, int(rect.x1))
    bottom = min(pix.height, int(rect.y1))
    return img.crop((left, top, right, bottom))


async def run() -> Dict[str, Any]:
    load_dotenv(find_dotenv())

    synthetic = Path("tests/fixtures/synthetic_table.pdf")
    if not synthetic.exists():
        _maybe_generate_synthetic_pdf(synthetic)
    candidates = [
        synthetic,
        Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
        Path("data/input/pipeline/BHT_CV32A65X_marked_with_requirements.pdf"),
        Path("data/input/pipeline/qb50_system_requirements_and_recommendations_marked.pdf"),
        Path("data/input/pipeline/qb50_1_14.pdf"),
    ]

    found: Optional[Dict[str, Any]] = None
    pdf_path: Optional[Path] = None
    for cp in candidates:
        if not cp.exists():
            continue
        max_pages = 1 if cp == synthetic else 10
        for page in range(1, max_pages + 1):
            try:
                tables = camelot.read_pdf(str(cp), pages=str(page), flavor="lattice")
            except Exception:
                tables = None
            if (not tables) or (tables.n == 0):
                try:
                    tables = camelot.read_pdf(str(cp), pages=str(page), flavor="stream")
                except Exception:
                    tables = None
            if not tables or tables.n == 0:
                continue
            pick = None
            for t in tables:
                df = getattr(t, "df", None)
                bbox = getattr(t, "_bbox", None) or getattr(t, "bbox", None)
                if df is None or bbox is None:
                    continue
                rows, cols = int(df.shape[0]), int(df.shape[1])
                header = list(df.iloc[0]) if rows >= 1 else []
                nonempty = sum(1 for x in header if str(x).strip())
                if rows >= 2 and cols >= 2 and nonempty >= max(1, cols // 2):
                    pick = (df, bbox)
                    break
            if pick:
                found = {"page": page, "df": pick[0], "bbox": pick[1]}
                pdf_path = cp
                break
        if found:
            break
    if not found or pdf_path is None:
        return {"ok": False, "error": "no_table_found"}

    page_num = int(found["page"])  # 1-based
    df = found["df"]
    bbox = tuple(found["bbox"])  # (x1, y1, x2, y2) in PDF coords (origin bottom-left)

    # Render page and crop
    zoom = 3.0
    doc = fitz.open(str(pdf_path))
    page = doc[page_num - 1]
    page_w, page_h = page.rect.width, page.rect.height

    # Expand bbox by 20%
    ex = _expand_bbox(bbox, 1.2, page_w, page_h)
    # Convert PDF coords (origin bottom-left) -> image coords (origin top-left)
    x1, y1, x2, y2 = ex
    top = page_h - y2
    left = x1
    bottom = page_h - y1
    right = x2

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    # Scale bbox to pixel space
    rect_px = fitz.Rect(left * zoom, top * zoom, right * zoom, bottom * zoom)
    crop_img = _crop_pixmap_to_pil(pix, rect_px).convert("RGBA")
    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    ts_img = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
    crop_path = artifacts / f"camelot_llm_crop_{ts_img}.png"
    crop_img.save(crop_path)
    buf = io.BytesIO()
    crop_img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"

    # LLM call
    prompt = (
        "You are an expert table extractor. Given an image of a table from a PDF, return ONLY a strict JSON object with EXACT keys and types:\n\n"
        "{\n"
        '  "title": string,            // concise title; if inferred, prefix with INFERRED_\n'
        '  "columns": string[],        // header cells as strings\n'
        '  "data": string[][]          // row-major 2D array of cell text\n'
        "}\n\n"
        "Rules:\n- Respond with a single JSON object only (no markdown, no code fences, no commentary).\n- Do not include any extra keys.\n- Normalize whitespace; keep cell contents as plain strings.\n- Extract all visible rows beneath the header; do NOT return an empty data array if rows are present."
    )
    params = {
        "model": os.getenv("LITELLM_DEFAULT_MODEL", "gemini/gemini-2.5-flash"),
        "text": prompt,
        "image": data_url,
    }
    results = await litellm_call(
        [params],
        wrap_json=True,
        response_format="json_object",
        desc="LLM vs Camelot",
        show_progress=False,
        concurrency=1,
        request_timeout=45,
    )
    out = results[0] if results else ""

    if isinstance(out, str):
        try:
            obj = json.loads(out)
        except Exception as e:
            return {"ok": False, "error": f"non_json_output: {e}", "raw": out[:1000]}
    else:
        content = getattr(out, "content", None)
        if isinstance(content, str):
            try:
                obj = json.loads(content)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"non_json_output: {e}",
                    "raw": (content or "")[:1000],
                }
        else:
            return {"ok": False, "error": "empty_output"}

    # Basic comparison: column count and shape
    try:
        cols_llm = obj.get("columns") or []
        data_llm = obj.get("data") or []
        cols_cam = list(df.iloc[0]) if len(df) > 0 else []
        # Basic checks
        ok_cols = isinstance(cols_llm, list) and (len(cols_llm) >= 1)
        ok_data = isinstance(data_llm, list) and (len(data_llm) >= 1)
        # Compare column counts roughly (within +/- 2), filter empty Camelot headers
        cols_cam_ne = [c for c in cols_cam if str(c).strip()]
        similar_cols = abs(len(cols_llm) - len(cols_cam_ne)) <= 2
        ok = ok_cols and ok_data and similar_cols
        return {
            "ok": bool(ok),
            "camelot": {
                "pdf": str(pdf_path),
                "page": page_num,
                "bbox": bbox,
                "columns_inferred": cols_cam[:10],
                "rows": int(df.shape[0]),
                "cols": int(df.shape[1]),
            },
            "llm": obj,
            "crop": str(crop_path),
        }
    except Exception as e:
        return {"ok": False, "error": f"compare_failed: {e}"}


def main() -> int:
    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run())
    ts = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
    out_path = out_dir / f"generate_json_vs_camelot_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artifact: {out_path}")
    if report.get("ok"):
        print("generate_json_vs_camelot: OK")
        return 0
    else:
        print("generate_json_vs_camelot: FAIL", report.get("error") or "unknown")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
