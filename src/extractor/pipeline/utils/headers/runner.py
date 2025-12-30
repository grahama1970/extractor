"""
Stage 03 header processing pipeline.

Extracted from 03_suspicious_headers.py.
"""
import asyncio
import json
import os
import sys
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import fitz
from loguru import logger

STAGE03_COLOR_ENRICH = os.getenv("STAGE03_COLOR_ENRICH", "1").lower() in {"1", "true", "yes", "y"}

try:
    import psutil
except ImportError:
    psutil = None

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.diagnostics import (
    classify_llm_error,
    get_run_id,
    gpu_metrics_available,
    iso_now,
    make_event,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
from extractor.pipeline.utils.headers import (
    normalize_model_alias as _normalize_model_alias,
    verify_header_with_llm as _verify_header_with_llm,
    retrieve_prior_decisions as _retrieve_prior_decisions,
)
from extractor.pipeline.utils.suspicious_headers_utils import (
    ensure_first_span_color,
    norm_text,
    text_sha1,
)
from extractor.pipeline.utils.debug_utils import log_timing
from extractor.pipeline.utils.section_builder_utils import (
    pdf_analyze_section_numbering as _pdf_analyze_numbering,
    pdf_extract_section_title as _pdf_extract_title,
    is_probable_pdf_section_header as _is_probable_pdf_header,
)
from extractor.pipeline.utils.prompt_builder import build_llm_context

from extractor.pipeline.utils.scillm_router import get_text_router, get_vlm_router
from extractor.pipeline.steps.scillm_preflight_validator import quick_scillm_check
from extractor.pipeline.utils.model_params import build_chat_extras
from extractor.pipeline.utils.prompt_loader import load_prompt

# Load prompt
PROMPT = load_prompt("03_suspicious_headers")
SYSTEM_PROMPT = PROMPT.get("system", "You are an expert at analyzing PDF section headers.")


def _env_vlm_model(default: str = "") -> str:
    """SciLLM-only: prefer CHUTES_VLM_MODEL; do not consult LITELLM_* envs."""
    return (os.getenv("CHUTES_VLM_MODEL") or default).strip()


@dataclass
class Config:
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
        """Return (target, above, below) where above/below skip empty blocks.

        Empty means:
        - No text content (after strip) AND
        - No usable bbox (missing or zero area)

        Preference: textual neighbors; fallback to any block with a non-zero bbox
        within a small window.
        """

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
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
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

        # If neighbor is empty, scan up to ±5 blocks to find a non-empty one
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
        """Renders an image of the block and its neighbors, saves it, and returns base64.

        Also logs render timing and metadata to RUN_RESULTS_DIR/03_suspicious_headers/logs/timings.jsonl
        using attempt=context_render.
        """
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

        # ensure expanded rect stays within page bounds across PyMuPDF versions
        expanded_rect = expanded_rect & self.page_obj.rect

        matrix = fitz.Matrix(self.config.render_dpi / 72, self.config.render_dpi / 72)
        pix = self.page_obj.get_pixmap(matrix=matrix, clip=expanded_rect)  # type: ignore[attr-defined]

        # Save the image for inspection
        image_path = self.image_output_dir / f"suspicious_p{self.page_idx}_b{self.block_idx}.png"
        pix.save(str(image_path))

        # Also update the block with the path to its context image
        self.page_blocks[self.block_idx]["context_image_path"] = str(image_path)

        # IMPORTANT: Encode as PNG to match data URL type
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
                    "blocks_in_context": int(1 + (1 if above else 0) + (1 if below else 0)),
                    "w": getattr(pix, "width", None),
                    "h": getattr(pix, "height", None),
                    "image_pixels": (getattr(pix, "width", 0) or 0) * (getattr(pix, "height", 0) or 0),
                    "b64_bytes": len(b64),
                    "render_cache": "miss",
                },
            )
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            pass
        return b64

    def build_dataset_record(
        self,
        *,
        context_text: str,
        final_label: bool,
        label_source: str,
        reasoning: str = "",
    ) -> dict[str, Any]:
        target, above, below = self.get_context_blocks()
        t_text = (target.get("text") or target.get("content") or "").strip()
        fs = target.get("first_span_font") or {}
        font_sig = f"{fs.get('name') or '?'}|{fs.get('size') or '?'}|{'b' if fs.get('bold') else 'n'}{'i' if fs.get('italic') else 'n'}|{fs.get('color_bucket') or '?'}"
        rec = {
            "doc_path": str(self.config.input_pdf),
            "json_path": str(self.config.input_json),
            "page_idx": int(self.page_idx),
            "block_idx": int(self.block_idx),
            "header_text": t_text,
            "header_text_norm": norm_text(t_text),
            "text_sha1": text_sha1(t_text + "|" + font_sig),
            "font_signature": font_sig,
            "context_text": context_text,
            "label_is_header": bool(final_label),
            "label_source": label_source,
            "reasoning": reasoning or "",
            "timestamp": datetime.now().isoformat(),
            "text_only": os.getenv("STAGE03_TEXT_ONLY", "1").lower() in ("1", "true", "yes", "y"),
        }
        # Include saved context image path if present
        try:
            rec["context_image_path"] = target.get("context_image_path")
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            pass
        return rec

