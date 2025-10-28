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
from extractor.pipeline.utils.scillm_router import get_vlm_router
from extractor.pipeline.utils.response_utils import normalize_json_content
from extractor.pipeline.utils.debug_utils import ensure_logs_dir, time_block

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
USE_JSON_CHAT = os.getenv("SCILLM_USE_JSON_CHAT", "").lower() in {"1","true","yes","y"}
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
    router: Any | None = None,
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

    # Router-only (SciLLM). No SDK/curl fallback inside steps.
    router = get_vlm_router()
    # Optional per-call timing: set RUN_RESULTS_DIR to base results dir
    _rd = os.getenv("RUN_RESULTS_DIR")
    if _rd:
        logs_dir = ensure_logs_dir(Path(_rd), "06_figure_extractor")
        with time_block(logs_dir, "figure_vlm", parts=len(user_parts), image=1 if any(isinstance(p, dict) and p.get("type")=="image_url" for p in user_parts) else 0):
            resp = await router.acompletion(
                model="chutes/vlm",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_parts}],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=220,
                timeout=VLM_TIMEOUT_SEC,
            )
    else:
        resp = await router.acompletion(
            model="chutes/vlm",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_parts}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=220,
            timeout=VLM_TIMEOUT_SEC,
        )
    _, obj = normalize_json_content(resp)
    if isinstance(obj, dict):
        return {
            "description": obj.get("description"),
            "title": obj.get("title"),
            "source": obj.get("source"),
            "number": obj.get("number"),
        }
    return {}


async def _process_one(
    *,
    doc: fitz.Document,
    block: dict[str, Any],
    figure_id: str,
    image_output_dir: Path,
    skip_descriptions: bool,
    router: Any | None = None,
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
                image_data=image_data,
                text_above=above_text,
                text_below=below_text,
                nearby_text=nearby_text,
                router=router,
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
    # Router is constructed on demand inside calls (get_vlm_router)
    router = None
    try:
        from extractor.pipeline.utils.scillm_router import get_vlm_router as _rv
        router = _rv()
    except Exception:
        router = None

    async def runner(i: int, blk: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            return await _process_one(
                doc=doc,
                block=blk,
                figure_id=f"figure_{i+1:03d}",
                image_output_dir=image_output_dir,
                skip_descriptions=skip_descriptions,
                router=router,
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
        # Write per-figure summaries for diagnostics
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
        except Exception:
            pass
        return out
    finally:
        doc.close()
        # Ensure router is closed cleanly to avoid aiohttp warnings
        if router is not None:
            try:
                close = getattr(router, "aclose", None) or getattr(router, "close", None)
                if close is not None:
                    maybe = close()
                    if hasattr(maybe, "__await__"):
                        try:
                            import asyncio as _asyncio
                            loop = _asyncio.get_running_loop()
                            # schedule without blocking
                            loop.create_task(maybe)  # type: ignore
                        except RuntimeError:
                            # no running loop, run synchronously
                            import asyncio as _asyncio
                            _asyncio.run(maybe)  # type: ignore
            except Exception:
                pass


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
    # Minimal schema validation
    try:
        for f in result.get("figures", []):
            assert isinstance(f.get("bbox"), (list, tuple)) and len(f.get("bbox")) == 4
            # accept page or page_idx
            _ = f.get("page_idx") if "page_idx" in f else f.get("page")
    except Exception as _e:
        console.print(f"[yellow]Stage 06 schema warning: {_e}[/yellow]")

    out_path.write_text(json.dumps(result, indent=2))

    console.print(
        f"stage06:done out={out_path} duration_ms={int((time.monotonic()-t0)*1000)} count={len(figures)}"
    )
    return out_path


if __name__ == "__main__":
    # Minimal entry: either --bundle BUNDLE_JSON [OUT_DIR] [--skip-descriptions]
    # or STAGE02_JSON STAGE04_JSON PDF_DIR [OUT_DIR] [--skip-descriptions]
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception:
        pass
    import sys
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.06_figure_extractor --bundle BUNDLE [OUT_DIR] [--skip-descriptions]\n"
            "   or: python -m extractor.pipeline.steps.06_figure_extractor STAGE02_JSON STAGE04_JSON PDF_DIR [OUT_DIR] [--skip-descriptions]",
            file=sys.stderr,
        )
        sys.exit(2)
    skip = False
    if "--skip-descriptions" in argv:
        skip = True
        argv = [a for a in argv if a != "--skip-descriptions"]
    kw = {}
    if argv and argv[0] == "--bundle":
        try:
            bundle = Path(argv[1])
        except IndexError:
            print("--bundle requires a path", file=sys.stderr)
            sys.exit(2)
        out_dir = Path(argv[2]) if len(argv) > 2 else Path("data/results/pipeline")
        kw = {"bundle": bundle, "output_dir": out_dir, "skip_descriptions": skip}
    else:
        if len(argv) < 3:
            print("Missing args. See --help.", file=sys.stderr)
            sys.exit(2)
        s02 = Path(argv[0])
        s04 = Path(argv[1])
        pdf_dir = Path(argv[2])
        out_dir = Path(argv[3]) if len(argv) > 3 else Path("data/results/pipeline")
        kw = {
            "stage_02_json": s02,
            "stage_04_json": s04,
            "pdf_dir": pdf_dir,
            "output_dir": out_dir,
            "skip_descriptions": skip,
        }
    out = run(**kw)
    print(str(out))
