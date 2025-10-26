#!/usr/bin/env python3
"""
Stage 06 — Figure Extractor (lean)

Contract (simple, debugger‑friendly):
- Inputs: Stage 02 blocks (Figure/Image), Stage 04 sections, cleaned PDF path, output dir.
- For each figure block:
  - Crop region (small vertical padding), save image to image_output/.
  - Collect text bands immediately above/below + nearby text.
  - Single SciLLM multimodal call (image + texts) → JSON {description, title, source, number}.
  - Normalize title/number; map to section if bbox intersects; append record.
- Output: writes 06_figure_extractor/json_output/06_figures.json.

SciLLM-only. No httpx/litellm fallbacks. Minimal logs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import fitz  # PyMuPDF
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from rich.console import Console
from scillm import acompletion

from extractor.pipeline.utils.figure_extractor_utils import (
    _estimate_bbox,
    _expand_bbox,
    _render_region,
    _save_image_bytes,
    _nearby_text,
    _bbox_area,
    _normalize_title,
    _assemble_result,
    intersect_sections,
)

# Load environment (project standard). Does not override existing env vars.
load_dotenv(find_dotenv())

console = Console()


# Tunables (env‑driven)
VERTICAL_PADDING_RATIO = float(os.getenv("FIGURE_VERTICAL_PADDING", "0.2"))
CONCURRENCY = int(os.getenv("STAGE06_CONCURRENCY", "6"))
BAND_ABOVE_PX = int(os.getenv("STAGE06_BAND_ABOVE_PX", "120"))
BAND_BELOW_PX = int(os.getenv("STAGE06_BAND_BELOW_PX", "140"))
VLM_TIMEOUT_SEC = float(os.getenv("STAGE06_VLM_TIMEOUT_SEC", "25"))
FIGURE_MIN_AREA = int(os.getenv("FIGURE_MIN_AREA_PX", "5000"))
FIGURE_DESC_ENABLED = os.getenv("FIGURE_DESC", "1").lower() in {"1", "true", "yes"}


def _band_texts(page: fitz.Page, bbox: list[float]) -> tuple[str, str]:
    rr = fitz.Rect(*bbox)
    band_above = fitz.Rect(rr.x0, max(0, rr.y0 - BAND_ABOVE_PX), rr.x1, rr.y0)
    band_below = fitz.Rect(rr.x0, rr.y1, rr.x1, min(page.rect.height, rr.y1 + BAND_BELOW_PX))

    def collect(clip_rect: fitz.Rect) -> str:
        blks = page.get_text("blocks", clip=clip_rect)
        return " ".join((b[4] or "").strip() for b in blks if (b[4] or "").strip())

    return collect(band_above), collect(band_below)


async def _describe_and_title_multimodal(
    *,
    image_data: bytes,
    text_above: str,
    text_below: str,
    nearby_text: str,
) -> dict[str, Optional[str]]:
    base = os.getenv("CHUTES_API_BASE", "").strip()
    key = os.getenv("CHUTES_API_KEY", "").strip()
    model = (os.getenv("CHUTES_VLM_MODEL") or "").strip()
    if not (base and key and model):
        return {}

    b64 = base64.b64encode(image_data).decode("utf-8")
    system = (
        "You assist PDF figure extraction. Return strict JSON only with keys: "
        "description (2–3 sentences), title (<=10 words, no 'Figure' prefix), "
        "source ('above'|'below'|'context'|'unknown'), number (optional)."
    )
    user_parts: list[Any] = [
        {
            "type": "text",
            "text": (
                "Text above (may contain caption):\n" + (text_above or "")[:600]
                + "\n\nText below (may contain caption):\n" + (text_below or "")[:600]
                + "\n\nNearby text on page:\n" + (nearby_text or "")[:800]
            ),
        },
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]

    try:
        resp = await acompletion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=base,
            api_key=None,
            extra_headers={"x-api-key": key},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_parts}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=220,
            timeout=VLM_TIMEOUT_SEC,
        )
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, dict):
            obj = content
        else:
            # If a string slipped through, accept it as raw JSON
            obj = json.loads(content) if content else {}
        return {
            "description": (obj or {}).get("description"),
            "title": (obj or {}).get("title"),
            "source": (obj or {}).get("source"),
            "number": (obj or {}).get("number"),
        }
    except Exception as e:
        logger.warning(f"multimodal.describe_title.error err={e}")
        return {}


async def _process_one(
    *,
    doc: fitz.Document,
    block: dict[str, Any],
    figure_id: str,
    image_output_dir: Path,
    skip_descriptions: bool,
) -> dict[str, Any] | None:
    try:
        page_num = int(block.get("page_idx", 0))
        page = doc[page_num]

        bbox0 = block.get("bbox") or _estimate_bbox(page, block)
        expanded_bbox = _expand_bbox(bbox0, page.rect.height, VERTICAL_PADDING_RATIO)

        image_data = _render_region(page, expanded_bbox)
        img_path = _save_image_bytes(image_output_dir, figure_id, image_data)

        above_text, below_text = _band_texts(page, bbox0)
        nearby_text = _nearby_text(page, expanded_bbox)

        description = "Description skipped (offline)"
        figure_title: Optional[str] = None
        title_source: Optional[str] = None
        number_hint: Optional[str] = None

        if FIGURE_DESC_ENABLED and not skip_descriptions and _bbox_area(expanded_bbox) >= FIGURE_MIN_AREA:
            meta = await _describe_and_title_multimodal(
                image_data=image_data, text_above=above_text, text_below=below_text, nearby_text=nearby_text
            )
            if meta:
                if isinstance(meta.get("description"), str):
                    description = meta["description"].strip() or description
                if isinstance(meta.get("title"), str):
                    figure_title = meta["title"].strip() or None
                if isinstance(meta.get("source"), str):
                    title_source = meta["source"].strip() or None
                if isinstance(meta.get("number"), str):
                    number_hint = meta["number"].strip() or None

        number, base_title, normalized_id = _normalize_title(figure_title or number_hint)

        return _assemble_result(
            figure_id=figure_id,
            page_num=page_num,
            output_dir=image_output_dir.parent,  # stage dir; utils computes relative path from parent.parent
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
    except Exception as e:
        logger.error(f"figure.extract.error id={figure_id} err={e}")
        return None


async def _process_all(
    *,
    pdf_path: Path,
    figure_blocks: list[dict[str, Any]],
    image_output_dir: Path,
    skip_descriptions: bool,
) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(max(1, CONCURRENCY))

    async def runner(i: int, blk: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            return await _process_one(
                doc=doc, block=blk, figure_id=f"figure_{i+1:03d}", image_output_dir=image_output_dir, skip_descriptions=skip_descriptions
            )

    tasks = []
    doc = fitz.open(str(pdf_path))
    try:
        for i, blk in enumerate(figure_blocks):
            tasks.append(asyncio.create_task(runner(i, blk)))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[dict[str, Any]] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"figure.task.error idx={i} err={res}")
                continue
            if res:
                out.append(res)
        return out
    finally:
        doc.close()


## section intersection moved to utils.intersect_sections


def run(
    stage_02_json: Optional[Path] = None,
    stage_04_json: Optional[Path] = None,
    pdf_dir: Optional[Path] = None,
    output_dir: Path = Path("data/results/pipeline"),
    bundle: Optional[Path] = None,
    skip_descriptions: bool = False,
) -> Path:
    """Extract figures, call SciLLM once per figure (image + band texts), write JSON."""
    import time

    t0 = time.monotonic()

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

    blocks = [b for b in stage_02_data.get("blocks", []) if b.get("block_type") in ("Figure", "Image")]

    # Output dirs
    stage_dir = output_dir / "06_figure_extractor"
    json_dir = stage_dir / "json_output"
    img_dir = stage_dir / "image_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"stage06:start pdf={pdf_path} blocks={len(blocks)} label={label}")

    figures: list[dict[str, Any]] = []
    if blocks:
        figures = asyncio.run(
            _process_all(pdf_path=pdf_path, figure_blocks=blocks, image_output_dir=img_dir, skip_descriptions=skip_descriptions)
        )

    # Map to sections
    if figures and sections:
        intersect_sections(figures, sections)

    result = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(stage_02_json) if stage_02_json else str(bundle),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "figure_count": len(figures),
        "figures": figures,
    }

    out_path = json_dir / "06_figures.json"
    out_path.write_text(json.dumps(result, indent=2))

    console.print(
        f"stage06:done out={out_path} duration_ms={int((time.monotonic()-t0)*1000)} count={len(figures)}"
    )
    return out_path
