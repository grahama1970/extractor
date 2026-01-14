#!/usr/bin/env python3
"""
Stage 01: Annotation Processor
------------------------------
PDF Annotation Extract → Context Capture → LLM Interpretation → Clean PDF

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
from typing import List, Dict, Any, Optional, cast
from datetime import datetime

# Third-party
try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 01 requires it.", file=sys.stderr)
    raise

try:
    import psutil
except ImportError:
    psutil = None

from loguru import logger

# Pipeline Utilities
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.debug_utils import log_timing
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    make_event,
    classify_llm_error,
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
    "computed_feature_rules": [
        {"feature": "gridlines_detected", "equals": True, "stages": ["05"]}
    ],
}
# Try loading ext config if present
try:
    ext_rules = Path(__file__).resolve().parent.parent / "config" / "relevant_rules.json"
    if ext_rules.exists():
        with open(ext_rules, "r") as f:
            RELEVANT_RULES = json.load(f)
except Exception: pass


def _compute_relevant_to_for_annotation(a: Dict[str, Any]) -> List[str]:
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
        except Exception: pass
        
        texts = [note, echo] + labels
        # 1) Keywords
        for kw, st in (RELEVANT_RULES.get("keywords_to_stages") or {}).items():
            if not kw: continue
            if any(kw in t for t in texts):
                for s in st or []:
                    if s not in stages: stages.append(s)
        # 2) Inferred Type
        if inferred_type:
            for s in (RELEVANT_RULES.get("inferred_types_to_stages") or {}).get(inferred_type, []):
                if s not in stages: stages.append(s)
        # 3) Validator
        vs = a.get("validator_suggestion") or {}
        vtype = str((vs or {}).get("type") or "").lower()
        if vtype:
            for s in (RELEVANT_RULES.get("validator_suggestion_to_stages") or {}).get(vtype, []):
                if s not in stages: stages.append(s)
        # 4) Features
        feats = a.get("computed_features") or {}
        for rule in RELEVANT_RULES.get("computed_feature_rules") or []:
            feat = rule.get("feature")
            if feat in feats and feats.get(feat) == rule.get("equals"):
                for s in rule.get("stages") or []:
                    if s not in stages: stages.append(s)
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': 'compute_relevant'})
    return sorted(stages)


def _llm_enabled(model: Optional[str]) -> bool:
    if not model:
        return False
    if isinstance(model, str):
        normalized = model.strip().lower()
        if normalized in {"", "none", "null", "off", "false", "0", "ignore", "disabled"}:
            return False
    return True


# ------------------------------------------------------------------
# EXTRACTION LOGIC
# ------------------------------------------------------------------

def _get_expanded_rect(
    annot: fitz.Annot,
    page: fitz.Page,
    config: Config,
    freetext_rects: List[fitz.Rect],
    other_annots: List[fitz.Rect],
) -> fitz.Rect:
    MAX_RADIUS = 200
    current = annot.rect
    cx, cy = (current.x0 + current.x1) / 2, (current.y0 + current.y1) / 2

    # closest FreeText
    best, best_d = None, float("inf")
    for ft in freetext_rects:
        fx, fy = (ft.x0 + ft.x1) / 2, (ft.y0 + ft.y1) / 2
        d = ((cx - fx) ** 2 + (cy - fy) ** 2) ** 0.5
        if d < best_d and d <= MAX_RADIUS:
            best_d, best = d, ft
    expanded = current if best is None else current | best

    # walls
    walls = other_annots
    top = max([r.y1 for r in walls if r.y1 <= expanded.y0], default=0)
    bot = min([r.y0 for r in walls if r.y0 >= expanded.y1], default=page.rect.height)

    # vertical expansion
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
        if "lines" not in blk: continue
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

def _union_bbox(blocks: List[Dict[str, Any]]) -> Optional[fitz.Rect]:
    rect: Optional[fitz.Rect] = None
    for blk in blocks or []:
        try:
            b = blk.get("bbox")
            if not b: continue
            r = fitz.Rect(b)
            rect = r if rect is None else (rect | r)
        except Exception: continue
    return rect

def _compute_alignment(page_rect: fitz.Rect, inner_rect: Optional[fitz.Rect]) -> Optional[str]:
    if inner_rect is None: return None
    page_cx = (page_rect.x0 + page_rect.x1) / 2.0
    inner_cx = (inner_rect.x0 + inner_rect.x1) / 2.0
    dx = abs(inner_cx - page_cx)
    threshold = 0.1 * (page_rect.x1 - page_rect.x0)
    if dx <= threshold: return "center"
    return "left"

def _compute_spacing(
    original_rect: fitz.Rect, above_blocks: List[Dict[str, Any]], below_blocks: List[Dict[str, Any]]
) -> Dict[str, Optional[float]]:
    spacing_above: Optional[float] = None
    spacing_below: Optional[float] = None
    if above_blocks:
        b = fitz.Rect(above_blocks[0].get("bbox"))
        spacing_above = max(0.0, original_rect.y0 - b.y1)
    if below_blocks:
        b = fitz.Rect(below_blocks[0].get("bbox"))
        spacing_below = max(0.0, b.y0 - original_rect.y1)
    return {"spacing_above": spacing_above, "spacing_below": spacing_below}

def _extract_plain_text(blocks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for blk in blocks or []:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = (sp.get("text") or "").strip()
                if t: parts.append(t)
    return " ".join(parts).strip()

def _detect_numbering(text: str) -> Dict[str, Optional[Any]]:
    import re
    res: Dict[str, Optional[Any]] = {
        "has_numbering": None,
        "numbering_text": None,
        "numbering_depth": None,
    }
    if not text: return res
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
    feats: Dict[str, Optional[float]] = {
        "gridlines_h_density": None,
        "gridlines_v_density": None,
        "gridlines_detected": None,
    }
    try:
        import cv2
        import numpy as np
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None: return feats
        h, w = img.shape[:2]
        bw = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10)
        hk = max(10, w // 30)
        h_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1)), iterations=1)
        vk = max(10, h // 30)
        v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk)), iterations=1)
        h_density = float(np.count_nonzero(h_lines)) / float(h * w)
        v_density = float(np.count_nonzero(v_lines)) / float(h * w)
        feats["gridlines_h_density"] = h_density
        feats["gridlines_v_density"] = v_density
        feats["gridlines_detected"] = bool(h_density > 0.002 and v_density > 0.002)
    except Exception: pass
    return feats

def extract_annotations_data(pdf_path: Path, config: Config) -> List[Dict[str, Any]]:
    annots_out = []
    try: doc = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"Stage 01 failed to open PDF: {pdf_path}") from exc

    with doc:
        for pno in range(len(doc)):
            page = doc.load_page(pno)
            all_annots = list(page.annots() or [])
            if not all_annots: continue
            
            freettext_list: List[fitz.Annot] = [
                a for a in all_annots
                if (isinstance(a.type, tuple) and len(a.type) > 1 and a.type[1] == ANNOT_FREETEXT)
            ]
            freetext_rects = [a.rect for a in freettext_list]
            freetext_notes = []
            for a in freettext_list:
                note = (getattr(a, "info", {}) or {}).get("content") or getattr(a, "contents", None)
                freetext_notes.append({"rect": a.rect, "note": note})
            
            page_text_dict = page.get_text("dict")
            for idx, annot in enumerate(all_annots):
                if (isinstance(annot.type, tuple) and len(annot.type) > 1 and annot.type[1] == ANNOT_FREETEXT and not config.include_freetext):
                    continue
                
                original_rect = fitz.Rect(annot.rect)
                other_rects = [a.rect for i, a in enumerate(all_annots) if i != idx]
                expanded_rect = _get_expanded_rect(annot, page, config, freetext_rects, other_rects)
                
                # Context extraction
                context_blocks = _get_context_blocks(original_rect, expanded_rect, page_text_dict, config.context_blocks)
                
                # Image rendering
                matrix = fitz.Matrix(config.render_dpi / 72, config.render_dpi / 72)
                try: pix = page.get_pixmap(matrix=matrix, clip=expanded_rect, annots=False)
                except: pix = page.get_pixmap(matrix=matrix, clip=expanded_rect)
                
                img_dir = config.output_dir / "visual_output"
                img_dir.mkdir(parents=True, exist_ok=True)
                img_path = img_dir / f"annot_p{pno}_a{idx}.png"
                pix.save(str(img_path))
                
                # Features
                inside_blocks = context_blocks["inside"]
                inside_plain = _extract_plain_text(inside_blocks) or ""
                grid = _gridline_features(str(img_path))
                
                annots_out.append({
                    "id": f"p{pno}_a{idx}",
                    "page": pno,
                    "type": "FreeText",
                    "original_rect": [original_rect.x0, original_rect.y0, original_rect.x1, original_rect.y1],
                    "expanded_rect": [expanded_rect.x0, expanded_rect.y0, expanded_rect.x1, expanded_rect.y1],
                    "inside_blocks": inside_blocks,
                    "above_blocks": context_blocks["above"],
                    "below_blocks": context_blocks["below"],
                    "image_path": str(img_path),
                    "human_note": next((ft["note"] for ft in freetext_notes if original_rect.intersects(ft["rect"])), None), # Simplification
                    "computed_features": {
                        "alignment": _compute_alignment(page.rect, _union_bbox(inside_blocks)),
                        **_detect_numbering(inside_plain),
                        "gridlines_detected": grid.get("detected", False)
                    },
                    "provenance": "freetext",
                })
    return annots_out

def create_clean_pdf(input_path: Path, output_dir: Path) -> str:
    clean_path = output_dir / f"{input_path.stem}_clean.pdf"
    doc = fitz.open(input_path)
    with doc:
        for page in doc:
            for annot in list(page.annots() or []):
                page.delete_annot(annot)
        doc.save(str(clean_path))
    return str(clean_path)

# ------------------------------------------------------------------
# LLM PROCESSING
# ------------------------------------------------------------------

def build_context(annot: Dict[str, Any]) -> str:
    def b2s(blocks):
        lines = []
        for blk in blocks:
             for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp.get("text", "").strip(): lines.append(f"- {sp['text'].strip()}")
        return "\n".join(lines) if lines else "N/A"
    
    return textwrap.dedent(f"""
        Annotation ID: {annot['id']}
        Type: {annot['type']}
        Page: {annot['page']}
        Inside Text:
        {b2s(annot['inside_blocks'])}
        Above Text:
        {b2s(annot['above_blocks'])}
    """).strip()

async def process_pdf_pipeline(config: Config):
    stage_start_ts = datetime.now().isoformat()
    t_stage0 = time.monotonic()
    run_id = get_run_id()
    diagnostics = []
    
    stage_output_dir = config.output_dir
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    logger.info("01: extracting annotations…")
    data = extract_annotations_data(config.input_pdf, config)
    if config.limit_annotations: data = data[:config.limit_annotations]
    
    clean_pdf_path = create_clean_pdf(config.input_pdf, stage_output_dir)

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
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    ]
                except Exception as e:
                    logger.warning(f"Failed to load image for annot {d.get('id')}: {e}")
            
            requests.append({
                "model": config.llm_model,
                "messages": [
                     {"role": "system", "content": PROMPT["system"]},
                     {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"},
                "timeout": 30,
                "index": idx
            })

        api_key = os.getenv("CHUTES_API_KEY")
        api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")

        async for r in parallel_acompletions_iter(
            requests,
            api_base=api_base,
            api_key=api_key,
            concurrency=config.llm_concurrency,
            timeout=30,
            response_format={"type": "json_object"},
            repair_invalid_json=True
        ):
            idx = r.get("index")
            if idx is None: continue
            
            d = data[idx]
            if r.get("ok"):
                try:
                    content = r.get("parsed") or r.get("content")
                    if isinstance(content, str):
                        cleaned = clean_json_string(content)
                        d["interpretation"] = json.loads(cleaned) if isinstance(cleaned, str) else cleaned
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
        if feats.get("gridlines_detected"): score = 1
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
        "timings": {"duration": int((time.monotonic() - t_stage0) * 1000)}
    }
    
    # Optional FAISS
    try:
        idx, meta = build_ann_index(data)
        if idx: save_ann_index(idx, meta, stage_output_dir / "annots_faiss", data)
    except Exception: pass

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
    return run_step_sanity(STEP_NAME)

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 01: Annotation Processor")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
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
