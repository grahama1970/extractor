#!/usr/bin/env python3
"""
Stage 06 — Figure Extractor (Deterministic)

Contract:
- Inputs: Stage 02 blocks (Figure/Image), Stage 04 sections, cleaned PDF path, output dir.
- For each figure block:
  - Crop region (small vertical padding), save image to visual_output/.
  - Collect text bands immediately above/below + nearby text for context.
  - Map to section if bbox intersects.
- Output: writes 06_figure_extractor/json_output/06_figures.json.

NOTE: This stage is purely deterministic (no LLM/VLM calls).
VLM description/title inference is performed by Stage 06b (figure_describer).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import find_dotenv, load_dotenv
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
from rich.console import Console

from extractor.pipeline.utils.figure_extractor_utils import (
    _expand_bbox,
    _save_image_bytes,
    _bbox_area,
    _normalize_title,
    _assemble_result,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity

# Load environment (project standard). Does not override existing env vars.
load_dotenv(find_dotenv())

console = Console()
STEP_NAME = "06_figure_extractor"


def sanity() -> int:
    """Return sanity check result."""
    return run_step_sanity(STEP_NAME)


# Tunables (env‑driven)
VERTICAL_PADDING_RATIO = float(os.getenv("FIGURE_VERTICAL_PADDING", "0.2"))
CONCURRENCY = int(os.getenv("STAGE06_CONCURRENCY", "6"))
BAND_ABOVE_PX = int(os.getenv("STAGE06_BAND_ABOVE_PX", "120"))
BAND_BELOW_PX = int(os.getenv("STAGE06_BAND_BELOW_PX", "140"))
FIGURE_MIN_AREA = int(os.getenv("FIGURE_MIN_AREA_PX", "5000"))


# ------------------------------------------------------------------
# pdf_oxide engine helpers
# ------------------------------------------------------------------


def _band_texts_oxide(doc, page_idx: int, bbox: list[float]) -> tuple[str, str]:
    """Extract text from bands above/below a bbox using pdf_oxide."""
    w, h = doc.page_dimensions(page_idx)
    x0, y0, x1, y1 = bbox

    # Above band
    above_rect = (x0, max(0, y0 - BAND_ABOVE_PX), x1, y0)
    below_rect = (x0, y1, x1, min(h, y1 + BAND_BELOW_PX))

    def collect_oxide(rect):
        spans = doc.extract_spans_in_rect(page_idx, rect)
        texts = [s["text"].strip() for s in spans if s.get("text", "").strip()]
        return " ".join(texts)

    return collect_oxide(above_rect), collect_oxide(below_rect)


def _nearby_text_oxide(doc, page_idx: int, bbox: list[float]) -> str:
    """Extract text from a bounding box region using pdf_oxide."""
    spans = doc.extract_spans_in_rect(page_idx, tuple(bbox))
    return " ".join(s["text"].strip() for s in spans if s.get("text", "").strip())


def _render_region_oxide(doc, page_idx: int, bbox: list[float], dpi: int = 144) -> bytes:
    """Render a page region using pdf_oxide's clipped rendering."""
    return bytes(doc.render_page_clipped(page_idx, tuple(bbox), dpi=dpi))


