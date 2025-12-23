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

    # 6) LLM batch — verify and collect JSON payloads (scillm + Chutes x-api-key)
    llm_payloads: list[dict[str, Any]] = []
    if prepared:
        try:
            t_llm0 = time.monotonic()
            try:
                _verify_cap = int(os.getenv("STAGE03_VERIFY_MAX_TOKENS", "256"))
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                _verify_cap = 256


            async def _process_item(item: dict) -> dict:
                return await _verify_header_with_llm(
                    item["image_b64"],
                    item["context_text"],
                    item["model"],
                    item_timeout=config.item_timeout_seconds,
                )

            results = await process_items_concurrently(
                prepared,
                _process_item,
                description="Verifying Headers",
            )
            llm_batch_duration_ms = int((time.monotonic() - t_llm0) * 1000)
        except TimeoutError as e:
            logger.error(f"Stage 03 model calls timed out after {config.max_runtime_seconds}s")
            info = classify_llm_error(e)
            try:
                diagnostics.append(
                    make_event(
                        "03_suspicious_headers",
                        "error",
                        info["code"],
                        info["message"],
                        {"prepared": len(prepared)},
                    )
                )
                errors_count += 1
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                pass
            results = [
                json.dumps({"error": {"type": "Timeout", "message": info.get("message")}})
            ] * len(prepared)
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            logger.error(f"Stage 03 model calls failed: {e}")
            info = classify_llm_error(e)
            try:
                diagnostics.append(
                    make_event(
                        "03_suspicious_headers",
                        "error",
                        info["code"],
                        info["message"],
                        {"prepared": len(prepared)},
                    )
                )
                errors_count += 1
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                pass
            results = [
                json.dumps({"error": {"type": type(e).__name__, "message": info.get("message")}})
            ] * len(prepared)

        for ans in results:
            try:
                # ans is already a dict from _verify_header_with_llm (or empty dict on error fallback)
                llm_payloads.append(ans if isinstance(ans, dict) else {})
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                llm_payloads.append({})

    # 7) Apply results back to blocks — update types, suspicion fields, persist
    parse_error_count = 0
    prep_idx = 0
    for idx, task in enumerate(tasks):
        # Determine result (auto or from batch)
        if idx in auto_results:
            llm_result = auto_results[idx]
        else:
            payload = llm_payloads[prep_idx] if prep_idx < len(llm_payloads) else {}
            prep_idx += 1
            if payload.get("error"):
                # Keep header on model error but record reasoning
                err = payload["error"]
                llm_result = {
                    "is_header": True,
                    "reasoning": f"LLM error: {err.get('type')}: {err.get('message')}",
                }
            else:
                payload = cast(dict[str, Any], payload)
                if payload.get("is_header") is None:
                    payload["is_header"] = True
                if payload.get("reasoning") is None:
                    payload["reasoning"] = ""
                llm_result = payload

        # Count parse_error soft-fails for observability/thresholds
        try:
            if str(llm_result.get("reasoning", "")).strip() == "parse_error":
                parse_error_count += 1
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            pass

        # Update JSON in place
        block_to_update = marker_data["pages"][task.page_idx]["blocks"][task.block_idx]
        is_header = bool(llm_result.get("is_header", True))
        if not is_header:
            block_to_update["block_type"] = "Text"

        block_to_update["suspicious_header"] = False
        block_to_update["llm_verification"] = {
            "verified_at": datetime.now().isoformat(),
            "model": config.llm_model,
            "result": llm_result,
            "original_block_type": "SectionHeader",
            "final_block_type": block_to_update["block_type"],
        }

        # Use a dedicated flag to control writing suspicion fields
        if config.write_suspicion_fields:
            if is_header:
                block_to_update["is_suspicious"] = False
                block_to_update["suspicious_reasons"] = []
                block_to_update["suspicion_confidence"] = 0.0
                block_to_update["requires_review"] = False
            else:
                block_to_update["is_suspicious"] = True
                reasons = block_to_update.get("suspicious_reasons") or []
                if "llm_verification_reject" not in [str(r) for r in reasons]:
                    reasons.append("llm_verification_reject")
                block_to_update["suspicious_reasons"] = reasons
                # If model returned a confidence field, prefer it; else set a default high suspicion
                try:
                    conf = llm_result.get("confidence")
                    block_to_update["suspicion_confidence"] = (
                        float(conf) if isinstance(conf, (int, float)) else 0.9
                    )
                except Exception as exc:
                    log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                    raise
                    block_to_update["suspicion_confidence"] = 0.9
                block_to_update["requires_review"] = True

        # Dataset dump (for future finetuning)
        try:
            ds_enabled = os.getenv("STAGE03_DUMP_DATASET", "1").lower() in ("1", "true", "yes", "y")
            if ds_enabled:
                # Use aligned prepared context text when not auto; otherwise rebuild minimal
                try:
                    if idx in auto_results:
                        tgt, abv, bel = task.get_context_blocks()
                        ctx = build_llm_context(tgt, abv, bel)
                    else:
                        ctx = prepared_ctx[prep_idx - 1] if (prep_idx - 1) < len(prepared_ctx) else ""
                except Exception as exc:
                    log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                    raise
                    ctx = ""
                rec = task.build_dataset_record(
                    context_text=ctx,
                    final_label=bool(is_header),
                    label_source=("heuristic_auto" if idx in auto_results else "llm"),
                    reasoning=str((llm_result or {}).get("reasoning") or ""),
                )
                ds_dir = Path(os.getenv("STAGE03_DATASET_DIR", str(config.output_dir / "datasets" / "suspicious_headers")))
                ds_dir.mkdir(parents=True, exist_ok=True)
                run_file = ds_dir / f"{run_id}.jsonl"
                with open(run_file, "a", encoding="utf-8") as fp:
                    fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            logger.warning(f"dataset_dump_failed: {_e}")
    pdf_doc.close()

    # 8) Save the updated JSON — flatten pages to top-level blocks
    output_json_path = json_output_dir / "03_verified_blocks.json"

    # Flatten the pages structure back to a simple list of blocks
    final_blocks = [block for page in marker_data["pages"] for block in page["blocks"]]
    # Policy guardrail: demote any remaining SectionHeader whose text ends with ':' or ';'
    # and any title containing '(continued)' or '- Continued'.
    try:
        import re as _re
        for b in final_blocks:
            bt = b.get("type") or b.get("block_type")
            if bt != "SectionHeader":
                continue
            txt = (b.get("text") or b.get("content") or "").strip()
            low = txt.lower()
            if txt.endswith(":") or txt.endswith(";") or "(continued" in low or "- continued" in low:
                # Demote to Text
                b["block_type"] = "Text"
                b["type"] = "Text"
                # Clear any prior header flags
                if b.get("suspicious_header"):
                    b["suspicious_header"] = False
                b.setdefault("llm_verification", {})
                b["llm_verification"]["result"] = {"is_header": False, "reasoning": "policy_auto_reject_colon_semicolon_or_continued"}
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass
    marker_data["blocks"] = final_blocks
    del marker_data["pages"]

    marker_data["run_id"] = run_id
    marker_data["errors_count"] = errors_count
    marker_data["warnings_count"] = warnings_count
    marker_data["diagnostics"] = diagnostics
    stage_end_ts = datetime.now().isoformat()
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_end"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_end"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass
    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": stage_end_ts,
        "stage_duration_ms": int((time.monotonic() - t_stage0) * 1000),
        "preflight_duration_ms": int(locals().get("preflight_duration_ms", 0)),
        "llm_batch_duration_ms": int(locals().get("llm_batch_duration_ms", 0)),
    }
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass
    marker_data["timings"] = timings
    marker_data["resources"] = resources
    # Threshold policy for parse errors
    try:
        warn_frac = float(os.getenv("PARSE_WARN_FRAC", "0.05"))
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        warn_frac = 0.05
    try:
        fail_frac = float(os.getenv("PARSE_FAIL_FRAC", "0.20"))
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        fail_frac = 0.20
    total_verified = max(1, len(tasks) - len(auto_results))
    parse_rate = parse_error_count / float(total_verified)

    # Write output unless DRY_RUN=1
    if os.getenv("DRY_RUN", "0").lower() not in {"1","true","yes","y"}:
        with open(output_json_path, "w") as f:
            json.dump(marker_data, f, indent=2)
        print(f"\nVerification complete. Updated JSON saved to: {output_json_path}")
    else:
        print("[03] DRY_RUN=1 → skipped writing json_output (logs/timings still recorded)")

    # Summarize timings.jsonl → timings_summary.json (best-effort)
    try:
        from pathlib import Path as _P
        rd = os.getenv("RUN_RESULTS_DIR")
        if rd:
            logs_dir = _P(rd) / "03_suspicious_headers" / "logs"
            tfile = logs_dir / "timings.jsonl"
            if tfile.exists():
                lat = []
                attempts = 0
                ok = 0
                exc = 0
                for line in tfile.read_text(encoding="utf-8").splitlines():
                    try:
                        rec = json.loads(line)
                        attempts += 1
                        if str(rec.get("outcome")) == "ok":
                            ok += 1
                        if str(rec.get("outcome")) == "exception":
                            exc += 1
                        if rec.get("latency_ms") is not None:
                            lat.append(float(rec["latency_ms"]))
                    except Exception as exc:
                        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                        raise
                        continue
                lat_sorted = sorted(lat)
                def _pct(p: float) -> float:
                    if not lat_sorted:
                        return 0.0
                    idx = int(max(0, min(len(lat_sorted)-1, round(p * (len(lat_sorted)-1)))))
                    return float(lat_sorted[idx])
                summary = {
                    "attempts": attempts,
                    "ok": ok,
                    "exceptions": exc,
                    "parse_error_count": parse_error_count,
                    "parse_error_rate": round(parse_rate, 4),
                    "p50_ms": _pct(0.50),
                    "p95_ms": _pct(0.95),
                }
                (logs_dir / "timings_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass

    # Enforce thresholds: warn vs fail
    if parse_rate >= fail_frac:
        raise RuntimeError(
            f"Stage 03 parse_error rate {parse_rate:.2%} exceeded fail threshold {fail_frac:.0%}"
        )
    if parse_rate >= warn_frac:
        print(
            f"[03] Warning: parse_error rate {parse_rate:.2%} exceeded warn threshold {warn_frac:.0%}"
        )


# ------------------------------------------------------------------
# COMMAND-LINE INTERFACE
# ------------------------------------------------------------------
