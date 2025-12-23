"""Stage 01 annotation processor runner."""
import json
import os
import sys
import asyncio
import time
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger
import fitz  # PyMuPDF
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    make_event,
)

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

# Global constants
ANNOT_FREETEXT = "FreeText"


@dataclass
class Config:
    input_pdf: Path
    output_dir: Path
    vertical_expansion_ratio: float = 0.5
    full_page_width: bool = True
    include_freetext: bool = field(default=False)
    use_images: bool = False
    render_dpi: int = 150
    llm_model: str = field(
        default_factory=lambda: os.getenv("", "")
    )
    llm_concurrency: int = 5
    context_blocks: int = 2
    limit_annotations: int = 0
    max_runtime_seconds: int = 0
    debug: bool = False
    cache: bool = True


def _get_expanded_rect(
    annot: fitz.Annot,
    page: fitz.Page,
    config: Config,
    freetext_rects: List[fitz.Rect],
    other_annots: List[fitz.Rect],
) -> fitz.Rect:
    """Get expanded rectangle around annotation."""
    MAX_RADIUS = 200
    current = annot.rect
    cx, cy = (current.x0 + current.x1) / 2, (current.y0 + current.y1) / 2

    best, best_d = None, float("inf")
    for ft in freetext_rects:
        fx, fy = (ft.x0 + ft.x1) / 2, (ft.y0 + ft.y1) / 2
        d = ((cx - fx) ** 2 + (cy - fy) ** 2) ** 0.5
        if d < best_d and d <= MAX_RADIUS:
            best_d, best = d, ft
    expanded = current if best is None else current | best

    walls = other_annots
    top = max([r.y1 for r in walls if r.y1 <= expanded.y0], default=0)
    bot = min([r.y0 for r in walls if r.y0 >= expanded.y1], default=page.rect.height)

    h = current.y1 - current.y0
    extra = max(h * config.vertical_expansion_ratio, 40.0) / 2.0
    y0 = max(top, expanded.y0 - extra)
    y1 = min(bot, expanded.y1 + extra)

    x0, x1 = (0, page.rect.width) if config.full_page_width else (expanded.x0, expanded.x1)
    return fitz.Rect(x0, y0, x1, y1)


def run(
    input_pdf: Path,
    output_dir: Path = Path("data/results/pipeline"),
    llm_model: Optional[str] = None,
    concurrency: int = 5,
    dpi: int = 150,
    include_freetext: bool = False,
    images: bool = False,
    debug: bool = False,
    limit: int = 0,
    timeout: int = 0,
    cache: bool = True,
) -> Path:
    """Processes a PDF to extract and interpret annotations, saving to a structured output directory."""

    # Define the specific output directory for this stage
    stage_output_dir = output_dir / "01_annotation_processor"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    # Configure logging sink per stage
    try:
        from loguru import logger as _lg

        _lg.remove()
        _lg.add(
            str(stage_output_dir / "stage_01_annotations.log"),
            level="DEBUG" if debug else "INFO",
            enqueue=True,
            backtrace=True,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
        _lg.add(
            sys.stderr,
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass

    cfg = Config(
        input_pdf=input_pdf,
        output_dir=stage_output_dir,
        llm_model=llm_model
        or os.getenv(
            # SciLLM-only: remove legacy defaults
            "",
        ),
        llm_concurrency=concurrency,
        render_dpi=dpi,
        include_freetext=include_freetext,
        use_images=images,
        debug=debug,
        limit_annotations=limit,
        max_runtime_seconds=timeout,
        cache=cache,
    )
    print(f"[01] Processing {input_pdf}")
    if debug:
        print(f"[01] DEBUG: include_freetext = {cfg.include_freetext}")
    try:
        asyncio.run(process_pdf_pipeline(cfg))
        print(f"[01] Saved annotations (may be empty) to {stage_output_dir / 'json_output' / '01_annotations.json'}")
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        logger.exception("Stage 01 failed")
        print(f"Stage 01 failed: {e}")
        raise RuntimeError(f"Stage 01 failed: {e}")
    return stage_output_dir / "json_output" / "01_annotations.json"


# ------------------------------------------------------------------
# Minimal __main__ for convenience: import-safe, optional
if __name__ == "__main__":
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass
    import sys
    from pathlib import Path
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.01_annotation_processor INPUT_PDF [OUT_DIR]",
            file=sys.stderr,
        )
        sys.exit(2)
    if argv[0] == "sanity":
        sys.exit(sanity())
    # Compatibility: accept `run <PDF> -o <OUT>` shape used by runners
    if argv[0] == "run":
        try:
            input_pdf = Path(argv[1])
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            print("Missing input PDF", file=sys.stderr)
            sys.exit(2)
        out_dir = Path("data/results/pipeline")
        if "-o" in argv:
            try:
                out_dir = Path(argv[argv.index("-o") + 1])
            except Exception as exc:
                log_stage_error('01_annotation_processor', exc, {'context': '01'})
                raise
                pass
    else:
        input_pdf = Path(argv[0])
        out_dir = Path(argv[1]) if len(argv) > 1 else Path("data/results/pipeline")
    out = run(input_pdf=input_pdf, output_dir=out_dir)
    print(str(out))

# DEBUG-BUNDLE COMMAND
# ------------------------------------------------------------------
def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
):
    """Run Stage 01 from a single JSON bundle.

    Bundle schema:
    {
      "pdf": "/abs/path/to/input.pdf",
      "options": {
        "include_freetext": true,
        "images": false,
        "limit": 0,
        "timeout": 0,
        "dpi": 150,
        "concurrency": 5,
        "model": "openai/gpt-4o-mini"
      }
    }
    """
    stage_output_dir = output_dir / "01_annotation_processor"
    stage_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        pdf_path = Path(data.get("pdf") or "")
        if not pdf_path or not pdf_path.exists():
            raise ValueError("Bundle must include existing 'pdf' file path")
        opts = data.get("options") or {}
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        print(f"Failed to load bundle: {e}")
        raise ValueError(f"Failed to load bundle: {e}")

    cfg = Config(
        input_pdf=pdf_path,
        output_dir=stage_output_dir,
        include_freetext=bool(opts.get("include_freetext", True)),
        use_images=bool(opts.get("images", False)),
        render_dpi=int(opts.get("dpi", 150)),
        llm_model=str(
            opts.get(
                "model",
                os.getenv(
            # SciLLM-only: remove legacy defaults
            "",
                ),
            )
        ),
        llm_concurrency=int(opts.get("concurrency", 5)),
        limit_annotations=int(opts.get("limit", 0)),
        max_runtime_seconds=int(opts.get("timeout", 0)),
        debug=bool(opts.get("debug", False)),
        cache=bool(opts.get("cache", True)),
    )
    try:
        asyncio.run(process_pdf_pipeline(cfg))
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        print(f"Stage 01 debug-bundle failed: {e}")
        raise RuntimeError(f"Stage 01 debug-bundle failed: {e}")
    print("Debug-bundle run completed for Stage 01")


