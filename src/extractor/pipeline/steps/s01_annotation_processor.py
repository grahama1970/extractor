#!/usr/bin/env python3
"""
Stage 01: Annotation Processor
------------------------------
PDF Annotation Extract → Context Capture → LLM Interpretation → Clean PDF

Uses pdf_oxide (MIT) as the sole extraction engine.
Refactored to be self-contained (merged from utils/annots/runner.py).
"""

import os
import json
import base64
import asyncio
import textwrap
import time
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

from loguru import logger

# Pipeline Utilities
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
from extractor.pipeline.utils.diagnostics import (
    get_run_id,
)
from extractor.pipeline.utils.prompt_loader import load_prompt
from extractor.pipeline.utils.json_utils import clean_json_string
from extractor.pipeline.utils.ann_index import build_ann_index, save_ann_index

# ------------------------------------------------------------------
# CONFIG & CONSTANTS
# ------------------------------------------------------------------
STEP_NAME = "01_annotation_processor"
ANNOT_FREETEXT = "FreeText"
DEBUG = False
RENDER_DPI = 200


@dataclass
class Config:
    """Encapsulate settings for PDF processing and LLM integration."""
    input_pdf: Path
    output_dir: Path
    vertical_expansion_ratio: float = 0.5
    full_page_width: bool = True
    include_freetext: bool = field(default=False)
    use_images: bool = False
    render_dpi: int = 150
    llm_model: str = field(default_factory=lambda: "")
    llm_concurrency: int = 5
    context_blocks: int = 2
    limit_annotations: int = 0
    max_runtime_seconds: int = 0
    debug: bool = False
    cache: bool = True


# ------------------------------------------------------------------
# RELEVANT RULES (previously loaded from json)
# ------------------------------------------------------------------
RELEVANT_RULES = {
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
    "computed_feature_rules": [{"feature": "gridlines_detected", "equals": True, "stages": ["05"]}],
}
# Try loading ext config if present
try:
    ext_rules = Path(__file__).resolve().parent.parent / "config" / "relevant_rules.json"
    if ext_rules.exists():
        with open(ext_rules, "r") as f:
            RELEVANT_RULES = json.load(f)
except Exception as e:
    logger.debug(f"Failed to load external relevant_rules.json, using defaults: {e}")


def _compute_relevant_to_for_annotation(a: Dict[str, Any]) -> List[str]:
    """Derive relevant categories from an annotation."""
    stages: List[str] = []
    try:
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
        except Exception as e:
            logger.debug(f"Failed to parse interpretation fields: {e}")

        texts = [note, echo] + labels
        # 1) Keywords
        for kw, st in (RELEVANT_RULES.get("keywords_to_stages") or {}).items():
            if not kw:
                continue
            if any(kw in t for t in texts):
                for s in st or []:
                    if s not in stages:
                        stages.append(s)
        # 2) Inferred Type
        if inferred_type:
            for s in (RELEVANT_RULES.get("inferred_types_to_stages") or {}).get(inferred_type, []):
                if s not in stages:
                    stages.append(s)
        # 3) Validator
        vs = a.get("validator_suggestion") or {}
        vtype = str((vs or {}).get("type") or "").lower()
        if vtype:
            for s in (RELEVANT_RULES.get("validator_suggestion_to_stages") or {}).get(vtype, []):
                if s not in stages:
                    stages.append(s)
        # 4) Features
        feats = a.get("computed_features") or {}
        for rule in RELEVANT_RULES.get("computed_feature_rules") or []:
            feat = rule.get("feature")
            if feat in feats and feats.get(feat) == rule.get("equals"):
                for s in rule.get("stages") or []:
                    if s not in stages:
                        stages.append(s)
    except Exception as exc:
        log_stage_error("01_annotation_processor", exc, {"context": "compute_relevant"})
    return sorted(stages)


def _llm_enabled(model: Optional[str]) -> bool:
    """Check if a model string indicates LLM is enabled."""
    if not model:
        return False
    if isinstance(model, str):
        normalized = model.strip().lower()
        if normalized in {"", "none", "null", "off", "false", "0", "ignore", "disabled"}:
            return False
    return True


# ------------------------------------------------------------------
# pdf_oxide ENGINE
# ------------------------------------------------------------------


