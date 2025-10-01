#!/usr/bin/env python3
"""
PDF Annotation Extract → Context Capture → LLM Interpretation → Clean PDF → ArangoDB
Refactored POC with Typer CLI and easy debug mode for VS Code.
"""

import os
import json
import base64
import asyncio
import textwrap
from pathlib import Path
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, cast, Annotated
from datetime import datetime
import time

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 01 requires it.", file=sys.stderr)
    raise
import typer
from loguru import logger
from extractor.pipeline.utils.litellm_call import litellm_call

from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    make_event,
    classify_llm_error,
)

# Use pipeline-local JSON utilities to avoid heavy core service deps during this stage
from extractor.pipeline.utils.json_utils import clean_json_string
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

# ------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------
DEBUG = False
RENDER_DPI = 200
ANNOT_FREETEXT = "FreeText"


def build_cli():
    import typer as _typer

    app = _typer.Typer(help="Annotate → LLM → Clean PDF → ArangoDB", add_completion=False)

    # Re-register commands inside the factory to avoid import-time side effects
    # by referencing the existing callables.
    app.command(name="run")(run)
    app.command(name="debug-bundle")(debug_bundle)
    return app


"""Relevant-to rules config (optional file-based)."""


def _load_relevant_rules() -> Dict[str, Any]:
    """Load relevant rules from config/relevant_rules.json if present; otherwise use defaults."""
    try:
        here = Path(__file__).resolve().parent.parent / "config" / "relevant_rules.json"
        if here.exists():
            with open(here, "r") as f:
                return cast(Dict[str, Any], json.load(f))
    except Exception:
        pass
    # Defaults – small, maintainable ruleset
    return {
        "keywords_to_stages": {
            "section header": ["03"],
            "not a section header": ["03"],
            "not header": ["03"],
            "list item": ["03"],
            "caption": ["03"],
            "footnote": ["03"],
            "table": ["05"],
            "table header": ["05"],
            "merge": ["07"],
            "continues": ["07"],
            "wrap": ["07"],
            "split header": ["07"],
            "split table": ["07"],
        },
        "inferred_types_to_stages": {
            "section_header": ["03"],
            "paragraph": ["03"],
            "list_item": ["03"],
            "caption": ["03"],
            "footnote": ["03"],
            "table_region": ["05"],
            "table_header": ["05"],
        },
        "validator_suggestion_to_stages": {
            "section_header": ["03"],
            "table_region": ["05"],
        },
        "computed_feature_rules": [
            {"feature": "gridlines_detected", "equals": True, "stages": ["05"]}
        ],
    }


RELEVANT_RULES = _load_relevant_rules()


def _compute_relevant_to_for_annotation(a: Dict[str, Any]) -> List[str]:
    stages: List[str] = []
    try:
        # Collect texty sources: human_note and interpretation labels / echo
        note = (a.get("human_note") or "").lower()
        interp = a.get("interpretation") or {}
        labels = []
        echo = ""
        inferred_type = ""
        try:
            if isinstance(interp.get("labels"), list):
                labels = [str(x).lower() for x in interp.get("labels")]
            echo = str(interp.get("human_note_echo") or "").lower()
            inf = interp.get("inferred_object") or {}
            if isinstance(inf, dict):
                inferred_type = str(inf.get("type") or "").lower()
        except Exception:
            pass
        texts = [note, echo] + labels
        # 1) keyword rules
        for kw, st in (RELEVANT_RULES.get("keywords_to_stages") or {}).items():
            try:
                if not kw:
                    continue
                if any(kw in t for t in texts):
                    for s in st or []:
                        if s not in stages:
                            stages.append(s)
            except Exception:
                continue
        # 2) inferred object type
        if inferred_type:
            for s in (RELEVANT_RULES.get("inferred_types_to_stages") or {}).get(inferred_type, []):
                if s not in stages:
                    stages.append(s)
        # 3) validator suggestion
        vs = a.get("validator_suggestion") or {}
        vtype = str((vs or {}).get("type") or "").lower()
        if vtype:
            for s in (RELEVANT_RULES.get("validator_suggestion_to_stages") or {}).get(vtype, []):
                if s not in stages:
                    stages.append(s)
        # 4) computed features
        feats = a.get("computed_features") or {}
        for rule in RELEVANT_RULES.get("computed_feature_rules") or []:
            try:
                feat = rule.get("feature")
                if feat in feats and feats.get(feat) == rule.get("equals"):
                    for s in rule.get("stages") or []:
                        if s not in stages:
                            stages.append(s)
            except Exception:
                continue
    except Exception:
        return stages
    return sorted(stages)


# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
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
        default_factory=lambda: os.getenv(
            "LITELLM_DEFAULT_MODEL", os.getenv("DEFAULT_LITELLM_MODEL", "openai/gpt-4o-mini")
        )
    )
    llm_concurrency: int = 5
    context_blocks: int = 2
    # Debugging controls
    limit_annotations: int = 0  # 0 = no limit
    max_runtime_seconds: int = 0  # 0 = no overall timeout
    debug: bool = False
    cache: bool = True  # Enable LiteLLM cache by default


# DB export handled by stage 10 (arangodb_exporter).

# ------------------------------------------------------------------
# PROMPT
# ------------------------------------------------------------------
SYSTEM_PROMPT = textwrap.dedent(
    """
You are a PDF annotation interpreter. Given (a) a cropped image of the annotated region and
(b) nearby text blocks (inside/above/below), infer what the human likely intended to label and explain why.
Do not assume a specific category in advance; infer from visual and textual evidence. If a human note
(e.g., "Section Header") is provided in the context, evaluate alignment with that note.

Return ONLY a JSON object with keys:
{
  "title": string|null,                   // short title/name if applicable
  "summary": string,                      // 1–2 sentence gist of the region
  "entities": [string],                   // salient terms
  "labels": [string],                     // free-form tags from content
  "human_note_echo": string|null,         // echo of human note if present
  "inferred_object": {                    // your best guess of the object type
    "type": "section_header"|"paragraph"|"table"|"table_header"|"figure"|"caption"|"list_item"|"equation"|"code_block"|"footnote"|"header_footer"|"annotation_note"|"other",
    "confidence": number,                 // 0.0–1.0
    "rationale": string                   // concise why: visual/text cues supporting the choice
  },
  "alternate_objects": [                 // optional alternates with brief rationale
    {"type": string, "confidence": number, "rationale": string}
  ],
  "matches_human_label": boolean|null,    // if human note given, whether this region fits it
  "visual_features": {                    // cues you used; nulls allowed when unknown
    "bold_detected": boolean|null,
    "font_sizes": [number]|null,
    "has_numbering": boolean|null,
    "list_bullet": boolean|null,
    "spacing_above": number|null,
    "spacing_below": number|null,
    "alignment": "left"|"center"|"right"|null,
    "gridlines_or_cells": boolean|null    // evidence suggestive of a table
  }
}

Rules:
- Be neutral; infer the object type from the image + text context. Do not hallucinate.
- Ground rationale in observable cues (e.g., larger font, bold, numbering, extra spacing, centered alignment, gridlines).
- If any field is unknown, use null (or [] for lists). Keep output compact.
"""
)