# ------------------------------------------------------------------
# DEBUG ENTRY
# ------------------------------------------------------------------
## No __main__: use scripts/debug or import and call run(...)
def _get_context_blocks(
    original_rect: fitz.Rect,
    expanded_rect: fitz.Rect,
    page_text_dict: Dict[str, Any],
    num_blocks: int,
) -> Dict[str, List[Dict[str, Any]]]:
    inside, above, below = [], [], []
    for blk in page_text_dict.get("blocks", []):
        if "lines" not in blk:
            continue
        blk_rect = fitz.Rect(blk["bbox"])
        if original_rect.intersects(blk_rect):
            inside.append(blk)
            continue
        if expanded_rect.intersects(blk_rect):
            if blk_rect.y1 <= original_rect.y0:
                above.append(blk)
            elif blk_rect.y0 >= original_rect.y1:
                below.append(blk)
    above.sort(key=lambda b: original_rect.y0 - b["bbox"][3])
    below.sort(key=lambda b: b["bbox"][1] - original_rect.y1)
    return {"inside": inside, "above": above[:num_blocks], "below": below[:num_blocks]}


def _collect_font_sizes(blocks: List[Dict[str, Any]]) -> List[float]:
    sizes: List[float] = []
    for blk in blocks or []:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                try:
                    sz = float(sp.get("size")) if sp.get("size") is not None else None
                    if sz:
                        sizes.append(sz)
                except Exception as exc:
                    log_stage_error('01_annotation_processor', exc, {'context': '01'})
                    raise
                    continue
    return sizes


def _has_bold(blocks: List[Dict[str, Any]]) -> Optional[bool]:
    seen = False
    for blk in blocks or []:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                font = (sp.get("font") or "").lower()
                if "bold" in font:
                    return True
                seen = True
    return False if seen else None


def _union_bbox(blocks: List[Dict[str, Any]]) -> Optional[fitz.Rect]:
    rect: Optional[fitz.Rect] = None
    for blk in blocks or []:
        try:
            b = blk.get("bbox")
            if not b:
                continue
            r = fitz.Rect(b)
            rect = r if rect is None else (rect | r)
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            continue
    return rect


def _compute_alignment(page_rect: fitz.Rect, inner_rect: Optional[fitz.Rect]) -> Optional[str]:
    if inner_rect is None:
        return None
    try:
        page_cx = (page_rect.x0 + page_rect.x1) / 2.0
        inner_cx = (inner_rect.x0 + inner_rect.x1) / 2.0
        dx = abs(inner_cx - page_cx)
        threshold = 0.1 * (page_rect.x1 - page_rect.x0)
        if dx <= threshold:
            return "center"
        # crude heuristic for left/right
        if inner_rect.x0 <= page_rect.x0 + threshold:
            return "left"
        if inner_rect.x1 >= page_rect.x1 - threshold:
            return "right"
        return "left"
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        return None