async def process_pdf_pipeline(config: Config):
    """
    Stage 03 orchestrator: verify suspicious headers with a vision-capable LLM.

    Phases:
    1) Init: set up output dirs; load Stage 02 JSON + PDF; normalize to pages.
    2) Annotations: index by page; compute concise human-cue summaries (and global negatives); set source_pdf.
    3) Candidate discovery: collect suspicious headers; optionally include all SectionHeaders.
    4) Preflight: render one real candidate context image; probe selected model for vision support.
       Note: this sends a placeholder text ("Preflight vision capability check.") with the image only to test provider support; the
       response is ignored and NOT used for any header decision.
    5) Preparation: for each candidate, choose context neighbors (±5 scan), compute human cues (with optional auto-reject),
       render a context image, and build the textual prompt.
    6) LLM batch: call litellm in one batch with concurrency and optional timeout; parse JSON responses; map errors to safe defaults.
    7) Apply: update the block type (Text on reject), clear the suspicious_header flag, write llm_verification, update suspicion fields,
       and optionally persist results to ArangoDB if configured.
    8) Save: flatten pages back to a top-level blocks list and write 03_verified_blocks.json.

    Side effects:
    - Writes context images to image_output/ for each candidate.
    - Writes final JSON to json_output/.

    Flags of note:
    - verify_all_headers: include every SectionHeader as a candidate.
    - use_knowledge / auto_reject_negatives: use on-page annotation cues; can skip LLM on strong negatives.
    - llm_concurrency / max_runtime_seconds: batch performance controls.
    - write_suspicion_fields: reflect outcomes in suspicion_* fields.
    """
    # 1) Init — inputs and output layout
    warnings.filterwarnings(
        "ignore",
        message="Task was destroyed but it is pending",
        category=RuntimeWarning,
    )
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0

    print(f"Verifying suspicious headers in '{config.input_json.name}'...")
    stage_start_ts = datetime.now().isoformat()
    t_stage0 = time.monotonic()
    resources = snapshot_resources("start")

    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "03_suspicious_headers",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_start"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_start"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass

    # Define clear output paths
    json_output_dir = config.output_dir / "json_output"
    image_output_dir = config.output_dir / "image_output"
    json_output_dir.mkdir(parents=True, exist_ok=True)
    image_output_dir.mkdir(parents=True, exist_ok=True)

    # Load Stage 02 JSON
    with open(config.input_json) as f:
        marker_data = json.load(f)

    try:
        pdf_doc = fitz.open(config.input_pdf)
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        print(f"Failed to open PDF {config.input_pdf}: {e}")
        return {"success": False, "error": str(e)}

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

    # 2) Annotations — index by page, build global cue summary
    annotations_by_page: dict[int, list[dict[str, Any]]] = {}
    global_negative_examples_summary: str | None = None
    ann_index = None
    if config.annotations_json and config.annotations_json.exists():
        try:
            with open(config.annotations_json) as af:
                a_payload = json.load(af)
            for a in a_payload.get("annotations", []):
                p = int(a.get("page", -1))
                if p >= 0:
                    annotations_by_page.setdefault(p, []).append(a)
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            logger.warning(f"Failed to load annotations from {config.annotations_json}: {e}")

    # Load saved FAISS index from Stage 01 if present; else build ephemeral
    # NOTE: Removed misplaced FAISS/negatives block that executed at import time.
    # Annotation FAISS indexing and global negatives are handled inside process_pdf_pipeline.

    # 3) Candidate discovery — suspicious headers and fallbacks (or verify-all)
    # Preflight happens once we know we have candidates.

    # Pre-enrich blocks with numbering spans and optional color once per block
    text_only_mode = os.getenv("STAGE03_TEXT_ONLY", "1").lower() in ("1", "true", "yes", "y")
    if STAGE03_COLOR_ENRICH or True:  # numbering spans always enabled
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
                    if STAGE03_COLOR_ENRICH:
                        ensure_first_span_color(page_obj, block)
                except Exception as exc:
                    log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                    raise
                    continue

    # Identify candidate tasks (suspicious headers, suspicious SectionHeaders, or all SectionHeaders with --verify-all-headers)
    tasks: list[VerificationTask] = []
    for p_idx, page_data in enumerate(marker_data.get("pages", [])):
        page_blocks = page_data.get("blocks", [])
        for b_idx, block in enumerate(page_blocks):
            sh_flag = bool(block.get("suspicious_header") is True)
            # Fallback: treat SectionHeader with is_suspicious True (or header-related reasons) as candidates
            fallback_header_susp = (block.get("block_type") == "SectionHeader") and (
                bool(block.get("is_suspicious"))
                or any("header" in str(r).lower() for r in (block.get("suspicious_reasons") or []))
            )
            verify_all = bool(getattr(config, "verify_all_headers", False)) and (
                block.get("block_type") == "SectionHeader"
            )
            if sh_flag or fallback_header_susp or verify_all:
                tasks.append(
                    VerificationTask(
                        page_idx=p_idx,
                        block_idx=b_idx,
                        page_blocks=page_blocks,
                        page_obj=pdf_doc[p_idx],
                        config=config,
                        image_output_dir=image_output_dir,  # Pass image dir to task
                    )
                )

    # Optional limit for human debugging
    total_before = len(tasks)
    if config.task_limit and config.task_limit > 0:
        tasks = tasks[: config.task_limit]
        logger.info(
            f"Limiting suspicious header verifications to first {len(tasks)} of {total_before}"
        )

    if not tasks:
        print("No suspicious headers found to verify.")
        # Still save a result file for consistency
        output_json_path = json_output_dir / "03_verified_blocks.json"
        marker_data["run_id"] = run_id
        # Derive counts from diagnostics severities
        try:
            _err = sum(1 for _d in (diagnostics or []) if str(_d.get("severity")) == "error")
            _wrn = sum(1 for _d in (diagnostics or []) if str(_d.get("severity")) == "warning")
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            _err, _wrn = errors_count, warnings_count
        marker_data["errors_count"] = _err
        marker_data["warnings_count"] = _wrn
        marker_data["diagnostics"] = diagnostics
        with open(output_json_path, "w") as f:
            json.dump(marker_data, f, indent=2)
        print(f"Saved unmodified data to: {output_json_path}")
        pdf_doc.close()
        return

    print(f"Found {len(tasks)} suspicious headers. Starting verification...")
    # Log batch-level effective model + extras once
    try:
        eff_model = _normalize_model_alias(config.llm_model)
        eff_extras = build_chat_extras(eff_model)
        logger.info(f"stage03.batch: effective_model={eff_model} extras_keys={list(eff_extras.keys())}")
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass
    try:
        diagnostics.append(
            make_event(
                "03_suspicious_headers",
                "info",
                "vision_preflight_ok",
                f"Model supports vision: {config.llm_model}",
                {"tasks": len(tasks)},
            )
        )
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass

    # 4) Preflight — verify model supports vision using a real candidate clip
    # (Tiny images can be rejected by providers; we use an actual context image.)
    # Preflight (skip when text-only)
    try:
        if os.getenv("STAGE03_TEXT_ONLY", "1").lower() not in ("1", "true", "yes", "y"):
            sample_image_b64 = tasks[0].render_context_image_b64()
            t_pf0 = time.monotonic()
            _ = await _verify_header_with_llm(
                sample_image_b64, "Preflight vision capability check.", config.llm_model
            )
            preflight_duration_ms = int((time.monotonic() - t_pf0) * 1000)
            try:
                import os as _os
                _os.environ["VISION_PREFLIGHT_ASSUME_OK"] = "1"
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                pass
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pdf_doc.close()
        raise RuntimeError(f"Selected model does not support vision or call failed: {e}")

    # Prior decisions disabled: ArangoDB deferred to Step 10+
    def _normalize_header_text(t: str) -> str:
        import re

        s = (t or "").strip().lower()
        # drop excessive whitespace
        s = " ".join(s.split())
        # strip leading numbering like "4.1.2" or "(iv)" or "a)": keep words
        s = re.sub(r"^(\(?[ivx]+\)|\d+(?:[\.-]\d+)*|[a-z]\)|[a-z]\.)\s+", "", s)
        return s

    def _font_signature(b: dict[str, Any]) -> str:
        fs = b.get("first_span_font") or {}
        name = str(fs.get("name") or "?")
        size = fs.get("size")
        size = f"{float(size):.1f}" if isinstance(size, (int, float)) else str(size or "?")
        bold = "b" if fs.get("bold") else "n"
        italic = "i" if fs.get("italic") else "n"
        color = str(fs.get("color_bucket") or "?")
        return f"{name}|{size}|{bold}{italic}|{color}"

        # NOTE: Removed stray ArangoDB persistence block. DB export is deferred to later stages.

    # 5) Prepare prompts — compute cues, optional auto-reject, render image, build context
    prepared: list[dict[str, Any]] = []
    task_refs: list[VerificationTask] = []
    prepared_ctx: list[str] = []
    auto_results: dict[int, dict[str, Any]] = {}

    for idx, task in enumerate(tasks):
        try:
            target_block, above_block, below_block = task.get_context_blocks()
            # --- Heuristic guardrails BEFORE any LLM call ---
            # Demote common false positives early to reduce noise and cost.
            try:
                import re as _re
                raw_text = (target_block.get("text") or "").strip()
                # Auto-ACCEPT: strict 'numbering Title.' line = 100% header
                try:
                    hdr = _is_probable_pdf_header(raw_text, target_block.get("first_span_font") or {})
                    if hdr.get("is_header") and hdr.get("confidence") >= 0.999 and hdr.get("reason") and "strict_numbered_title_period" in hdr.get("reason"):
                        auto_results[idx] = {
                            "is_header": True,
                            "reasoning": "Auto-accept: strict_numbered_title_period",
                            "auto": True,
                        }
                        # Attach spans so downstream can rely on them
                        if hdr.get("spans"):
                            target_block["header_char_spans"] = hdr["spans"]
                            target_block.setdefault("header_title", hdr.get("title"))
                        continue
                except Exception as exc:
                    log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                    raise
                    pass
                # Accept classic numbered headings like "1.1.1 Section Title"
                is_numbered = bool(_re.match(r"^\s*\d+(?:[\.-]\d+){1,}\s+\S", raw_text))
                # Short colon label (wrapper) — e.g., "Mergeable Tables:" — often not a true header
                short_colon = len(raw_text) <= 40 and raw_text.endswith(":")
                bullet_prefix = raw_text.startswith("•") or raw_text.startswith("●")
                # Captions that look like Table/Figure labels
                is_caption = bool(
                    _re.match(r"^\s*(Table|Figure)\s+\d+(?:[-–]\d+)?[.:]", raw_text, _re.IGNORECASE)
                )
                # Sentence-like content rarely is a section header
                has_terminal_punct = raw_text.endswith(".") or raw_text.endswith(";")
                # If it is not numbered and matches one of the strong negative patterns, auto-reject
                if (not is_numbered) and (short_colon or is_caption or has_terminal_punct):
                    kind = 'not_header_colon' if short_colon else ('caption_pattern' if is_caption else 'not_header_sentence')
                    auto_results[idx] = {
                        "is_header": False,
                        "reasoning": f"Auto-reject: {kind}",
                        "debug_kind": kind,
                        "auto": True,
                    }
                    continue
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                pass
            # Optional FAISS advisory cue: similar annotations
            try:
                if ann_index is not None:
                    qtext = (target_block.get("text") or "")[:500]
                    sims = query_ann_index(ann_index, qtext, top_k=3)
                    if sims:
                        diagnostics.append(
                            make_event(
                                "03_suspicious_headers",
                                "info",
                                "ann_similar_support",
                                "Similar annotations found",
                                {"top_k": len(sims)},
                            )
                        )
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                pass

            # --- Build human annotations cues (if available) ---
            human_summary = None
            auto_reject = False
            auto_reason = ""
            if config.use_knowledge and annotations_by_page:
                anns = annotations_by_page.get(task.page_idx, [])
                cues: list[tuple[int, float, str]] = []
                bb = cast(list[float], target_block.get("bbox") or [0, 0, 0, 0])

                def _is_relevant_03(a: dict[str, Any]) -> bool:
                    try:
                        return "03" in (a.get("relevant_to") or [])
                    except Exception as exc:
                        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                        raise
                        return False

                anns_sorted = sorted(anns, key=lambda x: (not _is_relevant_03(x)))
                any_relevant_negative = False
                for a in anns_sorted:
                    rect = cast(list[float], a.get("expanded_rect") or a.get("original_rect") or [])
                    if not rect:
                        continue
                    overlap = _rect_overlap_ratio(bb, rect)
                    if overlap < 0.05:
                        continue
                    pol, st, lbl = _cue_from_annotation(a)
                    if pol != 0:
                        weight = st * min(1.0, 0.5 + overlap)
                        try:
                            if _is_relevant_03(a):
                                boost = float(
                                    (
                                        RELEVANT_RULES.get("boost_relevant_weight_for_stage") or {}
                                    ).get("03", 1.25)
                                )
                                weight = min(1.0, weight * boost)
                                if pol < 0:
                                    any_relevant_negative = True
                        except Exception as exc:
                            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                            raise
                            pass
                        cues.append((pol, weight, lbl))
                human_summary, _ = _summarize_cues(cues)
                if config.auto_reject_negatives and cues:
                    default_th = float(
                        (RELEVANT_RULES.get("auto_reject_thresholds") or {}).get("default", 0.85)
                    )
                    crucial_th = float(
                        (RELEVANT_RULES.get("auto_reject_thresholds") or {}).get(
                            "relevant_03", 0.75
                        )
                    )
                    threshold = crucial_th if any_relevant_negative else default_th
                    for pol, st, lbl in cues:
                        if pol < 0 and st >= threshold:
                            auto_reject = True
                            auto_reason = f"Auto-reject due to {'RELEVANT ' if any_relevant_negative else ''}negative human cue: {lbl} ({st:.2f})"
                            break

            # --- Prior decisions retrieval (optional, read-only) ---
            prior_summary = None
            if getattr(config, "use_prior", True):
                try:
                    tnorm = _normalize_header_text(target_block.get("text") or "")
                    fsig = _font_signature(target_block)
                    priors = _retrieve_prior_decisions(tnorm, fsig, limit=5)
                    if priors:
                        rej = [
                            p
                            for p in priors
                            if p.get("is_header") is False and (p.get("confidence") or 0) >= 0.85
                        ]
                        acc = [
                            p
                            for p in priors
                            if p.get("is_header") is True and (p.get("confidence") or 0) >= 0.85
                        ]
                        lines = []
                        if rej:
                            lines.append(f"Prior rejects: {len(rej)} (>=0.85 conf)")
                        if acc:
                            lines.append(f"Prior accepts: {len(acc)} (>=0.85 conf)")
                        prior_summary = "; ".join(lines) or f"Prior matches: {len(priors)}"
                        # Auto-reject based on strong prior evidence
                        if config.auto_reject_negatives and len(rej) >= 2:
                            auto_reject = True
                            auto_reason = (
                                f"Auto-reject due to prior decisions: {len(rej)} strong rejections"
                            )
                except Exception as exc:
                    log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                    raise
                    logger.debug(f"Prior processing failed: {e}")

            combined_human_summary = human_summary
            if global_negative_examples_summary:
                combined_human_summary = (
                    human_summary + "\n\n" if human_summary else ""
                ) + global_negative_examples_summary
            if prior_summary:
                combined_human_summary = (
                    combined_human_summary + "\n\n" if combined_human_summary else ""
                ) + f"Prior Decisions: {prior_summary}"

            if auto_reject:
                auto_results[idx] = {"is_header": False, "reasoning": auto_reason}
                continue

            # Render context image only when not in text-only mode
            text_only = os.getenv("STAGE03_TEXT_ONLY", "1").lower() in ("1", "true", "yes", "y")
            image_b64 = task.render_context_image_b64() if not text_only else ""
            context_text = build_llm_context(
                target_block,
                above_block,
                below_block,
                human_annotations_summary=combined_human_summary,
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": context_text},
                        *(
                            [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}]
                            if (not text_only and image_b64)
                            else []
                        ),
                    ],
                },
            ]
            # Inject normalized model id + provider/json extras per prepared item
            # Inject normalized model id
            try:
                _m_eff = _normalize_model_alias(config.llm_model)
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                _m_eff = config.llm_model
            prepared.append(
                {
                    "model": _m_eff,
                    "image_b64": image_b64,
                    "context_text": context_text,
                }
            )
            task_refs.append(task)
            prepared_ctx.append(context_text)

        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            logger.exception(
                f"Preparation failed for page {task.page_idx} block {task.block_idx}: {e}"
            )
            auto_results[idx] = {"is_header": True, "reasoning": f"Preparation error: {e}"}

    # 6) Hand-off to Stage 03b: Mark candidates for verification
    # We have 'prepared' items (LLM ready) and 'auto_results' (heuristic decisions).
    
    # helper to find metadata
    task_map = {id(t): t for t in tasks}

    # Apply Auto-Results immediately
    for idx, res in auto_results.items():
        task = tasks[idx]
        block = marker_data["pages"][task.page_idx]["blocks"][task.block_idx]
        
        is_header = res.get("is_header", False)
        reason = res.get("reasoning", "")
        
        block["suspicious_header"] = False # Decision made
        block["requires_verification"] = False
        block["llm_verification"] = {
            "verified_at": datetime.now().isoformat(),
            "model": "heuristic_v1",
            "result": res,
            "original_block_type": "SectionHeader",
            "final_block_type": "SectionHeader" if is_header else "Text"
        }
        if not is_header:
            block["block_type"] = "Text"
            block["is_suspicious"] = True
            block["suspicious_reasons"] = [reason]
        else:
            block["is_suspicious"] = False
            
    # Mark LLM Candidates
    for idx, prep in enumerate(prepared):
        # We need to map back to the block. 
        # We tracked 'task_refs' parallel to 'prepared'.
        task = task_refs[idx]
        block = marker_data["pages"][task.page_idx]["blocks"][task.block_idx]
        
        block["requires_verification"] = True
        # prompt_context contains the text we built for the LLM
        block["prompt_context"] = prep["context_text"]
        
        # Ensure image path is persisted (it was set in task_blocks during render, so it should be there)
        # But let's double check task.page_blocks IS the source of truth ref? 
        # Yes, task.page_blocks = page_blocks = page_data["blocks"]. It is a ref.

    # 7) Save Markup
    # Flatten the pages structure back to a simple list of blocks
    final_blocks = [block for page in marker_data["pages"] for block in page["blocks"]]
    
    marker_data["blocks"] = final_blocks
    del marker_data["pages"]

    marker_data["run_id"] = run_id
    # Clear old counts or set to 0
    marker_data["errors_count"] = errors_count
    marker_data["warnings_count"] = warnings_count
    marker_data["diagnostics"] = diagnostics
    
    stage_end_ts = datetime.now().isoformat()
    
    # Simple timings
    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": stage_end_ts,
        "stage_duration_ms": int((time.monotonic() - t_stage0) * 1000),
        "candidates_found": len(prepared),
        "auto_resolved": len(auto_results),
    }
    marker_data["timings"] = timings
    marker_data["resources"] = resources

    # Write output unless DRY_RUN=1
    output_json_path = json_output_dir / "03_markup.json"
    if os.getenv("DRY_RUN", "0").lower() not in {"1","true","yes","y"}:
        with open(output_json_path, "w") as f:
            json.dump(marker_data, f, indent=2)
        print(f"\nCandidate generation complete. Markup saved to: {output_json_path}")
    else:
        print("[03] DRY_RUN=1 → skipped writing json_output")



# ------------------------------------------------------------------
# COMMAND-LINE INTERFACE
# ------------------------------------------------------------------
