#!/usr/bin/env python3
"""
Extract all figures/images from stage 02 output.
- Find all Figure/Image blocks
- Extract with configurable padding to capture titles
- Robustly describe images concurrently using an LLM with retries
- Save images and descriptions to a structured output
"""

import json
import sys

import fitz  # PyMuPDF
import asyncio
import base64
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple
import threading

import psutil  # type: ignore

import typer
from dotenv import find_dotenv, load_dotenv
from loguru import logger
# Use the canonical LiteLLM helper for repairing/fixing JSON strings
# (matches docs: litellm/extras/json_utils.py)
from scillm.extras.json_utils import clean_json_string
from rich.console import Console
try:
    from scillm import acompletion as sc_completion  # type: ignore
except Exception:
    sc_completion = None  # type: ignore
from extractor.pipeline.utils.model_select import get_vlm_model, ModelSelectionError

from extractor.pipeline.utils.diagnostics import (
    build_stage_timings,
    get_run_id,
    gpu_metrics_available,
    iso_now,
    make_event,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
def _normalize_model_alias(model: str | None) -> str:
    """Pass-through alias helper. Preserve prefixes like 'openai/'."""
    return (model or "").strip()

# --- Initialization & Configuration ---

# Fail fast if .env is missing
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)
# SciLLM-only policy: avoid importing legacy LiteLLM cache to prevent lingering
# background threads or side effects that can block process exit.

# Avoid configuring handlers at import time; configure in CLI path.
def _configure_logging_once() -> None:
    try:
        logger.remove()
    except Exception:
        pass
    try:
        logger.add(sys.stderr, level="INFO")
    except Exception:
        pass

# Create console instance
console = Console()

# Make key parameters configurable via environment variables
VERTICAL_PADDING_RATIO = float(os.getenv("FIGURE_VERTICAL_PADDING", "0.2"))
# Single-source VLM model (no tiered fallbacks)
try:
    VLM_MODEL = get_vlm_model()
except ModelSelectionError as _e:
    print(f"Error: {_e}", file=sys.stderr)
    VLM_MODEL = ""
MAX_FIGURES_PER_DOC = int(os.getenv("FIGURE_MAX_PER_DOC", "12"))
MAX_FIGURES_PER_SECTION = int(os.getenv("FIGURE_MAX_PER_SECTION", "3"))
FIGURE_DESC_ENABLED = os.getenv("FIGURE_DESC", "1").lower() in {"1","true","yes"}
FIGURE_MIN_AREA = int(os.getenv("FIGURE_MIN_AREA_PX", "5000"))
DEFAULT_VLM = os.getenv("DEFAULT_VLM", "Qwen/Qwen2.5-VL-32B-Instruct").strip()


# --- Core Functions ---


def _estimate_bbox(page: "fitz.Page", block: dict[str, Any]) -> list[float]:
    """Best-effort bbox from block or first image on page."""
    bbox = block.get("bbox")
    if bbox and bbox != [0, 0, 0, 0]:
        return list(map(float, bbox))
    image_list = page.get_images(full=True)
    if image_list:
        rects = page.get_image_rects(image_list[0][0])
        if rects:
            r = rects[0]
            return [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]
    w, h = page.rect.width, page.rect.height
    return [50.0, 100.0, float(w - 50), float(h - 100)]


def _expand_bbox(bbox: Iterable[float], page_h: float, ratio: float) -> list[float]:
    x0, y0, x1, y1 = map(float, bbox)
    pad = (y1 - y0) * ratio
    return [x0, max(0.0, y0 - pad), x1, min(page_h, y1 + pad)]


def _render_region(page: "fitz.Page", bbox: Iterable[float], scale: float = 2.0) -> bytes:
    rect = fitz.Rect(*bbox)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect)
    return pix.tobytes("png")


def _save_image_bytes(dst_dir: Path, figure_id: str, data: bytes) -> Path:
    p = dst_dir / f"{figure_id}.png"
    p.write_bytes(data)
    return p