def _compute_spacing(
    original_rect: fitz.Rect, above_blocks: List[Dict[str, Any]], below_blocks: List[Dict[str, Any]]
) -> Dict[str, Optional[float]]:
    spacing_above: Optional[float] = None
    spacing_below: Optional[float] = None
    try:
        if above_blocks:
            # nearest above is the first (sorted earlier during collection)
            b = fitz.Rect(above_blocks[0].get("bbox"))
            spacing_above = max(0.0, original_rect.y0 - b.y1)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        spacing_above = None
    try:
        if below_blocks:
            b = fitz.Rect(below_blocks[0].get("bbox"))
            spacing_below = max(0.0, b.y0 - original_rect.y1)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        spacing_below = None
    return {"spacing_above": spacing_above, "spacing_below": spacing_below}


def _extract_plain_text(blocks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for blk in blocks or []:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = (sp.get("text") or "").strip()
                if t:
                    parts.append(t)
    return " ".join(parts).strip()


def _detect_numbering(text: str) -> Dict[str, Optional[Any]]:
    import re

    res: Dict[str, Optional[Any]] = {
        "has_numbering": None,
        "numbering_text": None,
        "numbering_depth": None,
    }
    if not text:
        return res
    # Try decimal multi-level like 1.2.3, then 1., then alpha/roman/case variants common in outlines
    m = re.match(r"^\s*((?:\d+\.)+\d+)\s+", text)
    if m:
        num = m.group(1)
        res["has_numbering"] = True
        res["numbering_text"] = num
        res["numbering_depth"] = len(num.split("."))
        return res
    m = re.match(r"^\s*(\d+\.)\s+", text)
    if m:
        res["has_numbering"] = True
        res["numbering_text"] = m.group(1)
        res["numbering_depth"] = 1
        return res
    m = re.match(r"^\s*([A-Z]\.\s+|[a-z]\)\s+|\([ivxlcdmIVXLCDM]+\)\s+)", text)
    if m:
        res["has_numbering"] = True
        res["numbering_text"] = m.group(1).strip()
        res["numbering_depth"] = 1
        return res
    res["has_numbering"] = False
    return res


def _gridline_features(image_path: str) -> Dict[str, Optional[float]]:
    """Very coarse gridline heuristic using OpenCV morphology; safe fallback on errors."""
    feats: Dict[str, Optional[float]] = {
        "gridlines_h_density": None,
        "gridlines_v_density": None,
        "gridlines_detected": None,
    }
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return feats
        h, w = img.shape[:2]
        # Adaptive threshold to isolate lines
        bw = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
        )
        # Horizontal lines
        hk = max(10, w // 30)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1))
        h_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        # Vertical lines
        vk = max(10, h // 30)
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk))
        v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
        h_density = float(np.count_nonzero(h_lines)) / float(h * w)
        v_density = float(np.count_nonzero(v_lines)) / float(h * w)
        feats["gridlines_h_density"] = h_density
        feats["gridlines_v_density"] = v_density
        # Conservative threshold: both present but small
        feats["gridlines_detected"] = bool(h_density > 0.002 and v_density > 0.002)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass
    return feats