async def _process_one_oxide(
    *,
    doc,
    block: dict[str, Any],
    figure_id: str,
    image_output_dir: Path,
) -> dict[str, Any] | None:
    """Process a figure block using pdf_oxide engine."""
    try:
        page_num = int(block.get("page_idx", 0))
        w, h = doc.page_dimensions(page_num)

        bbox0 = block.get("bbox") or [50.0, 100.0, w - 50, h - 100]
        if bbox0 == [0, 0, 0, 0]:
            bbox0 = [50.0, 100.0, w - 50, h - 100]

        area = _bbox_area(bbox0)
        if area < FIGURE_MIN_AREA:
            return None
        max_area = int(os.getenv("FIGURE_MAX_AREA_PX", "0"))
        if max_area > 0 and area > max_area:
            return None

        expanded_bbox = _expand_bbox(bbox0, h, VERTICAL_PADDING_RATIO)
        image_data = _render_region_oxide(doc, page_num, expanded_bbox)
        img_path = _save_image_bytes(image_output_dir, figure_id, image_data)

        above_text, below_text = _band_texts_oxide(doc, page_num, bbox0)
        nearby_text = _nearby_text_oxide(doc, page_num, expanded_bbox)

        description: Optional[str] = None
        figure_title: Optional[str] = None
        title_source: Optional[str] = None
        number_hint: Optional[str] = None

        number, base_title, normalized_id = _normalize_title(figure_title or number_hint)

        res = _assemble_result(
            figure_id=figure_id,
            page_num=page_num,
            output_dir=image_output_dir.parent,
            img_path=img_path,
            expanded_bbox=expanded_bbox,
            description=description,
            title=figure_title,
            title_source=title_source,
            number=number,
            base_title=base_title,
            normalized_id=normalized_id,
            extraction_time=datetime.now().isoformat(),
        )
        res["context_above"] = above_text
        res["context_below"] = below_text
        res["context_nearby"] = nearby_text
        return res
    except Exception as exc:
        log_stage_error("06_figure_extractor", exc, {"context": "06", "figure_id": figure_id})
        raise


async def _process_all_oxide(
    *,
    pdf_path: Path,
    figure_blocks: list[dict[str, Any]],
    image_output_dir: Path,
) -> list[dict[str, Any]]:
    """Process all figure blocks using pdf_oxide engine."""
    import pdf_oxide

    doc = pdf_oxide.open(str(pdf_path))
    sem = asyncio.Semaphore(max(1, CONCURRENCY))

    async def runner(i: int, blk: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            return await _process_one_oxide(
                doc=doc,
                block=blk,
                figure_id=f"figure_{i+1:03d}",
                image_output_dir=image_output_dir,
            )

    tasks = []
    out: list[dict[str, Any]] = []
    for i, blk in enumerate(figure_blocks):
        tasks.append(asyncio.create_task(runner(i, blk)))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"figure.task.error idx={i} err={res}")
            continue
        if res:
            out.append(res)

    try:
        logs_dir = image_output_dir.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(out):
            if not isinstance(r, dict):
                continue
            (logs_dir / f"figure_{i+1:03d}.summary.json").write_text(
                json.dumps(
                    {
                        "id": r.get("figure_id"),
                        "has_title": bool(r.get("title")),
                        "has_description": bool(r.get("ai_description")),
                        "title_source": r.get("title_source"),
                    },
                    indent=2,
                )
            )
    except Exception as exc:
        logger.warning(f"Failed to write figure summaries: {exc}")
    return out




def _rects_intersect(a: list, b: list) -> bool:
    """Pure-Python AABB intersection check (no fitz dependency)."""
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def _intersect_sections_simple(figures: list[dict], sections: list[dict]) -> None:
    """Attach section_id to figures using pure-Python rect intersection."""
    for figure in figures:
        bbox = figure.get("bbox")
        page = figure.get("page")
        if not bbox or page is None:
            continue
        for s in sections:
            ps = s.get("page_start")
            pe = s.get("page_end")
            sb = s.get("bbox")
            if ps is None or pe is None or sb is None:
                continue
            if ps <= page <= pe and _rects_intersect(bbox, sb):
                figure["section_id"] = s.get("id", "unknown")
                break