def _union_bbox(blocks: List[Dict[str, Any]]) -> Optional[Any]:
    """Compute the union bounding box of all blocks. Returns object with x0/y0/x1/y1."""
    x0, y0, x1, y1 = float("inf"), float("inf"), float("-inf"), float("-inf")
    found = False
    for blk in blocks or []:
        b = blk.get("bbox")
        if not b:
            continue
        found = True
        x0, y0 = min(x0, b[0]), min(y0, b[1])
        x1, y1 = max(x1, b[2]), max(y1, b[3])
    if not found:
        return None
    return type("R", (), {"x0": x0, "y0": y0, "x1": x1, "y1": y1})()


def _compute_alignment(page_rect: Any, inner_rect: Optional[Any]) -> Optional[str]:
    """Determine horizontal alignment of inner rectangle relative to page."""
    if inner_rect is None:
        return None
    page_cx = (page_rect.x0 + page_rect.x1) / 2.0
    inner_cx = (inner_rect.x0 + inner_rect.x1) / 2.0
    dx = abs(inner_cx - page_cx)
    threshold = 0.1 * (page_rect.x1 - page_rect.x0)
    return "center" if dx <= threshold else "left"


def extract_annotations_data_oxide(pdf_path: Path, config: Config) -> List[Dict[str, Any]]:
    """Extract annotations data from a PDF using pdf_oxide engine."""
    import pdf_oxide

    doc = pdf_oxide.open(str(pdf_path))
    annots_out = []

    for pno in range(doc.page_count()):
        annots = doc.extract_annotations(pno)
        if not annots:
            continue

        w, h = doc.page_dimensions(pno)
        page_text_dict = doc.extract_text_dict(pno)

        freetext_annots = [a for a in annots if a.get("type") == "FreeText"]
        freetext_rects = [[a["rect"][0], a["rect"][1], a["rect"][2], a["rect"][3]] for a in freetext_annots]
        freetext_notes = [{"rect": a["rect"], "note": a.get("content")} for a in freetext_annots]

        for idx, annot in enumerate(annots):
            if annot.get("type") == "FreeText" and not config.include_freetext:
                continue

            rect = annot.get("rect", [0, 0, 0, 0])
            original_rect = list(rect)

            # Expand rect
            extra = max((rect[3] - rect[1]) * config.vertical_expansion_ratio, 40.0) / 2.0
            x0 = 0 if config.full_page_width else rect[0]
            x1 = w if config.full_page_width else rect[2]
            y0 = max(0, rect[1] - extra)
            y1 = min(h, rect[3] + extra)
            expanded_rect = [x0, y0, x1, y1]

            # Context from text dict blocks
            inside_blocks, above_blocks, below_blocks = [], [], []
            for blk in page_text_dict.get("blocks", []):
                bb = blk.get("bbox")
                if not bb:
                    continue
                bx0, by0, bx1, by1 = bb[0], bb[1], bb[2], bb[3]
                # Intersection test
                if bx0 < original_rect[2] and bx1 > original_rect[0] and by0 < original_rect[3] and by1 > original_rect[1]:
                    inside_blocks.append(blk)
                elif bx0 < expanded_rect[2] and bx1 > expanded_rect[0] and by0 < expanded_rect[3] and by1 > expanded_rect[1]:
                    if by1 <= original_rect[1]:
                        above_blocks.append(blk)
                    elif by0 >= original_rect[3]:
                        below_blocks.append(blk)

            above_blocks.sort(key=lambda b: original_rect[1] - b["bbox"][3])
            below_blocks.sort(key=lambda b: b["bbox"][1] - original_rect[3])
            above_blocks = above_blocks[:config.context_blocks]
            below_blocks = below_blocks[:config.context_blocks]

            # Render region
            img_dir = config.output_dir / "visual_output"
            img_dir.mkdir(parents=True, exist_ok=True)
            img_path = img_dir / f"annot_p{pno}_a{idx}.png"
            try:
                img_data = doc.render_page_clipped(
                    pno, tuple(expanded_rect), dpi=config.render_dpi
                )
                img_path.write_bytes(bytes(img_data))
            except Exception as e:
                logger.debug(f"Render failed for annotation p{pno}_a{idx}: {e}")

            # Features
            inside_plain = _extract_plain_text(inside_blocks)
            grid = _gridline_features(str(img_path)) if img_path.exists() else {}

            annots_out.append({
                "id": f"p{pno}_a{idx}",
                "page": pno,
                "type": annot.get("type", "Unknown"),
                "original_rect": original_rect,
                "expanded_rect": expanded_rect,
                "inside_blocks": inside_blocks,
                "above_blocks": above_blocks,
                "below_blocks": below_blocks,
                "image_path": str(img_path),
                "human_note": next(
                    (
                        ft["note"]
                        for ft in freetext_notes
                        if (ft["rect"][0] < original_rect[2] and ft["rect"][2] > original_rect[0]
                            and ft["rect"][1] < original_rect[3] and ft["rect"][3] > original_rect[1])
                    ),
                    None,
                ),
                "computed_features": {
                    "alignment": _compute_alignment(
                        type("R", (), {"x0": 0, "x1": w, "y0": 0, "y1": h})(),
                        _union_bbox(inside_blocks) if inside_blocks else None,
                    ),
                    **_detect_numbering(inside_plain),
                    "gridlines_detected": grid.get("detected", False),
                },
                "provenance": "freetext",
            })

    return annots_out


