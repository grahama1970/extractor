#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "streamlit>=1.37.0",
#   "pymupdf>=1.24.2",
#   "Pillow>=10.3.0",
# ]
# ///

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import fitz
import streamlit as st
from PIL import Image, ImageDraw


@dataclass
class Box:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    label: str
    idx: int


def load_png(pdf: Path, page: int, dpi: int = 144) -> Image.Image:
    d = fitz.open(pdf)
    try:
        p = d.load_page(page)
        zoom = dpi / 72
        pm = p.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
    finally:
        d.close()


def draw_boxes(img: Image.Image, boxes: Iterable[Box], color=(255, 0, 0)) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    scale = 144 / 72
    for b in boxes:
        x0, y0, x1, y1 = int(b.x0 * scale), int(b.y0 * scale), int(b.x1 * scale), int(b.y1 * scale)
        draw.rectangle([x0, y0, x1, y1], outline=color, width=3)
        if b.label:
            tw, th = draw.textsize(b.label)
            bg = (0, 0, 0)
            draw.rectangle([x0, max(0, y0 - th - 4), x0 + tw + 6, y0], fill=bg)
            draw.text((x0 + 3, y0 - th - 2), b.label, fill=(255, 255, 255))
    return out


def load_stage(step: str, out_root: Path) -> tuple[Path, List[Box]]:
    if step == "02":
        p = out_root / "02_marker_extractor/json_output/02_marker_blocks.json"
        data = json.loads(p.read_text())
        boxes = []
        for i, b in enumerate(data.get("blocks", [])):
            bbox = b.get("bbox") or b.get("bbox0")
            if not bbox:
                continue
            boxes.append(
                Box(
                    page=int(b.get("page_idx", 0)),
                    x0=bbox[0],
                    y0=bbox[1],
                    x1=bbox[2],
                    y1=bbox[3],
                    label=b.get("block_type", "block"),
                    idx=i,
                )
            )
        return p, boxes
    if step == "05":
        p = out_root / "05_table_extractor/json_output/05_tables.json"
        data = json.loads(p.read_text())
        boxes = []
        for i, t in enumerate(data.get("tables", [])):
            bbox = t.get("bbox")
            if not bbox:
                continue
            boxes.append(
                Box(
                    page=int(t.get("page_idx", 0)),
                    x0=bbox[0],
                    y0=bbox[1],
                    x1=bbox[2],
                    y1=bbox[3],
                    label=t.get("title") or "table",
                    idx=i,
                )
            )
        return p, boxes
    if step == "06":
        p = out_root / "06_figure_extractor/json_output/06_figures.json"
        data = json.loads(p.read_text())
        boxes = []
        for i, f in enumerate(data.get("figures", [])):
            bbox = f.get("bbox")
            if not bbox:
                continue
            lbl = f.get("title") or f.get("inferred_title") or "figure"
            boxes.append(
                Box(
                    page=int(f.get("page_idx", 0)),
                    x0=bbox[0],
                    y0=bbox[1],
                    x1=bbox[2],
                    y1=bbox[3],
                    label=lbl,
                    idx=i,
                )
            )
        return p, boxes
    raise ValueError("Unsupported step: " + step)


def save_corrections(pdf: Path, step: str, corrections: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{pdf.stem}_{step}_corrections.json"
    out = out_dir / name
    out.write_text(
        json.dumps({"pdf": str(pdf), "step": step, "corrections": corrections}, indent=2)
    )
    return out


def main():
    st.set_page_config(page_title="Visual Review", layout="wide")
    pdf = Path(
        st.sidebar.text_input(
            "PDF path", "data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"
        )
    )
    out_root = Path(st.sidebar.text_input("Pipeline out root", "data/results/pipeline"))
    step = st.sidebar.selectbox("Step", ["02", "05", "06"], index=1)
    dpi = st.sidebar.slider("Render DPI", 100, 200, 144, step=4)

    if not pdf.exists() or not out_root.exists():
        st.warning("Set valid PDF and pipeline output paths.")
        return

    json_path, boxes = load_stage(step, out_root)
    pages = sorted({b.page for b in boxes})
    page = st.sidebar.selectbox("Page", pages, index=0)

    page_boxes = [b for b in boxes if b.page == page]
    img = load_png(pdf, page, dpi=dpi)
    st.image(draw_boxes(img, page_boxes), caption=f"Step {step} page {page}")

    st.markdown("### Edit labels / offsets (pixels at 144dpi)")
    updated: list[dict] = []
    for b in page_boxes:
        with st.expander(f"{b.idx}: {b.label}"):
            new_label = st.text_input(f"label_{b.idx}", b.label)
            dx = st.number_input(f"dx_{b.idx}", value=0, step=1)
            dy = st.number_input(f"dy_{b.idx}", value=0, step=1)
            dw = st.number_input(f"dw_{b.idx}", value=0, step=1)
            dh = st.number_input(f"dh_{b.idx}", value=0, step=1)
            updated.append(
                {
                    "idx": b.idx,
                    "page": b.page,
                    "label": new_label,
                    "dx": dx,
                    "dy": dy,
                    "dw": dw,
                    "dh": dh,
                }
            )

    if st.button("Save corrections"):
        out = save_corrections(pdf, step, updated, Path("scripts/artifacts/corrections"))
        st.success(f"Saved: {out}")


if __name__ == "__main__":
    main()
