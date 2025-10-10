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

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 06 requires it.", file=sys.stderr)
    raise
import asyncio
from pathlib import Path
from loguru import logger
import sys
from typing import List, Dict, Any, Optional
import base64
from tqdm.asyncio import tqdm_asyncio
import os
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
import textwrap
import typer


from rich.console import Console
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    iso_now,
    make_event,
    snapshot_resources,
    build_stage_timings,
)
from extractor.pipeline.utils.litellm_call import require_scillm_env, normalize_model_alias
import litellm
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

# --- Initialization & Configuration ---

# Fail fast if .env is missing
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)
try:
    initialize_litellm_cache()
except Exception as _e:
    logger.warning(f"LiteLLM cache init failed (continuing): {_e}")

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
# Use local model for simple image descriptions (2-3 sentences)
VLM_MODEL = (os.getenv("LITELLM_VLM_MODEL") or "").strip()
MAX_FIGURES_PER_DOC = int(os.getenv("FIGURE_MAX_PER_DOC", "12"))
MAX_FIGURES_PER_SECTION = int(os.getenv("FIGURE_MAX_PER_SECTION", "3"))
FIGURE_DESC_ENABLED = os.getenv("FIGURE_DESC", "1").lower() in {"1","true","yes"}
FIGURE_MIN_AREA = int(os.getenv("FIGURE_MIN_AREA_PX", "5000"))
DEFAULT_VLM = os.getenv("DEFAULT_VLM", "Qwen/Qwen2.5-VL-32B-Instruct").strip()


# --- Core Functions ---