# ------------------------------------------------------------------
# EXPANSION & EXTRACTION LOGIC
# ------------------------------------------------------------------
def _get_expanded_rect(
    annot: fitz.Annot,
    page: fitz.Page,
    config: Config,
    freetext_rects: List[fitz.Rect],
    other_annots: List[fitz.Rect],
) -> fitz.Rect:
    MAX_RADIUS = 200  # points
    current = annot.rect
    cx, cy = (current.x0 + current.x1) / 2, (current.y0 + current.y1) / 2

    # closest FreeText by 2-D distance
    best, best_d = None, float("inf")
    for ft in freetext_rects:
        fx, fy = (ft.x0 + ft.x1) / 2, (ft.y0 + ft.y1) / 2
        d = ((cx - fx) ** 2 + (cy - fy) ** 2) ** 0.5
        if d < best_d and d <= MAX_RADIUS:
            best_d, best = d, ft
    expanded = current if best is None else current | best

    # hard vertical walls
    walls = other_annots
    top = max([r.y1 for r in walls if r.y1 <= expanded.y0], default=0)
    bot = min([r.y0 for r in walls if r.y0 >= expanded.y1], default=page.rect.height)

    # symmetrical vertical expansion
    h = current.y1 - current.y0
    extra = max(h * config.vertical_expansion_ratio, 40.0) / 2.0
    y0 = max(top, expanded.y0 - extra)
    y1 = min(bot, expanded.y1 + extra)

    x0, x1 = (0, page.rect.width) if config.full_page_width else (expanded.x0, expanded.x1)
    return fitz.Rect(x0, y0, x1, y1)


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
                except Exception:
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
        except Exception:
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
    except Exception:
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
    except Exception:
        spacing_above = None
    try:
        if below_blocks:
            b = fitz.Rect(below_blocks[0].get("bbox"))
            spacing_below = max(0.0, b.y0 - original_rect.y1)
    except Exception:
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
    except Exception:
        pass
    return feats