def run(
    stage_02_json: Optional[Path] = None,
    stage_04_json: Optional[Path] = None,
    pdf_dir: Optional[Path] = None,
    output_dir: Path = Path("data/results/pipeline"),
    bundle: Optional[Path] = None,
    preset_config: Optional[dict[str, Any]] = None,
    engine: Optional[str] = None,
) -> Path:
    """Extract figures, deterministically (image + band texts), write JSON."""

    t0 = time.monotonic()
    # Note: No SciLLM preflight needed here.

    # Load inputs
    if bundle is not None:
        data = json.loads(Path(bundle).read_text())
        stage_02_data = data.get("marker_blocks") or {}
        sections = data.get("sections") or []
        clean_pdf = data.get("clean_pdf") or ""
        if not stage_02_data or not clean_pdf:
            raise ValueError("Bundle missing 'marker_blocks' or 'clean_pdf'")
        pdf_path = Path(clean_pdf)
        label = Path(bundle).name
    else:
        if not (stage_02_json and stage_04_json and pdf_dir):
            raise ValueError("Provide stage_02_json, sections json, and pdf_dir, or pass bundle")
        if not stage_02_json.exists() or not stage_04_json.exists():
            raise FileNotFoundError("Input JSON not found")
        stage_02_data = json.loads(stage_02_json.read_text())
        sections = json.loads(stage_04_json.read_text()).get("sections", [])
        try:
            pdf_path = next(pdf_dir.glob("*_clean.pdf"))
        except StopIteration:
            raise FileNotFoundError("No '*_clean.pdf' found in pdf_dir")
        label = stage_02_json.name

    blocks = [
        b
        for b in stage_02_data.get("blocks", [])
        if b.get("block_type") in ("Figure", "Image", "Picture")
    ]

    # Output dirs
    stage_dir = output_dir / "06_figure_extractor"
    json_dir = stage_dir / "json_output"
    img_dir = stage_dir / "visual_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"stage06:start pdf={pdf_path} blocks={len(blocks)} label={label}")
    # Configure a stage-specific log file for debugging
    try:
        logger.add(
            str(stage_dir / "stage_06_figure_extractor.log"),
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception as exc:
        log_stage_error("06_figure_extractor", exc, {"context": "06", "step": "logger_setup"})
        raise

    figures: list[dict[str, Any]] = []
    if blocks:
        figures = asyncio.run(
            _process_all_oxide(pdf_path=pdf_path, figure_blocks=blocks, image_output_dir=img_dir)
        )

    # Map to sections
    if figures and sections:
        _intersect_sections_simple(figures, sections)

    result = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(stage_02_json) if stage_02_json else str(bundle),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "figure_count": len(figures),
        "figures": figures,
    }

    out_path = json_dir / "06_figures.json"
    # Minimal schema validation
    try:
        for f in result.get("figures", []):
            assert isinstance(f.get("bbox"), (list, tuple)) and len(f.get("bbox")) == 4
            # accept page or page_idx
            _ = f.get("page_idx") if "page_idx" in f else f.get("page")
    except Exception as exc:
        log_stage_error("06_figure_extractor", exc, {"context": "06", "step": "schema_validation"})
        raise

    out_path.write_text(json.dumps(result, indent=2))

    console.print(
        f"stage06:done out={out_path} duration_ms={int((time.monotonic()-t0)*1000)} count={len(figures)}"
    )
    # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
    return out_path


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 06: Figure Extractor")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    parser.add_argument("--pdf-dir", type=Path, help="Dir containing input PDF")
    parser.add_argument("--engine", choices=["pymupdf", "pdf_oxide"], default=None)
    args = parser.parse_args()

    pipeline_dir = args.pipeline_dir

    try:
        logger.info("Running Stage 06...")
        stage_02 = pipeline_dir / "02_marker_extractor/json_output/02_marker_blocks.json"
        stage_04 = pipeline_dir / "04_section_builder/json_output/04_sections.json"

        if not stage_02.exists() or not stage_04.exists():
            logger.error("Missing input dependencies (S02 or S04)")
            sys.exit(1)

        # Locate PDF
        # If --pdf-dir is provided, use it. Otherwise, look in S01.
        pdf_dir = args.pdf_dir
        if not pdf_dir:
            s01_dir = pipeline_dir / "01_annotation_processor"
            if s01_dir.exists():
                pdf_dir = s01_dir

        if not pdf_dir:
            logger.error("--pdf-dir required for execution (or S01 output must exist)")
            sys.exit(1)

        run(
            stage_02_json=stage_02, stage_04_json=stage_04, pdf_dir=pdf_dir,
            output_dir=pipeline_dir, engine=args.engine,
        )

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