async def describe_image_with_llm(image_data: bytes, context: str = "") -> str:
    """Describe an image via a single LiteLLM Chat call (Router.acompletion under the hood)."""
    system_prompt = textwrap.dedent(
        """
        You are a helpful assistant that writes concise technical figure descriptions (2–3 sentences).
        Focus on what the figure shows, notable labels, axes, and relationships. Avoid speculation.
        """
    ).strip()
    b64 = base64.b64encode(image_data).decode("utf-8")
    user_content = [
        {"type": "text", "text": f"Context: {context[:2000]}"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    require_scillm_env()
    # Prefer explicit VLM model, then MED VLM, then DEFAULT_VLM constant
    raw_model = (
        os.getenv("LITELLM_VLM_MODEL")
        or os.getenv("LITELLM_MED_VLM_MODEL")
        or DEFAULT_VLM
    ).strip()
    model = normalize_model_alias(raw_model)
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            timeout=25,
            max_tokens=256,
            temperature=0.2,
            custom_llm_provider="openai",
        )
        content = None
        try:
            content = resp["choices"][0]["message"]["content"]
        except Exception:
            content = getattr(getattr(resp, "choices", [None])[0], "message", {}).get("content") if hasattr(resp, "choices") else None
        desc = (content or "").strip()
        if not desc:
            logger.error(f"figure_description.empty_output model={model}")
        return desc
    except Exception as e:
        logger.warning(f"Figure description failed (model={model}): {e}")
        return ""


async def extract_and_describe_figure(
    pdf_path: Path,
    block: Dict[str, Any],
    figure_id: str,
    output_dir: Path,
    skip_descriptions: bool = False,
) -> Optional[Dict[str, Any]]:
    """Extract a single figure with padding and get its description."""
    try:
        page_num = block.get("page_idx", 0)
        bbox = block.get("bbox")

        with fitz.open(str(pdf_path)) as pdf_doc:
            if page_num >= len(pdf_doc):
                logger.error(f"Page {page_num} out of range for {figure_id}")
                return None

            page = pdf_doc[page_num]

            # Bbox estimation logic
            if not bbox or bbox == [0, 0, 0, 0]:
                image_list = page.get_images(full=True)
                if image_list:
                    rects = page.get_image_rects(image_list[0][0])
                    if rects:
                        bbox = list(rects[0])
                if not bbox:
                    bbox = [50, 100, page.rect.width - 50, page.rect.height - 100]
                    logger.warning(f"Estimated bbox for {figure_id}: {bbox}")
                    try:
                        md = block.setdefault("metadata", {})
                        ev = make_event(
                            "06_figure_extractor",
                            "warning",
                            "bbox_estimated",
                            f"Estimated bbox for {figure_id}",
                            {"page": page_num, "bbox": bbox},
                        )
                        diags = md.setdefault("diagnostics", [])
                        diags.append(ev)
                    except Exception:
                        pass

            # Vertical padding
            x0, y0, x1, y1 = bbox
            vertical_padding = (y1 - y0) * VERTICAL_PADDING_RATIO
            expanded_bbox = [
                x0,
                max(0, y0 - vertical_padding),
                x1,
                min(page.rect.height, y1 + vertical_padding),
            ]

            # Image extraction
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(expanded_bbox))
            image_data = pix.tobytes("png")

            # Save image
            img_path = output_dir / f"{figure_id}.png"
            with open(img_path, "wb") as f:
                f.write(image_data)

            # Context extraction
            text_blocks = page.get_text("blocks")
            nearby_text = " ".join(
                [
                    b[4].strip()
                    for b in text_blocks
                    if fitz.Rect(b[:4]).intersects(fitz.Rect(expanded_bbox))
                ]
            )
            context = f"Nearby text on page: {nearby_text}"

        # Compute simple area and enforce min-area and optional global/section caps
        try:
            area = int((expanded_bbox[2]-expanded_bbox[0])*(expanded_bbox[3]-expanded_bbox[1]))
        except Exception:
            area = 0

        # Get AI description using the robust, retrying function (unless skipped)
        if skip_descriptions or not FIGURE_DESC_ENABLED or area < FIGURE_MIN_AREA:
            description = "Description skipped (offline)"
        else:
            try:
                description = await describe_image_with_llm(image_data, context)
                if (description or '').strip():
                    logger.info(f"figure_description.ok id={figure_id} model={(os.getenv('LITELLM_VLM_MODEL') or os.getenv('LITELLM_MED_VLM_MODEL') or '').strip()} len={len(description)}")
                else:
                    logger.warning(f"figure_description.empty id={figure_id}")
            except Exception as e:
                logger.error(f"LLM description for {figure_id} failed after all retries: {e}")
                try:
                    msg = str(e)
                    code = "llm_description_failed"
                    low = msg.lower()
                    if any(
                        k in low
                        for k in ["network", "connect", "connection", "readtimeout", "econn"]
                    ):
                        code = "llm_network_error"
                    ev = make_event(
                        "06_figure_extractor", "error", code, msg, {"figure_id": figure_id}
                    )
                    figure_md_diags = []
                    figure_md_diags.append(ev)
                except Exception:
                    figure_md_diags = []
                description = f"Error: Failed to get description - {e}"

        return {
            "figure_id": figure_id,
            "page": page_num,
            # store path relative to results root (../.. from image_output)
            "image_path": str(img_path.relative_to(output_dir.parent.parent)),
            "bbox": [float(x0), float(y0), float(x1), float(y1)],
            "ai_description": description,
            "metadata": (
                {"diagnostics": figure_md_diags}
                if isinstance(locals().get("figure_md_diags"), list)
                else {}
            ),
            "extraction_time": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Fatal error extracting {figure_id}: {e}")
        return None


async def process_figures_batch(
    pdf_path: Path,
    figure_blocks: List[Dict[str, Any]],
    output_dir: Path,
    skip_descriptions: bool = False,
) -> List[Dict[str, Any]]:
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

    results = []
    logger.info(f"Processing {len(tasks)} figures concurrently...")

    for f in tqdm_asyncio.as_completed(tasks, desc="Extracting and Describing Figures"):
        result = await f
        if result:
            results.append(result)
            logger.info(f"Completed {result['figure_id']}")

    return results


def run(
    stage_02_json: Path = typer.Argument(..., help="Path to Stage 02 (Marker) JSON output."),
    stage_04_json: Path = typer.Option(
        ..., "--sections", help="Path to Stage 04 (Sections) JSON output."
    ),
    pdf_dir: Path = typer.Option(
        "data/results/pipeline/01_annotation_processor",
        "--pdf-dir",
        help="Directory with the clean PDF from Stage 01.",
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
    """Extracts figures, describes them, and associates them with sections."""
    console.print(f"[green]Extracting figures from: {stage_02_json.name}[/green]")
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

    console.print(
        f"✅ Figure extraction complete. Saved {len(extracted_figures)} figures to: {output_path}"
    )


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
    """Run Stage 06 with a consolidated bundle (marker blocks + sections + clean PDF)."""
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

    try:
        data = json.loads(bundle.read_text())
        marker_blocks = data.get("marker_blocks")
        sections_obj = data.get("sections")
        clean_pdf = data.get("clean_pdf")
        if not marker_blocks or not sections_obj or not clean_pdf:
            raise ValueError("Bundle must include 'marker_blocks', 'sections', and 'clean_pdf'")
        tmp_marker = stage_output_dir / "_bundle_marker.json"
        tmp_sections = stage_output_dir / "_bundle_sections.json"
        tmp_marker.write_text(json.dumps(marker_blocks))
        tmp_sections.write_text(json.dumps({"sections": sections_obj}))
        pdf_path = Path(clean_pdf)
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    with open(tmp_marker) as f:
        stage_02_data = json.load(f)
    with open(tmp_sections) as f:
        sections_data = json.load(f)
    sections = sections_data.get("sections", [])

    figure_blocks = [
        b for b in stage_02_data.get("blocks", []) if b.get("block_type") in ["Figure", "Image"]
    ]
    if not figure_blocks:
        console.print("[yellow]No figure/image blocks found to process.[/yellow]")
        return

    extracted_figures = asyncio.run(
        process_figures_batch(
            pdf_path, figure_blocks, image_output_dir, skip_descriptions=skip_descriptions
        )
    )
    fig_block_map = {f"figure_{i+1:03d}": b for i, b in enumerate(figure_blocks)}
    for fig in extracted_figures:
        blk = fig_block_map.get(fig["figure_id"]) if isinstance(fig.get("figure_id"), str) else None
        if blk:
            fig.setdefault("page", blk.get("page_idx", fig.get("page", 0)))
            fig.setdefault("bbox", blk.get("bbox", fig.get("bbox")))
        if fig.get("bbox"):
            try:
                figure_bbox = fitz.Rect(fig["bbox"])
                for section in sections:
                    section_bbox = fitz.Rect(section["bbox"])
                    if section["page_start"] <= fig["page"] <= section[
                        "page_end"
                    ] and section_bbox.intersects(figure_bbox):
                        fig["section_id"] = section.get("id", "unknown")
                        break
            except Exception:
                pass

    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    result = {
        "timestamp": datetime.now().isoformat(),
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
    console.print(f"[green]Debug bundle: saved {len(extracted_figures)} figures to {output_path}")


def build_cli():
    import typer as _typer
    _configure_logging_once()
    app = _typer.Typer(help="Robustly extracts and describes figures from a PDF.")
    app.command(name="run")(run)
    app.command(name="debug-bundle")(debug_bundle)
    return app


if __name__ == "__main__":
    build_cli()()