def extract_annotations_data(pdf_path: Path, config: Config) -> List[Dict[str, Any]]:
    annots_out = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        logger.exception(f"Failed to open PDF {pdf_path}")
        raise RuntimeError(f"Stage 01 failed to open PDF: {pdf_path}") from e

    with doc:
        for pno in range(len(doc)):
            page = doc.load_page(pno)
            all_annots = list(page.annots() or [])
            if not all_annots:
                continue
            freettext_list: List[fitz.Annot] = [
                a
                for a in all_annots
                if (isinstance(a.type, tuple) and len(a.type) > 1 and a.type[1] == ANNOT_FREETEXT)
            ]
            freetext_rects = [a.rect for a in freettext_list]
            freetext_notes: List[Dict[str, Any]] = []
            for a in freettext_list:
                note = None
                try:
                    info = getattr(a, "info", None) or {}
                    note = info.get("content") or info.get("title") or info.get("subject")
                except Exception as exc:
                    log_stage_error('01_annotation_processor', exc, {'context': '01'})
                    raise
                    note = None
                if not note:
                    try:
                        note = getattr(a, "contents", None)
                    except Exception as exc:
                        log_stage_error('01_annotation_processor', exc, {'context': '01'})
                        raise
                        note = None
                freetext_notes.append({"rect": a.rect, "note": note})
            page_text_dict = page.get_text("dict")  # type: ignore[attr-defined]
            for idx, annot in enumerate(all_annots):
                if (
                    isinstance(annot.type, tuple)
                    and len(annot.type) > 1
                    and annot.type[1] == ANNOT_FREETEXT
                    and not config.include_freetext
                ):
                    continue
                original_rect = fitz.Rect(annot.rect)
                other_rects = [a.rect for i, a in enumerate(all_annots) if i != idx]
                expanded_rect = _get_expanded_rect(annot, page, config, freetext_rects, other_rects)
                # Ensure we include the full extent of any non-empty text block that intersects
                try:
                    new_rect = fitz.Rect(expanded_rect)
                    for blk in page_text_dict.get("blocks", []):
                        if "lines" not in blk:
                            continue
                        # Check non-empty text
                        has_text = False
                        for ln in blk.get("lines", []):
                            for sp in ln.get("spans", []):
                                if (sp.get("text") or "").strip():
                                    has_text = True
                                    break
                            if has_text:
                                break
                        if not has_text:
                            continue
                        blk_rect = fitz.Rect(blk.get("bbox", new_rect))
                        if blk_rect.intersects(new_rect):
                            new_rect = new_rect | blk_rect
                    # Clamp to page bounds
                    expanded_rect = new_rect & page.rect
                except Exception as exc:
                    log_stage_error('01_annotation_processor', exc, {'context': '01'})
                    raise
                    pass
                context_blocks = _get_context_blocks(
                    original_rect, expanded_rect, page_text_dict, config.context_blocks
                )
                # Compute textual features for inside/neighbor blocks
                inside_blocks = context_blocks["inside"]
                above_blocks = context_blocks["above"]
                below_blocks = context_blocks["below"]
                sizes_inside = _collect_font_sizes(inside_blocks)
                sizes_above = _collect_font_sizes(above_blocks)
                sizes_below = _collect_font_sizes(below_blocks)
                avg_size_inside = (sum(sizes_inside) / len(sizes_inside)) if sizes_inside else None
                avg_size_above = (sum(sizes_above) / len(sizes_above)) if sizes_above else None
                avg_size_below = (sum(sizes_below) / len(sizes_below)) if sizes_below else None
                bold_inside = _has_bold(inside_blocks)
                align = _compute_alignment(page.rect, _union_bbox(inside_blocks))
                spacing = _compute_spacing(original_rect, above_blocks, below_blocks)
                # Find nearest FreeText note for rationale (within expansion radius)
                nearest_note = None
                try:
                    cx, cy = (original_rect.x0 + original_rect.x1) / 2, (
                        original_rect.y0 + original_rect.y1
                    ) / 2
                    best_d = float("inf")
                    for ft in freetext_notes:
                        fx, fy = (ft["rect"].x0 + ft["rect"].x1) / 2, (
                            ft["rect"].y0 + ft["rect"].y1
                        ) / 2
                        d = ((cx - fx) ** 2 + (cy - fy) ** 2) ** 0.5
                        if d < best_d and d <= 200:
                            best_d = d
                            nearest_note = ft.get("note")
                except Exception as exc:
                    log_stage_error('01_annotation_processor', exc, {'context': '01'})
                    raise
                    nearest_note = None

                # Parse machine-readable keys from nearest_note if present
                def _parse_note_keys(note: Any) -> Dict[str, str]:
                    out: Dict[str, str] = {}
                    if not isinstance(note, str):
                        return out
                    for ln in [x.strip() for x in note.splitlines() if x.strip()]:
                        if "=" in ln and not ln.startswith("#"):
                            k, v = ln.split("=", 1)
                            out[k.strip()] = v.strip()
                    return out

                machine_note = _parse_note_keys(nearest_note)
                matrix = fitz.Matrix(config.render_dpi / 72, config.render_dpi / 72)
                # Render without drawing annotations to avoid annotation frames leaking into features
                try:
                    pix = page.get_pixmap(matrix=matrix, clip=expanded_rect, annots=False)  # type: ignore[attr-defined]
                except TypeError:
                    # Fallback for PyMuPDF versions without 'annots' kwarg
                    pix = page.get_pixmap(matrix=matrix, clip=expanded_rect)  # type: ignore[attr-defined]
                # write image immediately to avoid holding pixmaps in RAM
                img_dir = config.output_dir / "image_output"
                img_dir.mkdir(parents=True, exist_ok=True)
                img_path = img_dir / f"annot_p{pno}_a{idx}.png"
                pix.save(str(img_path))
                # Compute secondary features that need the image
                inside_plain = _extract_plain_text(inside_blocks) or ""
                numbering = _detect_numbering(inside_plain)
                grid = _gridline_features(str(img_path))

                annots_out.append(
                    {
                        "id": f"p{pno}_a{idx}",
                        "page": pno,
                        "type": "FreeText",
                        "original_rect": [original_rect.x0, original_rect.y0, original_rect.x1, original_rect.y1],
                        "expanded_rect": [expanded_rect.x0, expanded_rect.y0, expanded_rect.x1, expanded_rect.y1],
                        "inside_blocks": inside_blocks,
                        "above_blocks": above_blocks,
                        "below_blocks": below_blocks,
                        "image_path": str(img_path),
                        "human_note": nearest_note,
                        "machine_note": machine_note,
                        "computed_features": {
                            "avg_font_size_inside": avg_size_inside,
                            "avg_font_size_above": avg_size_above,
                            "avg_font_size_below": avg_size_below,
                            "bold_detected_inside": bold_inside,
                            "alignment": align,
                            **numbering,
                            "gridlines_detected": grid.get("detected", False) if isinstance(grid, dict) else False,
                        },
                        "provenance": "freetext",
                    }
                )
    
    # ------------------------------------------------------------------
    # SIDECAR INGESTION (Interactive Workflow)
    # ------------------------------------------------------------------
    try:
        sidecar_path = pdf_path.parent / f".{pdf_path.name}.annotations.json"
        if sidecar_path.exists():
            logger.info(f"Found sidecar annotations: {sidecar_path}")
            sidecar_data = json.loads(sidecar_path.read_text())
            boxes_by_page = sidecar_data.get("boxes_by_page", {})
            
            # Iterate through pages in the sidecar
            for p_str, boxes in boxes_by_page.items():
                try:
                    pno = int(p_str) - 1  # UI uses 1-based, fitz uses 0-based
                except ValueError:
                    continue
                
                if pno < 0 or pno >= len(doc):
                    continue
                    
                page = doc.load_page(pno)
                page_text_dict = page.get_text("dict")
                
                for idx, box in enumerate(boxes):
                    # Convert UI box to fitz.Rect
                    # UI: [x, y, w, h] (normalized or absolute? Assuming absolute based on server.py)
                    # server.py uses: x * pw, y * ph... wait, server.py implies normalized [x, y, w, h]
                    # Let's verify server.py logic: 
                    # rect = fitz.Rect(x * pw, y * ph, (x + w) * pw, (y + h) * ph)
                    # So UI sends NORMALIZED coordinates [0..1]
                    
                    bbox = box.get("bounding_box") or box.get("bbox")
                    if not bbox or len(bbox) != 4:
                        continue
                        
                    nx, ny, nw, nh = bbox
                    pw, ph = page.rect.width, page.rect.height
                    
                    # Denormalize to PDF points
                    x0 = nx * pw
                    y0 = ny * ph
                    x1 = (nx + nw) * pw
                    y1 = (ny + nh) * ph
                    
                    rect = fitz.Rect(x0, y0, x1, y1) & page.rect
                    
                    # Create a synthetic annotation object for consistency
                    # We treat these as "high confidence" human notes
                    human_note = box.get("label") or box.get("type") or "User Annotation"
                    
                    # Reuse context extraction logic
                    # For sidecar, we skip expansion/heuristics and trust the box
                    context_blocks = _get_context_blocks(
                        rect, rect, page_text_dict, config.context_blocks
                    )
                    
                    # Render image for this box
                    matrix = fitz.Matrix(config.render_dpi / 72, config.render_dpi / 72)
                    pix = page.get_pixmap(matrix=matrix, clip=rect, annots=False)
                    
                    img_dir = config.output_dir / "image_output"
                    img_dir.mkdir(parents=True, exist_ok=True)
                    # Use a distinct ID prefix for sidecar items
                    img_path = img_dir / f"sidecar_p{pno}_a{idx}.png"
                    pix.save(str(img_path))
                    
                    # Compute features (subset)
                    inside_blocks = context_blocks["inside"]
                    inside_plain = _extract_plain_text(inside_blocks) or ""
                    numbering = _detect_numbering(inside_plain)
                    
                    annots_out.append({
                        "id": f"sidecar_p{pno}_a{idx}",
                        "page": pno,
                        "type": "Sidecar", # Distinguish from "FreeText" etc.
                        "original_rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                        "expanded_rect": [rect.x0, rect.y0, rect.x1, rect.y1], # No expansion for user boxes
                        "inside_blocks": inside_blocks,
                        "above_blocks": context_blocks["above"],
                        "below_blocks": context_blocks["below"],
                        "image_path": str(img_path),
                        "human_note": human_note, # The label from the UI
                        "machine_note": {"type": box.get("type"), "id": box.get("instance_id")},
                        "computed_features": {
                            "avg_font_size_inside": None, # Skip expensive checks for now
                            "avg_font_size_above": None,
                            "avg_font_size_below": None,
                            "bold_detected_inside": _has_bold(inside_blocks),
                            "alignment": None,
                            **numbering,
                            "gridlines_detected": False, # TODO: run grid check if needed
                        },
                        "provenance": "sidecar" # Explicit marker
                    })
                    
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': 'sidecar_ingestion'})
        # Do not raise; failure to load sidecar should not block legacy pipeline
        logger.warning(f"Failed to load sidecar annotations: {exc}")

    return annots_out