def _nearby_text(page: "fitz.Page", bbox: Iterable[float]) -> str:
    rect = fitz.Rect(*bbox)
    blocks = page.get_text("blocks")
    lines = [b[4].strip() for b in blocks if fitz.Rect(b[:4]).intersects(rect) and (b[4] or "").strip()]
    return " ".join(lines)


def _bbox_area(bbox: Iterable[float]) -> int:
    x0, y0, x1, y1 = map(float, bbox)
    try:
        return int((x1 - x0) * (y1 - y0))
    except Exception:
        return 0


def _should_describe(area: int, cfg: dict[str, Any]) -> bool:
    """Policy gate for running the VLM description."""
    skip = bool(cfg.get("skip", False))
    enabled = bool(cfg.get("enabled", True))
    min_area = int(cfg.get("min_area", 0))
    return (not skip) and enabled and (area >= min_area)


def _detect_title_local(pdf_path: Path, page_idx: int, bbox: Iterable[float]) -> Tuple[Optional[str], Optional[str]]:
    import re as _re
    try:
        import fitz as _fitz
        with _fitz.open(str(pdf_path)) as _doc:
            page = _doc[page_idx]
            rr = _fitz.Rect(*bbox)
            band_below = _fitz.Rect(rr.x0, rr.y1, rr.x1, min(page.rect.height, rr.y1 + 140))
            blks = page.get_text("blocks", clip=band_below)
            for b in sorted(blks, key=lambda x: x[1]):
                txt = (b[4] or "").strip()
                if not txt:
                    continue
                if _re.match(r"^\s*(Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", txt, _re.IGNORECASE):
                    return txt, "below"
            band_above = _fitz.Rect(rr.x0, max(0, rr.y0 - 120), rr.x1, rr.y0)
            blks2 = page.get_text("blocks", clip=band_above)
            for b in sorted(blks2, key=lambda x: -x[3]):
                txt = (b[4] or "").strip()
                if not txt:
                    continue
                if _re.match(r"^\s*(Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", txt, _re.IGNORECASE):
                    return txt, "above"
    except Exception:
        pass
    return None, None


