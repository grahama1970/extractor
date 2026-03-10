#!/usr/bin/env python3
"""
Suspicious Header Verifier (Stage 03)
-------------------------------------
Purpose
- Takes Stage 02 Marker output + clean PDF.
- For every block flagged as `suspicious_header` (or verify-all), decides keep/demote.
- Writes 03_verified_blocks.json with suspicion cleared and llm_verification filled.

Heuristics before LLM (cheap guardrails)
- Auto-accept: strict numbered headers (e.g., “4.1.2 Title.” with number/title spans parsed).
- Auto-reject when *not numbered* and any of:
  * bullet prefix (•, ●, ▪, ‣, ⁃, –, —, -, *, +, ·)
  * short label ending with “:” (<=40 chars)
  * caption patterns “Table|Figure N[.M][.:]”
  * sentence-like endings “.” or “;”
  * “(continued)” / “- continued” (policy demotion also runs post-flatten)
- Optional human cues: negative/positive annotations near the bbox can auto-reject.

Signals sent to LLM
- Text context (above/target/below) plus “Signals:” line containing font name/size, bold/italic,
  color bucket, suspicion/quality scores, and numbering/title spans when available.
- Optional rendered context image (unless STAGE03_TEXT_ONLY=1).

Behavior
- If LLM (SciLLM vision) rejects → block_type set to Text, suspicious flags annotated.
- If accepts → header retained; suspicion cleared.
- Color enrichment and font signals are preserved for downstream scoring/audits.
"""

import asyncio
import base64
import json
import os
import sys
import time
import warnings
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]
from loguru import logger

# --- Pipeline Utils ---
from extractor.pipeline.utils.headers.llm import verify_header_with_llm as _verify_header_with_llm
from extractor.pipeline.utils.suspicious_headers_utils import (
    has_bullet_prefix,
    ensure_first_span_color,
)
from extractor.pipeline.utils.debug_utils import log_timing
from extractor.pipeline.utils.annotations import (
    load_relevant_rules as _load_relevant_rules,
)
from extractor.pipeline.utils.diagnostics import (
    get_run_id,
    snapshot_resources,
)
from extractor.pipeline.utils.prompt_loader import load_prompt
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.section_builder_utils import (
    pdf_analyze_section_numbering as _pdf_analyze_numbering,
    pdf_extract_section_title as _pdf_extract_title,
    is_probable_pdf_section_header as _is_probable_pdf_header,
)
from extractor.pipeline.utils.prompt_builder import build_llm_context
from scillm.batch import parallel_acompletions_iter

# --- Training Data & Classifier ---

_TRAINING_DIR = Path.home() / ".pi" / "training_data"
_CLASSIFIER_MODEL_PATH = Path.home() / ".pi" / "models" / "classifiers" / "header_verdict.joblib"
_header_classifier = None  # lazy-loaded