# ------------------------------------------------------------------
# CONTEXT & PROMPT BUILDING
# ------------------------------------------------------------------
def blocks_to_readable(blocks: List[Dict[str, Any]]) -> str:
    lines = []
    for blk in blocks:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                txt = sp.get("text", "").strip()
                if txt:
                    lines.append(f"- {txt}  (Font: {sp.get('font')}, Size: {sp.get('size')})")
    return "\n".join(lines) if lines else "N/A"


def build_context(annot: Dict[str, Any]) -> str:
    inside = blocks_to_readable(annot["inside_blocks"])
    above = blocks_to_readable(annot["above_blocks"])
    below = blocks_to_readable(annot["below_blocks"])
    human_note = annot.get("human_note") or "N/A"
    feats = annot.get("computed_features") or {}
    return textwrap.dedent(
        f"""
        Annotation ID: {annot['id']}
        Annotation Type: {annot['type']}
        Page Number: {annot['page']}
        Human Note (nearest FreeText): {human_note}

        === Text INSIDE Annotation Region ===
        {inside}

        === Text CONTEXT Directly Above Region ===
        {above}

        === Text CONTEXT Directly Below Region ===
        {below}

        === Computed Features (numeric) ===
        avg_font_size_inside: {feats.get('avg_font_size_inside')}
        avg_font_size_above: {feats.get('avg_font_size_above')}
        avg_font_size_below: {feats.get('avg_font_size_below')}
        bold_detected_inside: {feats.get('bold_detected_inside')}
        spacing_above: {feats.get('spacing_above')}
        spacing_below: {feats.get('spacing_below')}
        alignment: {feats.get('alignment')}
        """
    ).strip()