def create_clean_pdf_oxide(input_path: Path, output_dir: Path) -> str:
    """Create a clean PDF with annotations removed using pdf_oxide."""
    import pdf_oxide

    base_name = input_path.stem
    while base_name.endswith("_clean"):
        base_name = base_name[:-6]
    clean_path = output_dir / f"{base_name}_clean.pdf"

    doc = pdf_oxide.open(str(input_path))
    for pno in range(doc.page_count()):
        annots = doc.extract_annotations(pno)
        if annots:
            doc.remove_annotations(pno, list(range(len(annots))))
    doc.save(str(clean_path))
    return str(clean_path)




def _extract_plain_text(blocks: List[Dict[str, Any]]) -> str:
    """Extract plain text from structured blocks of data."""
    parts: List[str] = []
    for blk in blocks or []:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = (sp.get("text") or "").strip()
                if t:
                    parts.append(t)
    return " ".join(parts).strip()


def _detect_numbering(text: str) -> Dict[str, Optional[Any]]:
    """Extract numbering prefix details from a string."""
    import re

    res: Dict[str, Optional[Any]] = {
        "has_numbering": None,
        "numbering_text": None,
        "numbering_depth": None,
    }
    if not text:
        return res
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
    res["has_numbering"] = False
    return res


def _gridline_features(image_path: str) -> Dict[str, Optional[float]]:
    """Extract gridline density and detection status from image."""
    feats: Dict[str, Optional[float]] = {
        "gridlines_h_density": None,
        "gridlines_v_density": None,
        "gridlines_detected": None,
    }
    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return feats
        h, w = img.shape[:2]
        bw = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
        )
        hk = max(10, w // 30)
        h_lines = cv2.morphologyEx(
            bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1)), iterations=1
        )
        vk = max(10, h // 30)
        v_lines = cv2.morphologyEx(
            bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk)), iterations=1
        )
        h_density = float(np.count_nonzero(h_lines)) / float(h * w)
        v_density = float(np.count_nonzero(v_lines)) / float(h * w)
        feats["gridlines_h_density"] = h_density
        feats["gridlines_v_density"] = v_density
        feats["gridlines_detected"] = bool(h_density > 0.002 and v_density > 0.002)
    except Exception as e:
        logger.debug(f"Gridline feature extraction failed for {image_path}: {e}")
    return feats




# ------------------------------------------------------------------
# LLM PROCESSING
# ------------------------------------------------------------------


def build_context(annot: Dict[str, Any]) -> str:
    """Build context string from annotation."""
    def b2s(blocks):
        """Extract non-empty text lines from structured block data."""
        lines = []
        for blk in blocks:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp.get("text", "").strip():
                        lines.append(f"- {sp['text'].strip()}")
        return "\n".join(lines) if lines else "N/A"

    return textwrap.dedent(
        f"""
        Annotation ID: {annot['id']}
        Type: {annot['type']}
        Page: {annot['page']}
        Inside Text:
        {b2s(annot['inside_blocks'])}
        Above Text:
        {b2s(annot['above_blocks'])}
    """
    ).strip()