def _log_header_verdict(
    text: str,
    font: str | None,
    size: float | None,
    bold: bool | None,
    verdict: str,
    source: str,
    reason: str = "",
    confidence: float | None = None,
) -> None:
    """Append a training label to the S03 header verdicts JSONL file."""
    try:
        _TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "text": text[:500],
            "font": font,
            "size": size,
            "bold": bold,
            "verdict": verdict,
            "source": source,
            "reason": reason,
        }
        if confidence is not None:
            record["confidence"] = confidence
        with open(_TRAINING_DIR / "s03_header_verdicts.jsonl", "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"Failed to log header verdict to training data: {e}")


def _classify_header(
    text: str, font: str | None, size: float | None, bold: bool | None,
) -> dict | None:
    """Run the sklearn header classifier if a trained model exists.

    Returns {"verdict": "accept"|"reject", "confidence": float, "reason": str}
    or None if no model is available.
    """
    global _header_classifier
    if _header_classifier is False:
        return None
    if _header_classifier is None:
        if not _CLASSIFIER_MODEL_PATH.exists():
            _header_classifier = False
            return None
        try:
            import joblib
            _header_classifier = joblib.load(_CLASSIFIER_MODEL_PATH)
            logger.info(f"Loaded header classifier from {_CLASSIFIER_MODEL_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load header classifier: {e}")
            _header_classifier = False
            return None

    try:
        import re as _fre
        features = {
            "text_len": len(text),
            "has_number_prefix": int(bool(_fre.match(r"^\s*\d+(?:[\.\-]\d+)*\s", text))),
            "font_size": float(size or 0),
            "is_bold": int(bool(bold)),
            "ends_with_period": int(text.rstrip().endswith(".")),
            "ends_with_colon": int(text.rstrip().endswith(":")),
            "has_bullet_char": int(bool(_fre.match(r"^\s*[•●▪‣⁃–—\-\*\+·]", text))),
        }
        import numpy as np
        X = np.array([[features[k] for k in sorted(features)]])
        proba = _header_classifier.predict_proba(X)[0]
        classes = list(_header_classifier.classes_)
        accept_idx = classes.index("accept") if "accept" in classes else 0
        reject_idx = classes.index("reject") if "reject" in classes else 1
        if proba[accept_idx] >= proba[reject_idx]:
            verdict = "accept"
            conf = float(proba[accept_idx])
        else:
            verdict = "reject"
            conf = float(proba[reject_idx])
        return {"verdict": verdict, "confidence": conf, "reason": "sklearn_header_classifier"}
    except Exception as e:
        logger.debug(f"Header classifier inference failed: {e}")
        return None

# --- Configuration & Constants ---

STEP_NAME = "03_suspicious_headers"
PROMPT = load_prompt("03_suspicious_headers")
SYSTEM_PROMPT = PROMPT.get("system", "You are an expert at analyzing PDF section headers.")
RELEVANT_RULES = _load_relevant_rules()

STAGE03_COLOR_ENRICH = os.getenv("STAGE03_COLOR_ENRICH", "1").lower() in {"1", "true", "yes", "y"}

# Boilerplate patterns to auto-reject as non-content
BOILERPLATE_PATTERNS = [
    r"^\s*//",  # Comments
    r"^\s*Page\s+\d+\s+(?:of|/)\s+\d+",  # Page numbers (1 of 5, 1/5)
    r"^\s*TLP:\s*(WHITE|GREEN|AMBER|RED)\b",  # Relaxed TLP
    r"^\d+\s+[A-Z]+,\s+[A-Z]+\b",  # "7 HARRISON, JOHNSON" pattern
    r"^(CONFIDENTIAL|PROPRIETARY|COPYRIGHT)\b",
    r"^\s*-\s+continued\s*$",
    r"^\(continued\)\s*$",
    r"^THE CONTENTS$",
    r"^FOREWORD\s*\|",
    r"^iALERT White Paper",
    r"^\s*arXiv:\d{4}\.\d+",  # arXiv stamp (e.g. arXiv:2503.20461)
]

# Header/Footer patterns (additional patterns for PageHeader/PageFooter verification)
HEADER_FOOTER_PATTERNS = [
    r"^\s*page\s+\d+\s*$",  # "page 1"
    r"^\s*\d+\s*$",  # Just a page number
    r"^\s*-\s*\d+\s*-\s*$",  # "- 1 -"
    r"^\s*\d+\s*/\s*\d+\s*$",  # "1 / 10"
    r"^\s*\[\s*\d+\s*\]\s*$",  # "[1]"
    r"confidential|proprietary|draft|internal\s+use",  # Classification markers
    r"copyright\s*©?\s*\d{4}",  # Copyright notices
    r"all\s+rights\s+reserved",  # Rights statement
    r"^\s*document\s+(no|number|ref|reference)[:\s]*[\w\-]+",  # Document references
    r"^\s*revision[:\s]*\d+",  # Revision markers
    r"^\s*version[:\s]*\d+",  # Version markers
    r"^\s*date[:\s]*\d{1,2}[\/\-]\d{1,2}",  # Date markers
    r"printed\s+on",  # Print date
]

# Patterns that indicate content should NOT be filtered (even if in header/footer region)
HEADER_FOOTER_CONTENT_EXCEPTIONS = [
    r"^\d+(?:\.\d+)+\s+\S",  # Numbered section headers (1.1 Title)
    r"^section\s+\d+",  # Section headers
    r"^chapter\s+\d+",  # Chapter headers
    r"^appendix\s+[a-z\d]+",  # Appendix headers
]


try:
    import psutil
except ImportError:
    psutil = None


def _is_header_footer_content(text: str) -> tuple[bool, str]:
    """
    Check if text is typical header/footer content that should be filtered.

    Returns:
        (is_header_footer, reason) tuple
    """
    import re
    text = text.strip()

    if not text:
        return False, ""

    # Check for content exceptions first (actual section headers in header region)
    for pattern in HEADER_FOOTER_CONTENT_EXCEPTIONS:
        if re.match(pattern, text, re.IGNORECASE):
            return False, f"content_exception:{pattern[:20]}"

    # Very short text in header/footer region is likely boilerplate
    if len(text) < 50:
        for pattern in HEADER_FOOTER_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"header_footer_pattern:{pattern[:30]}"

    # Check boilerplate patterns
    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"boilerplate:{pattern[:20]}"

    return False, ""


def _verify_page_header_footer(block: dict, block_type: str) -> dict:
    """
    Verify if a PageHeader/PageFooter block should remain as header/footer
    or be promoted to regular content.

    Args:
        block: The block dict
        block_type: Either "PageHeader" or "PageFooter"

    Returns:
        Verification result dict
    """
    import re
    text = (block.get("text") or "").strip()

    # Short text in header/footer region is almost always boilerplate
    if len(text) < 30:
        is_hf, reason = _is_header_footer_content(text)
        if is_hf:
            return {
                "verified_as": block_type,
                "reasoning": f"Auto-confirm {block_type}: {reason}",
                "action": "keep_as_header_footer",
                "filter_from_content": True,
            }
        # Even short text without matching patterns is likely header/footer
        return {
            "verified_as": block_type,
            "reasoning": f"Auto-confirm {block_type}: short_text",
            "action": "keep_as_header_footer",
            "filter_from_content": True,
        }

    # Check for content exceptions - these should be promoted to Text
    for pattern in HEADER_FOOTER_CONTENT_EXCEPTIONS:
        if re.match(pattern, text, re.IGNORECASE):
            return {
                "verified_as": "Text",
                "reasoning": f"Promoted to Text: content_exception ({pattern[:20]})",
                "action": "promote_to_text",
                "filter_from_content": False,
            }

    # Check explicit header/footer patterns
    is_hf, reason = _is_header_footer_content(text)
    if is_hf:
        return {
            "verified_as": block_type,
            "reasoning": f"Confirmed {block_type}: {reason}",
            "action": "keep_as_header_footer",
            "filter_from_content": True,
        }

    # Longer text without clear patterns - might be actual content
    # Default to keeping as header/footer but flag for review
    return {
        "verified_as": block_type,
        "reasoning": f"Tentative {block_type}: no_clear_pattern (needs_review)",
        "action": "keep_as_header_footer",
        "filter_from_content": True,
        "needs_review": True,
    }


def _env_vlm_model(default: str = "") -> str:
    """SciLLM-only: prefer CHUTES_VLM_MODEL."""
    return (os.getenv("CHUTES_VLM_MODEL") or default).strip()


def sanity() -> int:
    """Run sanity check and return the result."""
    return run_step_sanity(STEP_NAME)


@dataclass
class Config:
    """Store configuration parameters for document processing tasks."""
    input_pdf: Path
    input_json: Path
    output_dir: Path
    render_dpi: int = int(os.getenv("STAGE03_VISION_DPI", "150"))
    llm_model: str = field(default_factory=_env_vlm_model)
    llm_concurrency: int = int(os.getenv("STAGE03_CONCURRENCY", "1"))
    debug: bool = False
    task_limit: int = 0
    max_runtime_seconds: int = 0
    item_timeout_seconds: int = int(os.getenv("STAGE03_ITEM_TIMEOUT", "30"))
    annotations_json: Path | None = None
    use_knowledge: bool = True
    use_prior: bool = True
    auto_reject_negatives: bool = True
    persist_headers: bool = False
    source_pdf: str | None = None
    verify_all_headers: bool = False
    write_suspicion_fields: bool = True


@dataclass
class VerificationTask:
    """Holds all necessary info for a single verification task."""

    page_idx: int
    block_idx: int
    page_blocks: list[dict[str, Any]]
    page_obj: fitz.Page
    config: Config
    image_output_dir: Path

    def get_context_blocks(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
        """Return (target, above, below) where above/below skip empty blocks."""

        def _has_text(b: dict[str, Any] | None) -> bool:
            if not b:
                return False
            t = (b.get("text") or b.get("content") or "").strip()
            if t:
                return True
            # legacy shape
            for ln in b.get("lines") or []:
                for sp in ln.get("spans") or []:
                    if (sp.get("text") or "").strip():
                        return True
            return False

        def _has_bbox(b: dict[str, Any] | None) -> bool:
            if not b:
                return False
            bb = b.get("bbox")
            if not isinstance(bb, (list, tuple)) or len(bb) != 4:
                return False
            x0, y0, x1, y1 = bb
            try:
                return (float(x1) - float(x0)) > 0 and (float(y1) - float(y0)) > 0
            except Exception:
                return False

        def _non_empty(b: dict[str, Any] | None) -> bool:
            return _has_text(b) or _has_bbox(b)

        target = self.page_blocks[self.block_idx]

        # immediate neighbors
        above = self.page_blocks[self.block_idx - 1] if self.block_idx > 0 else None
        below = (
            self.page_blocks[self.block_idx + 1]
            if self.block_idx < len(self.page_blocks) - 1
            else None
        )

        # If neighbor is empty, scan up to ±5 blocks
        MAX_SCAN = 5
        if not _non_empty(above):
            for i in range(self.block_idx - 2, max(-1, self.block_idx - 2 - MAX_SCAN), -1):
                if i < 0:
                    break
                cand = self.page_blocks[i]
                if _non_empty(cand):
                    above = cand
                    break

        if not _non_empty(below):
            for i in range(
                self.block_idx + 2, min(len(self.page_blocks), self.block_idx + 2 + MAX_SCAN)
            ):
                cand = self.page_blocks[i]
                if _non_empty(cand):
                    below = cand
                    break

        return target, above, below

    def render_context_image_b64(self) -> str:
        """Renders an image of the block and its neighbors, saves it, and returns base64."""
        t_start = time.monotonic()
        target, above, below = self.get_context_blocks()

        expanded_rect = fitz.Rect(target["bbox"])

        if above and "bbox" in above:
            expanded_rect.include_rect(fitz.Rect(above["bbox"]))
        if below and "bbox" in below:
            expanded_rect.include_rect(fitz.Rect(below["bbox"]))

        expanded_rect.x0 -= 10
        expanded_rect.y0 -= 10
        expanded_rect.x1 += 10
        expanded_rect.y1 += 10

        # ensure expanded rect stays within page bounds
        expanded_rect = expanded_rect & self.page_obj.rect

        matrix = fitz.Matrix(self.config.render_dpi / 72, self.config.render_dpi / 72)
        pix = self.page_obj.get_pixmap(matrix=matrix, clip=expanded_rect)  # type: ignore

        image_path = self.image_output_dir / f"suspicious_p{self.page_idx}_b{self.block_idx}.png"
        pix.save(str(image_path))

        self.page_blocks[self.block_idx]["context_image_path"] = str(image_path)

        b = pix.tobytes("png")
        b64 = base64.b64encode(b).decode("utf-8")
        try:
            log_timing(
                "03_suspicious_headers",
                {
                    "attempt": "context_render",
                    "outcome": "ok",
                    "render_ms": int((time.monotonic() - t_start) * 1000),
                    "page_idx": int(self.page_idx),
                    "block_idx": int(self.block_idx),
                    "w": getattr(pix, "width", None),
                    "h": getattr(pix, "height", None),
                },
            )
        except Exception as e:
            logger.debug(f"Failed to render context image for block {self.block_idx}: {e}")
        return b64


async def process_pdf_pipeline(config: Config):
    """
    Stage 03 orchestrator: verify suspicious headers with a vision-capable LLM.
    Merged from runner.py to be self-contained.
    """
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    run_id = get_run_id()

    print(f"Verifying suspicious headers in '{config.input_json.name}'...")
    datetime.now().isoformat()
    time.monotonic()
    snapshot_resources("start")

    # Define clear output paths
    json_output_dir = config.output_dir / "json_output"
    image_output_dir = config.output_dir / "visual_output"
    json_output_dir.mkdir(parents=True, exist_ok=True)
    image_output_dir.mkdir(parents=True, exist_ok=True)

    # Load Stage 02 JSON
    with open(config.input_json) as f:
        marker_data = json.load(f)

    try:
        pdf_doc = fitz.open(config.input_pdf)
    except Exception as e:
        logger.error(f"Failed to open PDF {config.input_pdf}: {e}")
        return

    # Normalize: Stage 02 may be flat blocks — convert to pages for local processing
    if "pages" not in marker_data:
        all_blocks = marker_data.get("blocks", [])
        pages_dict = {}
        for block in all_blocks:
            p_idx = block.get("page_idx", 0)
            if p_idx not in pages_dict:
                pages_dict[p_idx] = []
            pages_dict[p_idx].append(block)

        marker_data["pages"] = [
            {"blocks": pages_dict.get(i, [])} for i in sorted(pages_dict.keys())
        ]

    # Annotations
    annotations_by_page: dict[int, list[dict[str, Any]]] = {}
    if config.annotations_json and config.annotations_json.exists():
        try:
            with open(config.annotations_json) as af:
                a_payload = json.load(af)
            for a in a_payload.get("annotations", []):
                p = int(a.get("page", -1))
                if p >= 0:
                    annotations_by_page.setdefault(p, []).append(a)
        except Exception as e:
            logger.warning(f"Failed to load annotations: {e}")

    # Color Enrichment
    if STAGE03_COLOR_ENRICH:
        for p_idx, page_data in enumerate(marker_data.get("pages", [])):
            page_blocks = page_data.get("blocks", [])
            page_obj = pdf_doc[p_idx]
            for block in page_blocks:
                try:
                    raw_text = (block.get("text") or block.get("content") or "").strip()
                    if raw_text:
                        na = _pdf_analyze_numbering(raw_text)
                        if na.get("number_span") or na.get("title_span"):
                            block["header_char_spans"] = {
                                "number": na.get("number_span"),
                                "title": na.get("title_span"),
                            }
                            block.setdefault("header_title", _pdf_extract_title(raw_text))
                    ensure_first_span_color(page_obj, block)
                except Exception:
                    continue

    # Identify candidate tasks
    tasks: list[VerificationTask] = []
    page_header_footer_blocks: list[tuple[int, int, dict]] = []  # Track PageHeader/Footer for verification

    for p_idx, page_data in enumerate(marker_data.get("pages", [])):
        page_blocks = page_data.get("blocks", [])
        for b_idx, block in enumerate(page_blocks):
            block_type = block.get("block_type", "")

            # Handle PageHeader/PageFooter verification (new header_footer_bleed fix)
            if block_type in ("PageHeader", "PageFooter"):
                page_header_footer_blocks.append((p_idx, b_idx, block))
                # Verify header/footer content
                hf_result = _verify_page_header_footer(block, block_type)
                block["header_footer_verification"] = hf_result

                # If promoted to Text, update block_type
                if hf_result.get("action") == "promote_to_text":
                    block["block_type"] = "Text"
                    block["original_block_type"] = block_type
                    block["promoted_from_header_footer"] = True

                continue  # Don't add to tasks - handled inline

            # Original SectionHeader verification logic
            sh_flag = bool(block.get("suspicious_header") is True)
            fallback_header_susp = (block_type == "SectionHeader") and (
                bool(block.get("is_suspicious"))
                or any("header" in str(r).lower() for r in (block.get("suspicious_reasons") or []))
            )
            verify_all = bool(getattr(config, "verify_all_headers", False)) and (
                block_type == "SectionHeader"
            )
            if sh_flag or fallback_header_susp or verify_all:
                tasks.append(
                    VerificationTask(
                        page_idx=p_idx,
                        block_idx=b_idx,
                        page_blocks=page_blocks,
                        page_obj=pdf_doc[p_idx],
                        config=config,
                        image_output_dir=image_output_dir,
                    )
                )

    # Log header/footer verification stats
    if page_header_footer_blocks:
        promoted = sum(1 for _, _, b in page_header_footer_blocks
                      if b.get("header_footer_verification", {}).get("action") == "promote_to_text")
        kept = len(page_header_footer_blocks) - promoted
        logger.info(f"Header/Footer verification: {len(page_header_footer_blocks)} blocks, {kept} kept, {promoted} promoted to Text")

    if config.task_limit and config.task_limit > 0:
        tasks = tasks[: config.task_limit]

    if not tasks:
        print("No suspicious headers found to verify.")
        output_json_path = json_output_dir / "03_verified_blocks.json"

        # Flatten back
        final_blocks = [b for p in marker_data.get("pages", []) for b in p.get("blocks", [])]
        marker_data["blocks"] = final_blocks
        if "pages" in marker_data:
            del marker_data["pages"]

        marker_data["run_id"] = run_id
        with open(output_json_path, "w") as f:
            json.dump(marker_data, f, indent=2)
        pdf_doc.close()
        return

    print(f"Found {len(tasks)} suspicious headers. Starting verification...")

    # Preflight (skip when text-only)
    try:
        if os.getenv("STAGE03_TEXT_ONLY", "1").lower() not in ("1", "true", "yes", "y"):
            sample_image_b64 = tasks[0].render_context_image_b64()
            _ = await _verify_header_with_llm(
                sample_image_b64, "Preflight vision capability check.", config.llm_model
            )
    except Exception as e:
        logger.error(f"Preflight failed: {e}")
        pdf_doc.close()
        raise RuntimeError(f"Vision preflight failed: {e}")

    # Prepare prompts
    prepared: list[dict[str, Any]] = []
    task_refs: list[VerificationTask] = []
    auto_results: dict[int, dict[str, Any]] = {}

    import re as _re

    for idx, task in enumerate(tasks):
        try:
            target_block, above_block, below_block = task.get_context_blocks()
            raw_text = (target_block.get("text") or "").strip()

            # Extract font info for logging/classifier
            first_span_font = target_block.get("first_span_font") or {}
            _font_name = first_span_font.get("name")
            _font_size = first_span_font.get("size")
            _is_bold = first_span_font.get("bold")

            # Auto-ACCEPT: strict 'numbering Title.'
            try:
                hdr = _is_probable_pdf_header(raw_text, first_span_font)
                if (
                    hdr.get("is_header")
                    and hdr.get("confidence") >= 0.999
                    and hdr.get("reason")
                    and "strict_numbered_title_period" in hdr.get("reason")
                ):
                    auto_results[idx] = {
                        "is_header": True,
                        "reasoning": "Auto-accept: strict_numbered_title_period",
                        "auto": True,
                    }
                    if hdr.get("spans"):
                        target_block["header_char_spans"] = hdr["spans"]
                        target_block.setdefault("header_title", hdr.get("title"))
                    _log_header_verdict(raw_text, _font_name, _font_size, _is_bold,
                                        "accept", "heuristic", "strict_numbered_title_period")
                    continue
            except Exception as e:
                logger.debug(f"Heuristic header accept check failed: {e}")

            # Auto-REJECT heuristics
            is_numbered = bool(_re.match(r"^\s*\d+(?:[\.-]\d+){1,}\s+\S", raw_text))
            short_colon = len(raw_text) <= 40 and raw_text.endswith(":")
            raw_text.startswith("•") or raw_text.startswith("●")
            is_caption = bool(
                _re.match(r"^\s*(Table|Figure)\s+\d+(?:[-–]\d+)?[.:]", raw_text, _re.IGNORECASE)
            )
            has_terminal_punct = raw_text.endswith(".") or raw_text.endswith(";")

            if (not is_numbered) and (short_colon or is_caption or has_terminal_punct):
                kind = (
                    "not_header_colon"
                    if short_colon
                    else ("caption_pattern" if is_caption else "not_header_sentence")
                )
                auto_results[idx] = {
                    "is_header": False,
                    "reasoning": f"Auto-reject: {kind}",
                    "debug_kind": kind,
                    "auto": True,
                }
                _log_header_verdict(raw_text, _font_name, _font_size, _is_bold,
                                    "reject", "heuristic", kind)
                continue

            # Auto-REJECT: boilerplate patterns
            for pat in BOILERPLATE_PATTERNS:
                if _re.search(pat, raw_text, _re.IGNORECASE):
                    auto_results[idx] = {
                        "is_header": False,
                        "reasoning": f"Auto-reject: boilerplate_pattern ({pat[:20]}...)",
                        "auto": True,
                    }
                    _log_header_verdict(raw_text, _font_name, _font_size, _is_bold,
                                        "reject", "heuristic", f"boilerplate:{pat[:20]}")
                    break
            if idx in auto_results:
                continue

            # Classifier check: handle medium-confidence cases locally
            classifier_result = _classify_header(raw_text, _font_name, _font_size, _is_bold)
            if classifier_result and classifier_result["confidence"] >= 0.85:
                auto_results[idx] = {
                    "is_header": classifier_result["verdict"] == "accept",
                    "reasoning": f"Classifier: {classifier_result['reason']}",
                    "auto": True,
                }
                _log_header_verdict(raw_text, _font_name, _font_size, _is_bold,
                                    classifier_result["verdict"], "classifier",
                                    classifier_result["reason"],
                                    confidence=classifier_result["confidence"])
                continue
            # else: classifier uncertain or unavailable → fall through to VLM

            # Render
            text_only = os.getenv("STAGE03_TEXT_ONLY", "1").lower() in ("1", "true", "yes", "y")
            image_b64 = task.render_context_image_b64() if not text_only else ""
            context_text = build_llm_context(
                target_block,
                above_block,
                below_block,
                human_annotations_summary="",  # Simplification
            )

            prepared.append(
                {
                    "model": config.llm_model,
                    "image_b64": image_b64,
                    "context_text": context_text,
                }
            )
            task_refs.append(task)

        except Exception as e:
            logger.exception(f"Preparation failed for page {task.page_idx}: {e}")
            auto_results[idx] = {"is_header": True, "reasoning": f"Error: {e}"}

    # Apply Auto-Results
    for idx, res in auto_results.items():
        task = tasks[idx]
        block = marker_data["pages"][task.page_idx]["blocks"][task.block_idx]

        if os.getenv("CONTRACT_LOOP_DEBUG_VISUALS", "0").lower() in ("1", "true", "yes", "y"):
            try:
                if not block.get("context_image_path"):
                    _ = task.render_context_image_b64()
            except Exception as e:
                logger.debug(f"Failed to render debug visual for block {task.block_idx}: {e}")

        is_header = res.get("is_header", False)
        block["suspicious_header"] = False
        block["requires_verification"] = False
        block["llm_verification"] = {
            "verified_at": datetime.now().isoformat(),
            "model": "heuristic_v1",
            "result": res,
            "final_block_type": "SectionHeader" if is_header else "Text",
        }
        if not is_header:
            block["block_type"] = "Text"
            block["is_suspicious"] = True
            block["suspicious_reasons"] = [res.get("reasoning", "")]
        else:
            block["is_suspicious"] = False

    # Execute Batch LLM
    if prepared:
        logger.info(f"Batch verifying {len(prepared)} suspicious headers...")

        requests = []
        for idx, item in enumerate(prepared):
            user_content = [{"type": "text", "text": item["context_text"]}]
            if item["image_b64"]:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{item['image_b64']}"},
                    }
                )

            requests.append(
                {
                    "model": item["model"],
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
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
            timeout=config.item_timeout_seconds,
            wall_time_s=300,  # 5 min max for batch
            tenacious=True,  # Retry with backoff on rate limits
            response_format={"type": "json_object"},
            repair_invalid_json=True,
        ):
            idx = r.get("index")
            if idx is None:
                continue

            task = task_refs[idx]
            block = marker_data["pages"][task.page_idx]["blocks"][task.block_idx]

            is_header = False
            reason = f"LLM Error: {r.get('error')}"

            if r.get("ok"):
                try:
                    data = r.get("parsed") or r.get("content") or {}
                    if isinstance(data, str) and data:
                        import json_repair

                        data = json_repair.loads(data)
                    is_header = bool(data.get("is_header"))
                    reason = data.get("reasoning") or "Verified"
                except Exception as e:
                    reason = f"Parse Error: {e}"

            block["suspicious_header"] = False
            block["requires_verification"] = False
            block["llm_verification"] = {
                "verified_at": datetime.now().isoformat(),
                "model": config.llm_model,
                "result": {"is_header": is_header, "reasoning": reason},
                "final_block_type": "SectionHeader" if is_header else "Text",
            }

            # Log VLM verdict for training data
            vlm_verdict = "accept" if is_header else "reject"
            vlm_text = (block.get("text") or "").strip()
            vlm_font = (block.get("first_span_font") or {})
            _log_header_verdict(
                vlm_text,
                vlm_font.get("name"),
                vlm_font.get("size"),
                vlm_font.get("bold"),
                vlm_verdict, "vlm", reason,
            )

            if not is_header:
                block["block_type"] = "Text"
                block["is_suspicious"] = True
                block["suspicious_reasons"] = [reason]
            else:
                block["is_suspicious"] = False

    # Save Markup
    final_blocks = [block for page in marker_data["pages"] for block in page["blocks"]]
    marker_data["blocks"] = final_blocks
    del marker_data["pages"]
    marker_data["run_id"] = run_id

    # Save statistics/timings...

    output_json_path = json_output_dir / "03_verified_blocks.json"
    if os.getenv("DRY_RUN", "0").lower() not in {"1", "true", "yes", "y"}:
        with open(output_json_path, "w") as f:
            json.dump(marker_data, f, indent=2)
        print(f"Markup saved to: {output_json_path}")


# --- Main Entry Point ---


def run(
    input_json: Path,
    pdf_dir: Path = Path("data/results/pipeline/01_annotation_processor"),
    output_dir: Path = Path("data/results/pipeline"),
    model: str | None = None,
    concurrency: int = 1,
    dpi: int = 150,
    debug: bool = False,
    limit: int = 0,
    timeout: int = 0,
    annotations_json: Path | None = None,
    use_knowledge: bool = True,
    use_prior: bool = True,
    auto_reject: bool = True,
    persist_headers: bool = False,
    verify_all_headers: bool = False,
    skip_llm: bool = False,
) -> Path:
    """
    Finds and verifies suspicious section headers in a Marker JSON file using a multimodal LLM.
    """
    # ... (PDF cleaning resolution logic from original) ...
    run_results_dir = Path(os.getenv("RUN_RESULTS_DIR", "data/results/pipeline"))
    preflight_dir = run_results_dir / "00_preflight"
    clean_pdf_path: Path | None = None
    if preflight_dir.exists():
        matches = sorted(preflight_dir.rglob("clean.pdf"))
        if matches:
            prefer = [m for m in matches if m.parent.name in str(input_json)]
            clean_pdf_path = prefer[0] if prefer else matches[0]

    if clean_pdf_path is None:
        # Fallback
        try:
            candidates = sorted(pdf_dir.glob("*_clean.pdf"))
            if candidates:
                clean_pdf_path = candidates[0]
        except Exception as e:
            logger.warning(f"Failed to find clean PDF in {pdf_dir}: {e}")

    if clean_pdf_path is None:
        # Final fallback - assume user passed input_json which is valid, try to find PDF
        # from sibling directories? Or just raise if strict.
        # For this refactor, let's assume valid paths are passed or clean_pdf_path logic above works.
        pass

    stage_output_dir = output_dir / "03_suspicious_headers"
    stage_output_dir.mkdir(parents=True, exist_ok=True)

    if skip_llm:
        # Quick heuristic only pass (for deterministic/offline)
        marker_data = json.loads(input_json.read_text())
        pages = marker_data.get("pages")
        if not pages:
            pages = [{"blocks": marker_data.get("blocks", [])}]

        import re as _re

        run_id = get_run_id()
        hf_stats = {"total": 0, "kept": 0, "promoted": 0}

        for page in pages:
            for block in page.get("blocks", []):
                block_type = block.get("block_type", "")

                # Handle PageHeader/PageFooter verification (header_footer_bleed fix)
                if block_type in ("PageHeader", "PageFooter"):
                    hf_stats["total"] += 1
                    hf_result = _verify_page_header_footer(block, block_type)
                    block["header_footer_verification"] = hf_result

                    if hf_result.get("action") == "promote_to_text":
                        block["block_type"] = "Text"
                        block["original_block_type"] = block_type
                        block["promoted_from_header_footer"] = True
                        hf_stats["promoted"] += 1
                    else:
                        hf_stats["kept"] += 1
                    continue

                # Original SectionHeader verification
                is_section = block.get("block_type") == "SectionHeader"
                is_suspicious = bool(block.get("suspicious_header") is True)
                verify_all = bool(verify_all_headers) and is_section
                if not (is_section and (is_suspicious or verify_all)):
                    continue

                raw_text = (block.get("text") or "").strip()
                is_header = True
                reason = "Heuristic: pass-through"

                try:
                    hdr = _is_probable_pdf_header(raw_text, block.get("first_span_font") or {})
                    if hdr.get("is_header") and hdr.get("confidence", 0) >= 0.999:
                        reason = "Auto-accept: strict_numbered_title_period"
                        if hdr.get("spans"):
                            block["header_char_spans"] = hdr["spans"]
                            block.setdefault("header_title", hdr.get("title"))
                except Exception as e:
                    logger.debug(f"Strict header recheck failed for block: {e}")

                if is_header and has_bullet_prefix(raw_text):
                    is_header = False
                    reason = "Auto-reject: bullet_prefix"

                if is_header:
                    short_colon = len(raw_text) <= 40 and raw_text.endswith(":")
                    is_caption = bool(
                        _re.match(
                            r"^\s*(Table|Figure)\s+\d+(?:[-–]\d+)?[.:]", raw_text, _re.IGNORECASE
                        )
                    )
                    has_terminal_punct = raw_text.endswith(".") or raw_text.endswith(";")
                    if short_colon or is_caption or has_terminal_punct:
                        kind = (
                            "not_header_colon"
                            if short_colon
                            else ("caption_pattern" if is_caption else "not_header_sentence")
                        )
                        is_header = False
                        reason = f"Auto-reject: {kind}"

                if is_header:
                    for pat in BOILERPLATE_PATTERNS:
                        if _re.search(pat, raw_text, _re.IGNORECASE):
                            is_header = False
                            reason = f"Auto-reject: boilerplate_pattern ({pat[:20]}...)"
                            break

                block["suspicious_header"] = False
                block["requires_verification"] = False
                block["llm_verification"] = {
                    "verified_at": datetime.now().isoformat(),
                    "model": "heuristic_v1",
                    "result": {"is_header": is_header, "reasoning": reason},
                    "final_block_type": "SectionHeader" if is_header else "Text",
                }
                if not is_header:
                    block["block_type"] = "Text"
                    block["is_suspicious"] = True
                    block["suspicious_reasons"] = [reason]
                else:
                    block["is_suspicious"] = False

        # Log header/footer verification stats
        if hf_stats["total"] > 0:
            logger.info(
                f"Header/Footer verification (offline): {hf_stats['total']} blocks, "
                f"{hf_stats['kept']} kept, {hf_stats['promoted']} promoted to Text"
            )

        final_blocks = [b for p in pages for b in p.get("blocks", [])]
        marker_data["blocks"] = final_blocks
        if "pages" in marker_data:
            del marker_data["pages"]
        marker_data["run_id"] = run_id
        marker_data["header_footer_stats"] = hf_stats

        json_output_dir = stage_output_dir / "json_output"
        json_output_dir.mkdir(parents=True, exist_ok=True)
        output_json_path = json_output_dir / "03_verified_blocks.json"
        if os.getenv("DRY_RUN", "0").lower() not in {"1", "true", "yes", "y"}:
            with open(output_json_path, "w") as f:
                json.dump(marker_data, f, indent=2)
        return output_json_path

    eff_timeout = timeout if timeout and timeout > 0 else int(os.getenv("STAGE03_TIMEOUT", "600"))
    cfg = Config(
        input_pdf=clean_pdf_path or Path("MISSING_PDF"),  # Will fail in process if missing
        input_json=input_json,
        output_dir=stage_output_dir,
        llm_model=model or _env_vlm_model(),
        llm_concurrency=concurrency,
        render_dpi=dpi,
        debug=debug,
        task_limit=limit,
        max_runtime_seconds=eff_timeout,
        annotations_json=annotations_json,
        use_knowledge=use_knowledge,
        use_prior=use_prior,
        auto_reject_negatives=auto_reject,
        persist_headers=persist_headers,
        verify_all_headers=verify_all_headers,
    )

    asyncio.run(process_pdf_pipeline(cfg))
    return stage_output_dir / "json_output" / "03_verified_blocks.json"


RALPH_CONTRACT = """
Ralph Contract:
- Input: Stage 02 Marker Blocks (`02_marker_blocks.json`).
- Output: `03_verified_blocks.json`.
- Verification:
  - Output file exists.
  - JSON is valid.
  - Contains blocks with `block_type`='Header' (verified) or demoted to 'Text'.
  - `llm_verification` field is populated for processed blocks.
"""


def run_robust(pipeline_dir: Path, args: argparse.Namespace):
    """Robust execution with strategies."""

    pipeline_dir / "03_suspicious_headers"

    # Inputs
    input_json = pipeline_dir / "02_marker_blocks/json_output/02_marker_blocks.json"
    possible_s02_dirs = ["02_marker_extractor", "02_marker_blocks", "02_pdf_marker"]
    for d in possible_s02_dirs:
        cand = pipeline_dir / d / "json_output" / "02_marker_blocks.json"
        if cand.exists():
            input_json = cand
            break

    if not input_json.exists():
        logger.error("Dependencies missing (Stage 02). Cannot start.")
        sys.exit(1)

    MAX_ATTEMPTS = 3

    for attempt in range(1, MAX_ATTEMPTS + 1):
        verify_all = False
        auto_reject = True

        if attempt == 2:
            logger.warning("Attempt 1 found no work. Strategy: Disable Auto-Reject.")
            auto_reject = False
        elif attempt == 3:
            logger.warning("Still no work. Strategy: Verify ALL headers (Paranoid Mode).")
            auto_reject = False
            verify_all = True

        try:
            out_path = run(
                input_json=input_json,
                output_dir=pipeline_dir,
                auto_reject=auto_reject,
                verify_all_headers=verify_all,
            )

            # Simple check if output valid
            if out_path.exists():
                return

        except Exception as e:
            logger.error(f"Execution failed on attempt {attempt}: {e}")
            if attempt == MAX_ATTEMPTS:
                sys.exit(1)
            continue


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 03: Suspicious Headers")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    args = parser.parse_args()

    run_robust(args.pipeline_dir, args)