async def _infer_title_llm(nearby_text: str, description: str | None) -> Optional[str]:
    base = os.getenv("CHUTES_API_BASE", "").strip()
    key = os.getenv("CHUTES_API_KEY", "").strip()
    model = (os.getenv("CHUTES_TEXT_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or "").strip()
    if not (sc_completion and base and key and model):
        return None
    prompt = (
        "You are naming a figure for a technical document. Return ONLY a short title (<=10 words) in JSON.\n"
        "Do not include the word 'Figure' or numbering.\n\n"
        "Return: {\"title\": \"<short title>\"}.\n\n"
        f"Context (nearby text):\n{(nearby_text or '')[:800]}\n\n"
        f"Description (if any):\n{(description or '')[:400]}\n"
    )
    try:
        resp = await sc_completion(
            model=model,
            api_base=base,
            api_key=None,
            custom_llm_provider="openai_like",
            extra_headers={"x-api-key": key},
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=64,
            temperature=0.2,
            timeout=6.0,
        )
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            return None
        try:
            normalized = clean_json_string(content) if content else content
            obj = json.loads(normalized) if normalized else {}
            return (obj or {}).get("title") or None
        except Exception:
            return content.strip().strip('"') or None
    except Exception:
        return None


def _normalize_title(title: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    import re as _re
    if not title:
        return None, None, None
    m = _re.match(r"\s*(?:Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", title, _re.IGNORECASE)
    number = (m.group(1) or "").strip() or None if m else None
    base_title = (m.group(2) or "").strip() if m else title
    normalized_id = None
    if number:
        normalized_id = f"figure-{number}"
    elif base_title:
        import hashlib as _hash
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in base_title).strip("-")
        normalized_id = f"figure-{slug or _hash.sha1(base_title.encode('utf-8')).hexdigest()[:8]}"
    return number, base_title, normalized_id


def _assemble_result(
    *,
    figure_id: str,
    page_num: int,
    output_dir: Path,
    img_path: Path,
    expanded_bbox: Iterable[float],
    description: str,
    title: Optional[str],
    title_source: Optional[str],
    number: Optional[str],
    base_title: Optional[str],
    normalized_id: Optional[str],
    metadata: Optional[dict] = None,
    extraction_time: Optional[str] = None,
) -> dict[str, Any]:
    bbox_list = [
        float(expanded_bbox[0]),
        float(expanded_bbox[1]),
        float(expanded_bbox[2]),
        float(expanded_bbox[3]),
    ]
    out = {
        "figure_id": figure_id,
        "page": page_num,
        "image_path": str(img_path.relative_to(output_dir.parent.parent)),
        "bbox": bbox_list,
        "ai_description": description,
        "title": title,
        "title_source": title_source,
        "number": number,
        "base_title": base_title,
        "normalized_id": normalized_id,
    }
    if metadata:
        out["metadata"] = metadata
    if extraction_time:
        out["extraction_time"] = extraction_time
    return out


def _dump_debug_state(tag: str, out_dir: Path) -> None:
    """Write a small debug_state.json with thread + process info."""
    try:
        info: dict[str, Any] = {"tag": tag, "time": datetime.now().isoformat()}
        info["threads"] = [
            {"name": t.name, "daemon": t.daemon, "alive": t.is_alive()}
            for t in threading.enumerate()
        ]
        if psutil is not None:
            p = psutil.Process()
            info["open_files"] = [f.path for f in (p.open_files() or [])]
            try:
                info["fds"] = p.num_fds()  # type: ignore[attr-defined]
            except Exception:
                pass
            info["rss_mb"] = int((p.memory_info().rss or 0) / (1024 * 1024))
        out = out_dir / "debug_state.json"
        out.write_text(json.dumps(info, indent=2))
    except Exception:
        pass


async def describe_image_with_llm(image_data: bytes, context: str = "") -> str:
    """Minimal Chutes vision call via SciLLM (OpenAI‑compatible, non‑stream)."""
    base = os.getenv("CHUTES_API_BASE", "").strip()
    key = os.getenv("CHUTES_API_KEY", "").strip()
    model = (os.getenv("CHUTES_VLM_MODEL") or VLM_MODEL or "").strip()
    if not (base and key and model):
        logger.warning("CHUTES_* env or model missing; skipping figure description")
        return ""

    b64 = base64.b64encode(image_data).decode("utf-8")
    messages = [
        {
            "role": "system",
            "content": "Write a concise technical figure description (2–3 sentences). Focus on what the figure shows, labels/axes, and relationships; avoid speculation.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Context: {context[:2000]}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        },
    ]

    try:
        resp = await sc_completion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=base,
            api_key=None,
            extra_headers={"x-api-key": key},
            messages=messages,
            temperature=0.2,
            max_tokens=200,
            timeout=25.0,
        )
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
        if not content:
            logger.warning(f"figure_description.empty_output model={model}")
        return content
    except Exception as e:
        logger.warning(f"figure_description.error model={model} err={e}")
        return ""


async def extract_and_describe_figure(
    pdf_path: Path,
    block: dict[str, Any],
    figure_id: str,
    output_dir: Path,
    skip_descriptions: bool = False,
) -> dict[str, Any] | None:
    """Extract one figure region, describe it, and build a record."""
    try:
        page_num = int(block.get("page_idx", 0))
        with fitz.open(str(pdf_path)) as pdf_doc:
            if page_num >= len(pdf_doc):
                logger.error(f"page_out_of_range id={figure_id} page={page_num}")
                return None
            page = pdf_doc[page_num]
            bbox0 = _estimate_bbox(page, block)
            if not block.get("bbox") or block.get("bbox") == [0, 0, 0, 0]:
                try:
                    md = block.setdefault("metadata", {})
                    ev = make_event(
                        "06_figure_extractor",
                        "warning",
                        "bbox_estimated",
                        f"Estimated bbox for {figure_id}",
                        {"page": page_num, "bbox": bbox0},
                    )
                    md.setdefault("diagnostics", []).append(ev)
                except Exception:
                    pass
            expanded_bbox = _expand_bbox(bbox0, page.rect.height, VERTICAL_PADDING_RATIO)
            image_data = _render_region(page, expanded_bbox)
            img_path = _save_image_bytes(output_dir, figure_id, image_data)
            nearby_text = _nearby_text(page, expanded_bbox)
            context = f"Nearby text on page: {nearby_text}"

        area = _bbox_area(expanded_bbox)

        if _should_describe(area, {"skip": skip_descriptions, "enabled": FIGURE_DESC_ENABLED, "min_area": FIGURE_MIN_AREA}):
            try:
                description = await describe_image_with_llm(image_data, context)
            except Exception as e:
                logger.error(f"figure_description.error id={figure_id} err={e}")
                description = f"Error: Failed to get description - {e}"
        else:
            description = "Description skipped (offline)"

        figure_title, title_source = _detect_title_local(pdf_path, page_num, bbox0)

        if not figure_title:
            inferred = await _infer_title_llm(nearby_text, description)
            if inferred:
                figure_title = f"INFER: {inferred}"
                title_source = title_source or "infer"

        number, base_title, normalized_id = _normalize_title(figure_title)

        meta_val = (
            {"diagnostics": figure_md_diags}
            if isinstance(locals().get("figure_md_diags"), list)
            else {}
        )
        return _assemble_result(
            figure_id=figure_id,
            page_num=page_num,
            output_dir=output_dir,
            img_path=img_path,
            expanded_bbox=expanded_bbox,
            description=description,
            title=figure_title,
            title_source=title_source,
            number=number,
            base_title=base_title,
            normalized_id=normalized_id,
            metadata=meta_val,
            extraction_time=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Fatal error extracting {figure_id}: {e}")
        return None


async def process_figures_batch(
    pdf_path: Path,
    figure_blocks: list[dict[str, Any]],
    output_dir,
    skip_descriptions: bool = False,
) -> list[dict[str, Any]]:
    """Process all figures concurrently with a progress bar."""
    # Optional: cap the number of figures processed to keep runs deterministic/fast
    if MAX_FIGURES_PER_DOC and isinstance(figure_blocks, list):
        figure_blocks = figure_blocks[:MAX_FIGURES_PER_DOC]

    tasks = [
        extract_and_describe_figure(
            pdf_path, block, f"figure_{i+1:03d}", output_dir, skip_descriptions=skip_descriptions
        )
        for i, block in enumerate(figure_blocks)
    ]

    results: list[dict[str, Any]] = []
    logger.info(f"Processing {len(tasks)} figures concurrently...")

    try:
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, res in enumerate(gathered):
            if isinstance(res, Exception):
                logger.error(f"figure_task.failed index={idx} error={res}")
                continue
            if res:
                results.append(res)
                try:
                    logger.info(f"Completed {res['figure_id']}")
                except Exception:
                    pass
    finally:
        # Ensure no orphan tasks remain
        for t in tasks:
            if not t.done():
                t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    return results


def run(
    stage_02_json: Optional[Path] = typer.Argument(
        None, help="Path to Stage 02 (Marker) JSON. Ignored when --bundle is provided."
    ),
    stage_04_json: Optional[Path] = typer.Option(
        None, "--sections", help="Path to Stage 04 (Sections) JSON. Ignored with --bundle."
    ),
    pdf_dir: Optional[Path] = typer.Option(
        None,
        "--pdf-dir",
        help="Directory with the clean PDF from Stage 01. Ignored with --bundle.",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    bundle: Optional[Path] = typer.Option(
        None,
        "--bundle",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Debug bundle JSON with keys: marker_blocks, sections, clean_pdf.",
    ),
    skip_descriptions: bool = typer.Option(
        False,
        "--skip-descriptions/--no-skip-descriptions",
        help="Offline mode: skip LLM descriptions and emit placeholders",
    ),
    debug: bool = typer.Option(
        bool(os.getenv("STAGE06_DEBUG", "").lower() in ("1", "true", "yes", "y")),
        "--debug/--no-debug",
        help="Emit extra debugging artifacts (threads, open files) at end of stage.",
    ),
    force_exit: bool = typer.Option(
        bool(os.getenv("STAGE06_FORCE_EXIT", "0").lower() in ("1", "true", "yes", "y")),
        "--force-exit/--no-force-exit",
        help="Force an immediate process exit after writing outputs (workaround for third-party threads).",
    ),
):
    """Extracts figures, describes them, and associates them with sections."""
    label = bundle.name if bundle else (stage_02_json.name if stage_02_json else "<bundle>")
    console.print(f"[green]Extracting figures from: {label}[/green]")
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time

    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    import os

    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "06_figure_extractor",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass

    # --- Input Validation and Data Loading ---
    if bundle is not None:
        try:
            data = json.loads(Path(bundle).read_text())
            stage_02_data = data.get("marker_blocks") or {}
            sections = data.get("sections") or []
            clean_pdf = data.get("clean_pdf")
            if not stage_02_data or not clean_pdf:
                raise ValueError("bundle missing 'marker_blocks' or 'clean_pdf'")
            pdf_path = Path(clean_pdf)
        except Exception as e:
            typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
            raise typer.Exit(2)
    else:
        if not stage_02_json or not stage_04_json or not pdf_dir:
            console.print("[red]Missing required inputs. Provide stage_02_json, --sections, and --pdf-dir (or use --bundle).[/red]")
            raise typer.Exit(1)
        if not stage_02_json.exists():
            console.print(f"[red]Stage 02 JSON not found: {stage_02_json}[/red]")
            raise typer.Exit(1)
        if not stage_04_json.exists():
            console.print(f"[red]Stage 04 JSON not found: {stage_04_json}[/red]")
            raise typer.Exit(1)
        try:
            pdf_path = next(pdf_dir.glob("*_clean.pdf"))
        except StopIteration:
            console.print(f"[red]No '*_clean.pdf' found in --pdf-dir: {pdf_dir}[/red]")
            raise typer.Exit(1)
        with open(stage_02_json) as f:
            stage_02_data = json.load(f)
        with open(stage_04_json) as f:
            sections_data = json.load(f)
        sections = sections_data.get("sections", [])

    figure_blocks = [
        b for b in stage_02_data.get("blocks", []) if b.get("block_type") in ["Figure", "Image"]
    ]
    if not figure_blocks:
        console.print("[yellow]No figure/image blocks found to process.[/yellow]")
        # Always produce an output JSON for downstream consistency
        stage_output_dir = output_dir / "06_figure_extractor"
        json_output_dir = stage_output_dir / "json_output"
        stage_output_dir.mkdir(parents=True, exist_ok=True)
        json_output_dir.mkdir(exist_ok=True)
        empty = {
            "timestamp": datetime.now().isoformat(),
            "source_json": str(stage_02_json),
            "source_pdf": str(pdf_path),
            "status": "Completed",
            "figure_count": 0,
            "figures": [],
        }
        (json_output_dir / "06_figures.json").write_text(json.dumps(empty, indent=2))
        try:
            samples = stop_resource_sampler(sampler) if sampler else []
            if samples:
                resources.setdefault("resource_samples", samples)
        except Exception:
            pass
        return

    # --- Directory Setup ---
    stage_output_dir = output_dir / "06_figure_extractor"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time

    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    import os

    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "06_figure_extractor",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass

    # --- Figure Extraction and Description ---
    # build a stable map of figure_id -> source block
    fig_block_map = {f"figure_{i+1:03d}": b for i, b in enumerate(figure_blocks)}
    extracted_figures = asyncio.run(
        process_figures_batch(
            pdf_path, figure_blocks, image_output_dir, skip_descriptions=skip_descriptions
        )
    )
    # Ensure bbox/page present from the original blocks when available
    for fig in extracted_figures:
        blk = fig_block_map.get(fig["figure_id"]) if isinstance(fig.get("figure_id"), str) else None
        if blk:
            fig.setdefault("page", blk.get("page_idx", fig.get("page", 0)))
            fig.setdefault("bbox", blk.get("bbox", fig.get("bbox")))

    # --- Associate Figures with Sections ---
    for figure in extracted_figures:
        if not figure.get("bbox"):
            continue
        figure_bbox = fitz.Rect(figure["bbox"])
        for section in sections:
            section_bbox = fitz.Rect(section["bbox"])
            if section["page_start"] <= figure["page"] <= section["page_end"]:
                if section_bbox.intersects(figure_bbox):
                    figure["section_id"] = section.get("id", "unknown")
                    break

    # --- Final Payload and Output ---
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    result = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(stage_02_json),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "figure_count": len(extracted_figures),
        "figures": extracted_figures,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }

    output_path = json_output_dir / "06_figures.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    if debug:
        _dump_debug_state("after_write", json_output_dir)

    console.print(
        f"✅ Figure extraction complete. Saved {len(extracted_figures)} figures to: {output_path}"
    )
    # Optional hard exit to avoid lingering background threads from third-party libs.
    if force_exit:
        try:
            live = [t for t in threading.enumerate() if t.is_alive() and t is not threading.current_thread()]
            if live:
                logger.warning(
                    "Force-exit enabled; terminating despite live threads: "
                    + ", ".join(f"{t.name}(daemon={t.daemon})" for t in live)
                )
        except Exception:
            pass
        # Use os._exit to avoid atexit handlers/threads keeping process alive.
        os._exit(0)


def debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle with keys: marker_blocks, sections, clean_pdf",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    skip_descriptions: bool = typer.Option(
        False,
        "--skip-descriptions/--no-skip-descriptions",
        help="Offline mode: skip LLM descriptions and emit placeholders",
    ),
):
    """Deprecated: use `run --bundle <path>` instead. Thin alias for compatibility."""
    return run(
        stage_02_json=None,
        stage_04_json=None,
        pdf_dir=None,
        output_dir=output_dir,
        bundle=bundle,
        skip_descriptions=skip_descriptions,
        debug=False,
        force_exit=False,
    )


def build_cli():
    import typer as _typer
    _configure_logging_once()
    app = _typer.Typer(help="Robustly extracts and describes figures from a PDF.")
    app.command(name="run")(run)
    app.command(name="debug-bundle")(debug_bundle)
    return app


if __name__ == "__main__":
    # Minimal dev mode: no args + STAGE06_DEV=1 → run with two envs or a bundle.
    if len(sys.argv) == 1 and os.getenv("STAGE06_DEV", "").lower() in {"1", "true", "yes", "y"}:
        bundle = os.getenv("STAGE06_BUNDLE", "").strip()
        if bundle:
            debug_bundle(Path(bundle))
        else:
            s02 = os.environ["STAGE06_STAGE02_JSON"].strip()
            s04 = os.environ["STAGE06_STAGE04_JSON"].strip()
            pdfd = os.getenv("STAGE06_PDF_DIR", "data/results/pipeline/01_annotation_processor").strip()
            outd = os.getenv("STAGE06_OUTPUT_DIR", "data/results/pipeline").strip()
            skip = os.getenv("STAGE06_SKIP_DESCRIPTIONS", "0").lower() in {"1","true","yes","y"}
            run(
                stage_02_json=Path(s02),
                stage_04_json=Path(s04),
                pdf_dir=Path(pdfd),
                output_dir=Path(outd),
                skip_descriptions=skip,
                debug=True,
            )
    else:
        build_cli()()