async def process_pdf_pipeline(config: Config):
    """Orchestrate a PDF processing pipeline, extracting annotations."""
    datetime.now().isoformat()
    t_stage0 = time.monotonic()
    run_id = get_run_id()
    diagnostics = []

    stage_output_dir = config.output_dir
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    logger.info("01: extracting annotations… (engine=pdf_oxide)")

    data = extract_annotations_data_oxide(config.input_pdf, config)
    if config.limit_annotations:
        data = data[: config.limit_annotations]

    clean_pdf_path = create_clean_pdf_oxide(config.input_pdf, stage_output_dir)

    if not data:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "run_id": run_id,
            "source_pdf": str(config.input_pdf),
            "clean_pdf_path": clean_pdf_path,
            "status": "No annotations found.",
            "annotation_count": 0,
            "annotations": [],
            "diagnostics": diagnostics,
        }
        (json_output_dir / "01_annotations.json").write_text(json.dumps(payload, indent=2))
        return

    # LLM Interpretation
    PROMPT = load_prompt("01_annotation_processor")
    if config.llm_model:
        require_scillm_preflight()
        from scillm.batch import parallel_acompletions_iter

        requests = []
        for idx, d in enumerate(data):
            user_content: Any = build_context(d)
            if config.use_images and "image_path" in d:
                # We need to read image if we want to send it
                try:
                    with open(d["image_path"], "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    user_content = [
                        {"type": "text", "text": user_content},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]
                except Exception as e:
                    logger.warning(f"Failed to load image for annot {d.get('id')}: {e}")

            requests.append(
                {
                    "model": config.llm_model,
                    "messages": [
                        {"role": "system", "content": PROMPT["system"]},
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "timeout": 30,
                    "index": idx,
                }
            )

        api_key = os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123")
        api_base = os.getenv("SCILLM_API_BASE", "http://localhost:4010")

        async for r in parallel_acompletions_iter(
            requests,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai_like",  # Required per SCILLM_PAVED_PATH_CONTRACT
            concurrency=config.llm_concurrency,
            timeout=30,
            wall_time_s=180,  # 3 min max for batch
            tenacious=True,  # Retry with backoff on rate limits
            response_format={"type": "json_object"},
            repair_invalid_json=True,
        ):
            idx = r.get("index")
            if idx is None:
                continue

            d = data[idx]
            if r.get("ok"):
                try:
                    content = r.get("parsed") or r.get("content")
                    if isinstance(content, str):
                        cleaned = clean_json_string(content)
                        d["interpretation"] = (
                            json.loads(cleaned) if isinstance(cleaned, str) else cleaned
                        )
                    else:
                        d["interpretation"] = content
                except Exception:
                    d["interpretation"] = {"error": "Invalid JSON"}
            else:
                d["interpretation"] = {"error": r.get("error")}

    # Validator Suggestions
    for d in data:
        feats = d.get("computed_features") or {}
        score = 0
        if feats.get("gridlines_detected"):
            score = 1
        d["validator_suggestion"] = {"type": "table_region", "confidence": 0.8} if score else None
        d["relevant_to"] = _compute_relevant_to_for_annotation(d)

    # Output
    payload = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "source_pdf": str(config.input_pdf),
        "clean_pdf_path": clean_pdf_path,
        "annotation_count": len(data),
        "annotations": data,
        "diagnostics": diagnostics,
        "timings": {"duration": int((time.monotonic() - t_stage0) * 1000)},
    }

    # Optional FAISS
    try:
        idx, meta = build_ann_index(data)
        if idx:
            save_ann_index(idx, meta, stage_output_dir / "annots_faiss", data)
    except Exception as e:
        logger.debug(f"Optional FAISS index build failed: {e}")

    (json_output_dir / "01_annotations.json").write_text(json.dumps(payload, indent=2))


# ------------------------------------------------------------------
# RUNNER ENTRY POINT
# ------------------------------------------------------------------
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
    """Process PDF for annotations, returning output path."""
    stage_output_dir = output_dir / "01_annotation_processor"
    logger.add(stage_output_dir / "stage_01.log", level="DEBUG")

    cfg = Config(
        input_pdf=input_pdf,
        output_dir=stage_output_dir,
        llm_model=llm_model or "",
        llm_concurrency=concurrency,
        render_dpi=dpi,
        include_freetext=include_freetext,
        use_images=images,
        limit_annotations=limit,
    )

    asyncio.run(process_pdf_pipeline(cfg))
    return stage_output_dir / "json_output" / "01_annotations.json"


def sanity() -> int:
    """Perform sanity check for a step."""
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 01: Annotation Processor")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    parser.add_argument("--pdf", type=Path, help="Input PDF path (required for run)")
    args = parser.parse_args()

    if not args.pdf:
        logger.error("--pdf argument required for execution")
        sys.exit(1)

    try:
        run(input_pdf=args.pdf, output_dir=args.pipeline_dir)
    except Exception as e:
        logger.error(f"Stage 01 Failed: {e}")
        sys.exit(1)