# ------------------------------------------------------------------
# LLM CALL
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------------
def create_clean_pdf(input_path: Path, output_dir: Path) -> str:
    """Creates a version of the PDF with all annotations removed."""
    clean_path = output_dir / f"{input_path.stem}_clean.pdf"
    try:
        doc = fitz.open(input_path)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        logger.error(f"Failed to open PDF {input_path} for cleaning: {e}")
        raise

    with doc:
        for page in doc:
            for annot in list(page.annots() or []):
                page.delete_annot(annot)
        doc.save(str(clean_path))
    print(f"Cleaned PDF saved to: {clean_path}")
    return str(clean_path)


# ------------------------------------------------------------------
# PIPELINE
# ------------------------------------------------------------------
async def process_pdf_pipeline(config: Config):
    """Main pipeline for Stage 01."""
    stage_start_ts = datetime.now().isoformat()
    t_stage0 = time.monotonic()
    run_id = get_run_id()
    diagnostics: List[Dict[str, Any]] = []
    errors_count = 0
    warnings_count = 0
    resources: Dict[str, Any] = {}
    
    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_start"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_start"] = int((getattr(vm, "used", 0)) / (1024 * 1024))
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass
    # removed duplicate re-initialization of run_id/diagnostics/counters
    # Removed legacy LiteLLM cache init (SciLLM-only policy)
    print(f"Processing '{config.input_pdf.name}'…")

    # Define clear output paths for this stage
    stage_output_dir = config.output_dir
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)

    logger.info("01: extracting annotations…")
    data = extract_annotations_data(config.input_pdf, config)
    if config.limit_annotations and config.limit_annotations > 0:
        logger.info(f"Limiting annotations to first {config.limit_annotations} (for debugging)")
        data = data[: config.limit_annotations]
    if not data:
        logger.info("01: no annotations found; skipping LLM and writing empty payload.")
        clean_pdf_path = create_clean_pdf(config.input_pdf, stage_output_dir)
        payload = {
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id,
            "source_pdf": str(config.input_pdf),
            "clean_pdf_path": clean_pdf_path,
            "status": "No annotations found.",
            "annotation_count": 0,
            "annotations": [],
            "errors_count": errors_count,
            "warnings_count": warnings_count,
            "diagnostics": diagnostics,
        }
        out_json = json_output_dir / "01_annotations.json"
        with open(out_json, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info(f"01: saved empty result to: {out_json}")
        return

    # AGENTS.md compliance: Validate SciLLM environment only when we have annotations to interpret
    if config.llm_model or os.getenv("CHUTES_TEXT_MODEL"):
        try:
            logger.info("01: running SciLLM preflight…")
            require_scillm_preflight()
            logger.info("01: SciLLM preflight OK")
        except RuntimeError as e:
            logger.error(f"SciLLM preflight validation failed: {e}")
            if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
                raise
            # Continue without LLM if not in fail-fast mode
            logger.warning("Continuing without LLM inference due to preflight failure")
            config.llm_model = ""

    # images are already saved during extraction

    # Run LLM interpretation via scillm (Chutes x-api-key). Batch with bounded concurrency.
    results = []
    t_llm_ms = 0
    items: List[Dict[str, Any]] = []
    for d in data:
        try:
            # Build messages inline (developer-controlled images via --images flag)
            if config.use_images and "image_path" in d:
                with open(d["image_path"], "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                user_content: Any = [
                    {"type": "text", "text": build_context(d)},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]
            else:
                user_content = build_context(d)
            # Provider quirk: GPT-5 rejects temperature; omit it for gpt-5 models
            _model_l = (config.llm_model or "").lower()
            params = {
                "model": config.llm_model,
                "messages": [
                    {"role": "system", "content": PROMPT["system"]},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 1024,
                "timeout": 30,
                "stream": False,
            }
            if "gpt-5" not in _model_l:
                params["temperature"] = 0.1
            items.append(params)
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            logger.exception(f"Failed to build messages for {d.get('id')}: {e}")
            d["interpretation"] = {"error": f"message_build_failed: {e}"}
            try:
                diagnostics.append(
                    make_event(
                        "01_annotation_processor",
                        "error",
                        "llm_message_build_failed",
                        str(e),
                        {"annotation_id": d.get("id"), "page": d.get("page")},
                    )
                )
                errors_count += 1
            except Exception as exc:
                log_stage_error('01_annotation_processor', exc, {'context': '01'})
                raise
                pass
            items.append(
                {
                    "model": config.llm_model,
                    "messages": [{"role": "user", "content": "noop"}],
                }
            )

    async def _one_scillm_call(idx: int, params: Dict[str, Any]) -> Dict[str, Any]:
        # Router-only OpenAI-compatible call with AGENTS.md preflight validation
        # Fail fast if SciLLM environment is not properly configured
        if not quick_scillm_check():
            raise RuntimeError(
                "SciLLM environment not configured. "
                "Please set CHUTES_API_BASE, CHUTES_API_KEY, and CHUTES_TEXT_MODEL"
            )
        router = get_text_router()
        t0 = time.monotonic()
        timeout_s = int(params.get("timeout", 30))
        try:
            resp = await router.acompletion(
                model="chutes/text",
                messages=params.get("messages") or [],
                response_format={"type": "json_object"},
                temperature=params.get("temperature"),
                timeout=timeout_s,
                max_tokens=int(params.get("max_tokens", 1024)),
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            # Normalize resp access
            if isinstance(resp, dict):
                choices = resp.get("choices") or [{}]
                model_served = resp.get("model")
                usage = resp.get("usage") or {}
            else:
                choices = getattr(resp, "choices", [{}])
                model_served = getattr(resp, "model", None)
                usage = getattr(resp, "usage", None) or {}
            content = (choices or [{}])[0].get("message", {}).get("content", "")
            log_timing(
                "01_annotation_processor",
                {
                    "attempt": "interpret_annotation",
                    "outcome": "ok",
                    "route_name": "chutes/text",
                    "model": model_served,
                    "latency_ms": elapsed_ms,
                    "timeout_s": timeout_s,
                    "tokens_in": usage.get("prompt_tokens"),
                    "tokens_out": usage.get("completion_tokens"),
                    "item_index": idx,
                },
            )
            return {"index": idx, "content": content}
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            log_timing(
                "01_annotation_processor",
                {
                    "attempt": "interpret_annotation",
                    "outcome": "exception",
                    "exception": type(e).__name__,
                    "exception_msg": str(e)[:300],
                    "latency_ms": elapsed_ms,
                    "timeout_s": timeout_s,
                    "item_index": idx,
                },
            )
            # Return neutral content so outer parse can soft-fail
            return {"index": idx, "content": "{}"}

    try:
        t0 = time.monotonic()
        sem = asyncio.Semaphore(max(1, int(config.llm_concurrency or 1)))
        async def _task(i: int, p: Dict[str, Any]):
            async with sem:
                return await _one_scillm_call(i, p)
        coro = asyncio.gather(*(_task(i, it) for i, it in enumerate(items)))
        if config.max_runtime_seconds and config.max_runtime_seconds > 0:
            results = await asyncio.wait_for(coro, timeout=config.max_runtime_seconds)
        else:
            results = await coro
        t_llm_ms = int((time.monotonic() - t0) * 1000)
    except asyncio.TimeoutError as e:
        msg_info = classify_llm_error(e)
        try:
            diagnostics.append(
                make_event(
                    "01_annotation_processor",
                    "error",
                    msg_info["code"],
                    msg_info["message"],
                    {"items": len(items)},
                )
            )
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            pass
        if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
            raise
        results = []
        t_llm_ms = 0
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        msg_info = classify_llm_error(e)
        try:
            diagnostics.append(
                make_event(
                    "01_annotation_processor",
                    "error",
                    msg_info["code"],
                    msg_info["message"],
                    {"items": len(items)},
                )
            )
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            pass
        if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
            raise
        results = []
        t_llm_ms = 0

    # Parse results back into annotations
    if not results:
        # preserve shape when we timed out/failed: set empty interpretation
        for d in data:
            d["interpretation"] = {"error": "LLM call failed or timed out"}
    else:
        for r in results:
            idx = r.get("index") if isinstance(r, dict) else getattr(r, "index", -1)
            if not (0 <= idx < len(data)):
                continue
            d = data[idx]
            content_str = (r.get("content") if isinstance(r, dict) else getattr(r, "content", "")) or ""
            try:
                try:
                    from loguru import logger as _logger
                    # r can be a dict when using paved/scillm adapters; guard attribute access
                    model = getattr(getattr(r, 'request', object()), 'model', None)
                    ok = False
                    if isinstance(r, dict):
                        ok = bool(r.get("exception") is None)
                    else:
                        ok = bool(getattr(r, "exception", None) is None)
                    _logger.info(f"stage01_interpret: model={model} ok={ok}")
                except Exception as exc:
                    log_stage_error('01_annotation_processor', exc, {'context': '01'})
                    pass
                if not isinstance(content_str, str) or not content_str.strip():
                    d["interpretation"] = {"error": "Empty content from LLM"}
                    continue
                cleaned = clean_json_string(content_str)
                if isinstance(cleaned, dict):
                    d["interpretation"] = cast(Dict[str, Any], cleaned)
                    continue
                if isinstance(cleaned, list):
                    d["interpretation"] = {"data": cleaned}
                    continue
                try:
                    loaded = json.loads(cleaned)
                    if isinstance(loaded, dict):
                        d["interpretation"] = cast(Dict[str, Any], loaded)
                    else:
                        d["interpretation"] = {"data": loaded}
                except json.JSONDecodeError:
                    logger.error(
                        f"Invalid JSON for {d.get('id')}: {cleaned[:200]}..."
                    )
                    try:
                        diagnostics.append(
                            make_event(
                                "01_annotation_processor",
                                "error",
                                "llm_invalid_json",
                                "Model returned invalid JSON",
                                {"annotation_id": d.get("id")},
                            )
                        )
                        errors_count += 1
                    except Exception as exc:
                        log_stage_error('01_annotation_processor', exc, {'context': '01'})
                        raise
                        pass
                    d["interpretation"] = {
                        "error": "Invalid JSON response from LLM",
                        "raw_response": cleaned,
                    }
            except Exception as exc:
                log_stage_error('01_annotation_processor', exc, {'context': '01'})
                raise
                logger.exception(
                    f"Failed to parse LLM response for {d.get('id')}: {e}"
                )
                d["interpretation"] = {"error": str(e)}
        # legacy duplicate parsing block removed

    # Tiny validator: suggest header vs table based on computed features (does not override model)
    for d in data:
        feats = d.get("computed_features") or {}
        header_score = 0.0
        table_score = 0.0
        reasons: List[str] = []
        try:
            if feats.get("has_numbering") is True:
                header_score += 0.3
                reasons.append("numbering_present")
            avg_in = feats.get("avg_font_size_inside") or 0
            avg_ab = feats.get("avg_font_size_above") or 0
            avg_bl = feats.get("avg_font_size_below") or 0
            if avg_in and (avg_in > max(avg_ab, avg_bl) + 0.5):
                header_score += 0.3
                reasons.append("font_size_inside_larger")
            if feats.get("bold_detected_inside") is True:
                header_score += 0.2
                reasons.append("bold_detected")
            if (feats.get("spacing_above") or 0) > (2.0 * (feats.get("spacing_below") or 0) + 1.0):
                header_score += 0.1
                reasons.append("extra_spacing_above")
            if feats.get("alignment") == "center":
                header_score += 0.1
                reasons.append("center_alignment")
            if feats.get("gridlines_detected") is True:
                table_score += 0.5
                reasons.append("gridlines_detected")
            gh = feats.get("gridlines_h_density") or 0
            gv = feats.get("gridlines_v_density") or 0
            if gh > 0.01 and gv > 0.01:
                table_score += 0.2
                reasons.append("high_gridline_density")
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            pass
        suggestion: Optional[Dict[str, Any]] = None
        if header_score > 0.4 or table_score > 0.4:
            if header_score >= table_score:
                conf = min(1.0, header_score)
                suggestion = {"type": "section_header", "confidence": conf, "reasons": reasons}
            else:
                conf = min(1.0, table_score)
                suggestion = {"type": "table_region", "confidence": conf, "reasons": reasons}
        d["validator_suggestion"] = suggestion

    # Compute 'relevant_to' per-annotation using ruleset
    try:
        for d in data:
            d["relevant_to"] = _compute_relevant_to_for_annotation(d)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass

    # Create the cleaned PDF in the stage's output directory
    clean_pdf_path = create_clean_pdf(config.input_pdf, stage_output_dir)

    # Build the final, clean payload
    stage_end_ts = datetime.now().isoformat()
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_end"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_end"] = int((getattr(vm, "used", 0)) / (1024 * 1024))
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        pass

    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": stage_end_ts,
        "stage_duration_ms": int((time.monotonic() - t_stage0) * 1000),
        "llm_batch_duration_ms": t_llm_ms,
    }

    payload = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "source_pdf": str(config.input_pdf),
        "clean_pdf_path": clean_pdf_path,
        "status": "Completed",
        "annotation_count": len(data),
        "annotations": data,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }

    # Optional: build and save a local FAISS index for annotations (for stages 03/07)
    try:
        from extractor.pipeline.utils.ann_index import build_ann_index, save_ann_index

        idx, meta = build_ann_index(data)
        if idx is not None:
            base = stage_output_dir / "annots_faiss"
            save_ann_index(idx, meta, base, data)
            diagnostics.append(
                make_event(
                    "01_annotation_processor",
                    "info",
                    "ann_index_built",
                    "Built FAISS annotations index",
                    {"count": len(data)},
                )
            )
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
        try:
            diagnostics.append(
                make_event(
                    "01_annotation_processor", "warning", "ann_index_build_failed", str(e), {}
                )
            )
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
            pass

    # Save final JSON output
    out_json = json_output_dir / "01_annotations.json"
    with open(out_json, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved final output to: {out_json}")

    # ArangoDB logic is commented out to focus on file-based workflow
    # try:
    #     await insert_to_arangodb(payload)
    # except Exception as e:
    #     logger.error(f"ArangoDB upload failed: {e}")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