def extract_annotations_data(pdf_path: Path, config: Config) -> List[Dict[str, Any]]:
    annots_out = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
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
                except Exception:
                    note = None
                if not note:
                    try:
                        note = getattr(a, "contents", None)
                    except Exception:
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
                except Exception:
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
                except Exception:
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
                        "type": annot.type[1],
                        "original_rect": [
                            float(original_rect.x0),
                            float(original_rect.y0),
                            float(original_rect.x1),
                            float(original_rect.y1),
                        ],
                        "expanded_rect": [
                            float(expanded_rect.x0),
                            float(expanded_rect.y0),
                            float(expanded_rect.x1),
                            float(expanded_rect.y1),
                        ],
                        "inside_blocks": inside_blocks,
                        "above_blocks": above_blocks,
                        "below_blocks": below_blocks,
                        "image_path": str(img_path),
                        "human_note": nearest_note,
                        "machine_note": machine_note if machine_note else None,
                        "computed_features": {
                            "avg_font_size_inside": avg_size_inside,
                            "avg_font_size_above": avg_size_above,
                            "avg_font_size_below": avg_size_below,
                            "bold_detected_inside": bold_inside,
                            "alignment": align,
                            **spacing,
                            **numbering,
                            **grid,
                        },
                    }
                )
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
    except Exception as e:
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
    except Exception:
        pass
    # removed duplicate re-initialization of run_id/diagnostics/counters
    # Initialize LiteLLM cache once per run (avoid import-time side effects)
    try:
        if config.cache:
            initialize_litellm_cache()
    except Exception as _e:
        logger.warning(f"LiteLLM cache init failed (continuing): {_e}")
    print(f"Processing '{config.input_pdf.name}'…")

    # Define clear output paths for this stage
    stage_output_dir = config.output_dir
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)

    data = extract_annotations_data(config.input_pdf, config)
    if config.limit_annotations and config.limit_annotations > 0:
        logger.info(f"Limiting annotations to first {config.limit_annotations} (for debugging)")
        data = data[: config.limit_annotations]
    if not data:
        logger.info("No annotations found.")
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
        logger.info(f"Saved empty result to: {out_json}")
        return

    # images are already saved during extraction

    # Run LLM interpretation in a single batched call via litellm_call
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
                    {"role": "system", "content": SYSTEM_PROMPT},
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
        except Exception as e:
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
            except Exception:
                pass
            items.append(
                {
                    "model": config.llm_model,
                    "messages": [{"role": "user", "content": "noop"}],
                }
            )

    try:
        if config.max_runtime_seconds and config.max_runtime_seconds > 0:
            t0 = time.monotonic()
            sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
            results = await asyncio.wait_for(
                litellm_call(
                    items,
                    concurrency=config.llm_concurrency,
                    desc="Interpreting Annotations",
                    session_id=sid,
                    export="results",
                    sanitize_data_urls=os.getenv("STAGE01_SANITIZE_DATA_URLS", "redact"),
                    sanitize_truncate_chars=int(os.getenv("STAGE01_SANITIZE_CHARS", "48")),
                ),
                timeout=config.max_runtime_seconds,
            )
            t_llm_ms = int((time.monotonic() - t0) * 1000)
        else:
            t0 = time.monotonic()
            sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
            results = await litellm_call(
                items,
                concurrency=config.llm_concurrency,
                desc="Interpreting Annotations",
                session_id=sid,
                export="results",
                sanitize_data_urls=os.getenv("STAGE01_SANITIZE_DATA_URLS", "redact"),
                sanitize_truncate_chars=int(os.getenv("STAGE01_SANITIZE_CHARS", "48")),
            )
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
        except Exception:
            pass
        if os.getenv("PIPELINE_FAIL_FAST", "0").lower() in ("1", "true", "yes", "y"):
            raise
        results = []
        t_llm_ms = 0
    except Exception as e:
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
        except Exception:
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
            idx = r.index
            if not (0 <= idx < len(data)):
                continue
            d = data[idx]
            content_str = r.content or ""
            try:
                try:
                    from loguru import logger as _logger
                    _logger.info(
                        f"stage01_interpret: model={getattr(getattr(r,'request',object()),'model',None)} ok={r.exception is None}"
                    )
                except Exception:
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
                    except Exception:
                        pass
                    d["interpretation"] = {
                        "error": "Invalid JSON response from LLM",
                        "raw_response": cleaned,
                    }
            except Exception as e:
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
        except Exception:
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
    except Exception:
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
    except Exception:
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
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
    except Exception as e:
        try:
            diagnostics.append(
                make_event(
                    "01_annotation_processor", "warning", "ann_index_build_failed", str(e), {}
                )
            )
        except Exception:
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
def run(
    input_pdf: Annotated[Path, typer.Argument(..., help="PDF with annotations")],
    output_dir: Annotated[
        Path, typer.Option("-o", help="Parent directory for pipeline results")
    ] = Path("data/results/pipeline"),
    llm_model: Annotated[Optional[str], typer.Option("--model")] = None,
    concurrency: int = 5,
    dpi: int = 150,
    include_freetext: bool = typer.Option(
        False, "--include-freetext", help="Include FreeText annotations."
    ),
    images: bool = typer.Option(
        False, "--images/--no-images", help="Include annotation images in LLM prompts."
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Enable verbose logging to a stage log file."
    ),
    limit: int = typer.Option(
        0, "--limit", help="Limit number of annotations to process (0 = all)."
    ),
    timeout: int = typer.Option(
        0, "--timeout", help="Overall stage timeout in seconds (0 = no limit)."
    ),
    cache: bool = typer.Option(
        True, "--cache/--no-cache", help="Enable LiteLLM cache (default: enabled)"
    ),
):
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
    except Exception:
        pass

    cfg = Config(
        input_pdf=input_pdf,
        output_dir=stage_output_dir,
        llm_model=llm_model
        or os.getenv(
            "LITELLM_DEFAULT_MODEL", os.getenv("DEFAULT_LITELLM_MODEL", "openai/gpt-4o-mini")
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
    if debug:
        print(f"DEBUG: include_freetext = {cfg.include_freetext}")
    try:
        asyncio.run(process_pdf_pipeline(cfg))
    except Exception as e:
        logger.exception("Stage 01 failed")
        typer.secho(f"Stage 01 failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# ------------------------------------------------------------------
# DEBUG-BUNDLE COMMAND
# ------------------------------------------------------------------
def debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle JSON with key 'pdf' and optional 'options'",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
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
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

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
                    "LITELLM_DEFAULT_MODEL",
                    os.getenv("DEFAULT_LITELLM_MODEL", "openai/gpt-4o-mini"),
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
    except Exception as e:
        typer.secho(f"Stage 01 debug-bundle failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("Debug-bundle run completed for Stage 01", fg=typer.colors.GREEN)


# ------------------------------------------------------------------
# DEBUG ENTRY
# ------------------------------------------------------------------
if __name__ == "__main__":
    build_cli()()
