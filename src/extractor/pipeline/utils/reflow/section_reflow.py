"""
Core section reflow logic extracted from 07_reflow_section.py.

This module contains the main reflow_section_with_llm function and related helpers.
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.diagnostics import (
    classify_llm_error,
    iso_now,
    make_event,
)
from extractor.pipeline.utils.image_io import (
    get_annotation_image_b64,
    get_figure_image_b64,
    get_section_image_b64,
    get_table_image_b64,
)
from extractor.pipeline.utils.json_utils import (
    MAX_TOKENS_IMAGE,
    STOP_FENCES,
    STRICT_JSON_GUARD,
    clean_json_string,
    parse_json_strict,
    restrict_top_level_keys,
)
from extractor.pipeline.utils.model_select import get_vlm_model, get_text_model
from extractor.pipeline.utils.debug_utils import ensure_logs_dir, time_block, summarize_messages, log_timing
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.text_utils import sanitize_text
from extractor.pipeline.utils.log_utils import sanitize_messages_for_return
from extractor.pipeline.utils.model_params import build_chat_extras

from extractor.pipeline.utils.reflow import (
    sanitize_table_cell as _sanitize_table_cell,
    compute_table_confidence as _table_confidence,
    compute_table_merges as _compute_table_merges,
    build_table_block_from_stage05 as _build_table_block_from_stage05,
    df_map as _df_map,
    normalize_table_text as _normalize_table_text,
    iou_rect as _iou_rect,
    horizontal_iou as _h_iou,
    build_figure_block_from_stage06 as _build_figure_block_from_stage06,
    apply_layout_ordering as _apply_layout_ordering,
    extract_router_content as _router_content,
    content_to_json_dict as _content_to_json_dict,
    direct_scillm_json as _direct_scillm_json,
    get_usage_field as _usage_get,
    build_reflow_prompt,
    build_compact_prompt as _build_compact_prompt,
    build_compact_prompt_simple as _build_compact_prompt_simple,
    merge_section_tables as _merge_section_tables,
)

# Module-level configuration (set by caller)
LLM_MODEL = None
USE_LAYOUT_SKETCH = True
OMIT_IMAGES_IF_CONFIDENT = True
LAYOUT_CONF_THRESH = 0.8
STAGE07_MAX_TOKENS = 4096

async def reflow_section_with_llm(
    section_data: dict[str, Any],
    results_base_dir: Path,
    *,
    include_images: bool,
    allow_fallback: bool,
    llm_timeout: int = 60,
) -> dict[str, Any]:
    """Reflow a section using multimodal context (section/table/figure/annotation) and return structured JSON."""
    # Respect allow-images toggle (default text-only). Per-section gating may still disable images.
    _ALLOW_IMAGES = os.getenv("STAGE07_ALLOW_IMAGES", "0").lower() in ("1", "true", "yes", "y")
    include_images = bool(include_images and _ALLOW_IMAGES)
    # Ensure text model is selected even when debug-bundle bypasses run()
    global LLM_MODEL
    try:
        LLM_MODEL = get_text_model()
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        pass
    try:
        sec_diags = []

        # use shared helper

        # Decide if the model supports multimodal inputs
        supports_vision = any(
            kw in (LLM_MODEL or "").lower()
            for kw in (
                "gpt-5",
                "gpt-4o",
                "gpt-4.1",
                "gpt-4-vision",
                "claude-3",
                "gemini",
                "llava",
                "qwen-vl",
                "grok-vision",
            )
        )

        # Layout-based gating: omit images when we have a confident layout prior
        try:
            if include_images and USE_LAYOUT_SKETCH and OMIT_IMAGES_IF_CONFIDENT:
                conf = float(((section_data.get("layout_sketch") or {}).get("conf") or {}).get("ordering") or 0.0)
                if conf >= LAYOUT_CONF_THRESH:
                    include_images = False
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "info",
                                "images_omitted_due_to_layout_conf",
                                f"ordering_conf={conf}",
                                {},
                            )
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass

        # Build textual context
        context_text = build_section_context_text(section_data)
        try:
            # Optional context trim for initial warm-up with providers that can stall on very long first calls
            trim_env = os.getenv("STAGE07_TRIM_CHARS")
            if trim_env:
                n = int(trim_env)
                if n > 0:
                    context_text = context_text[:n]
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass
        # Enforce vision requirement before constructing images

        # Build user content (text + images if supported)
        user_content: Any
        image_blocks: list[dict[str, Any]] = []
        # Optionally perform a lightweight preflight to avoid large failed calls
        if include_images:
            try:
                ok = await preflight_vision_support(LLM_MODEL, timeout_sec=10)
                if ok:
                    supports_vision = True
                else:
                    supports_vision = False
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        sec_b64 = None
        anns = []
        sec_b64 = None
        if supports_vision and include_images:
            # Section visual
            sec_b64 = get_section_image_b64(section_data, results_base_dir)
            if sec_b64:
                image_blocks.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{sec_b64}"}}
                )
                try:
                    sec_diags.append(
                        make_event(
                            "07_reflow_section",
                            "info",
                            "section_image_attached",
                            "Included section image",
                            {},
                        )
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass

            # Table images: include only low-confidence tables
            for t in section_data.get("tables", []) or []:
                conf = _table_confidence(t)
                if conf < TABLE_CONF_THRESHOLD:
                    tb64 = get_table_image_b64(t, results_base_dir)
                    if tb64:
                        try:
                            sec_diags.append(
                                make_event(
                                    "07_reflow_section",
                                    "info",
                                    "table_image_attached",
                                    "Included table image (low confidence)",
                                    {"table_index": t.get("table_index"), "confidence": conf},
                                )
                            )
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            pass
                        image_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{tb64}"},
                            }
                        )
            # Figure images (optional via env)
            if INCLUDE_FIGURE_IMAGES:
                for f in section_data.get("figures", [])[:2]:
                    fb64 = get_figure_image_b64(f, results_base_dir)
                    if fb64:
                        try:
                            sec_diags.append(
                                make_event(
                                    "07_reflow_section",
                                    "info",
                                    "figure_image_attached",
                                    "Included figure image",
                                    {"figure_id": f.get("figure_id")},
                                )
                            )
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            pass
                        image_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{fb64}"},
                            }
                        )

            # Annotation images: include top-K by similarity/text length
            def _ann_score(a):
                try:
                    sim = float(a.get("similarity") or 0.0)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    sim = 0.0
                inside_len = 0
                try:
                    for blk in a.get("inside_blocks", []) or []:
                        for ln in blk.get("lines", []) or []:
                            for sp in ln.get("spans", []) or []:
                                inside_len += len((sp.get("text") or "").strip())
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                return sim + 0.001 * min(inside_len, 2000)

            anns = sorted(section_data.get("annotations", []) or [], key=_ann_score, reverse=True)[
                :MAX_ANNOTATION_IMAGES
            ]
            for a in anns:
                ab64 = get_annotation_image_b64(a, results_base_dir)
                if ab64:
                    image_blocks.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ab64}"}}
                    )

            # Attachments summary (counts are approximate by source lists)
            try:
                att_counts = {
                    "tables": len(section_data.get("tables", [])[:2]),
                    "figures": len(section_data.get("figures", [])[:2]),
                    "annotations": len(section_data.get("annotations", [])[:2]),
                }
                sec_diags.append(
                    make_event(
                        "07_reflow_section",
                        "info",
                        "attachments_summary",
                        "Attached images for reflow",
                        att_counts,
                    )
                )
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            user_content = [{"type": "text", "text": context_text}] + image_blocks
        elif supports_vision and not include_images:
            # Use plain string content; some providers return empty content for array parts
            user_content = context_text
        else:
            user_content = f"""{context_text}

[Note: Images omitted because the selected model does not support vision]"""

        if SCHEMA_MODE == "reflow_json":
            system_prompt = dedent(
                """
            You are a technical reflow engine. Given a PDF-extracted section JSON, compact tables, and a few images, output a single reflowed section JSON that merges contiguous content for LLM use and DB storage.

            Core requirements
            - Merge contiguous text into coherent paragraphs (fix hyphenation, broken words, OCR joins). Remove duplicated headers/footers and page artifacts.
            - Merge contiguous tables, including those that span pages, into one logical table positioned at the first fragment. Perform header normalization (remove intra-cell newlines/zero-width chars; trim/condense whitespace) and flatten multi-row headers by safe concatenation.
            - Preserve reading _order: top→bottom, left→right, across pages.
            - Prefer provided tables/pandas content; use images only for context or disambiguation.

            Data Integrity (strict)
            - Tables: DO NOT change cell content. No spelling “corrections”, translations, unit changes, rounding, normalization, inference, or reformatting. Keep numeric formats as-is.
            - Allowed in tables only: remove intra-cell newlines/excess spaces (join without changing character _order); flatten multi-row headers by concatenation delimiters.
            - Forbidden in tables: reordering rows/columns, filling blanks, deduping, computing totals.
            - Text/Headings/Lists: Fix OCR splits/hyphenation and obvious typos only outside tables. Record fixes in ocr_corrections.

            Figures
            - If the section has figures (see Figures JSON), include a figure block in blocks with: {"type":"figure", "title": string|null, "caption": string|null, "image_ref": string}.
            - Prefer using the provided ai_description as a concise caption when available; set image_ref to the figure image_path.

            Return exactly this JSON (no prose, no fences):
            {
              "reflowed_json": {
                "section_id": string,
                "title": string,
                "blocks": [
                  { "type": "heading", "level": int, "text": string, "source": { "pages": [int], "block_ids": [string] } },
                  { "type": "paragraph", "text": string, "source": { "pages": [int], "block_ids": [string] } },
                  { "type": "list", "style": "bulleted|numbered", "items": [string, ...], "source": { "pages": [int], "block_ids": [string] } },
                  { "type": "table", "title": string|null, "columns": [string,...], "rows": [[string|number|null,...],...],
                    "confidence": { "status": "high|medium|low", "density": number|null, "source": "camelot+pandas" },
                    "markdown": string|null, "markdown_provenance": "image"|null,
                    "image_refs": [string,...], "source": { "table_indices": [int], "page_indices": [int] } },
                  { "type": "figure", "title": string|null, "caption": string|null, "image_ref": string, "source": { "pages": [int], "block_ids": [string] } }
                ]
              },
              "ocr_corrections": { "erroneous": "corrected", ... },
              "improvements_made": string,
              "summary": string
            }

            Notes
            - Tables: build from provided columns+rows; ensure exact cell content; trim whitespace only. Include markdown only if pandas failed or confidence is low, in which case set markdown_provenance="image" and attach image_refs.
            - Figures: include concise caption and set image_ref to uploaded filename.
            - Source traceability: populate source.pages/block_ids when available; omit if unknown.
            """
            ).strip()
        else:
            system_prompt = dedent(
                """
            You are a technical editor. Given raw PDF-extracted section text plus structured context (tables with pandas metrics, figure descriptions, and nearby annotations), produce a clean Markdown reflow of the section.
            - Fix broken words, hyphenation across lines, and common OCR errors.
            - Keep semantics but remove duplicated headers/footers.
            - Data Integrity (strict for tables): DO NOT change cell content; if tables are present, include Markdown tables only when the table extraction is reliable (high density/consistent columns). Otherwise, summarize and reference the image. Record non-table OCR fixes in ocr_corrections.

            Output strictly JSON with keys:
              - "reflowed_text": "string (Markdown)"
              - "ocr_corrections": {"erroneous": "corrected", ...}
              - "improvements_made": "short description of the fixes"
              - "summary": "1–3 sentences summarizing the section content"
            Do not include explanations outside JSON.
            """
            ).strip()

        # Limit context size for GPT-5 stability
        if "gpt-5" in (LLM_MODEL or "").lower():
            context_text = context_text[:3000]
        # Compact cap for providers that return empty content with long payloads
        _cap = int(os.getenv("STAGE07_TEXT_MAX_CHARS", "2000"))
        _user_compact = user_content[:_cap]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _user_compact},
        ]

        # Attach images for Chat Completions (data URL parts)
        if include_images:
            max_images = int(os.getenv("STAGE07_MAX_IMAGES", "6"))
            attached = 0

            def _attach_blocks(b64: str | None, kind: str, meta: dict):
                nonlocal attached, image_blocks
                if b64 and attached < max_images:
                    image_blocks.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    )
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "info",
                                f"{kind}_image_attached",
                                "Included image",
                                meta,
                            )
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    attached += 1

            if sec_b64:
                _attach_blocks(sec_b64, "section", {"section_id": section_data.get("id")})
            for t in section_data.get("tables", []) or []:
                conf = _table_confidence(t)
                if conf < TABLE_CONF_THRESHOLD:
                    _attach_blocks(
                        get_table_image_b64(t, results_base_dir),
                        "table",
                        {"table_index": t.get("table_index"), "confidence": conf},
                    )
            if INCLUDE_FIGURE_IMAGES:
                for f in section_data.get("figures", [])[:2]:
                    _attach_blocks(
                        get_figure_image_b64(f, results_base_dir),
                        "figure",
                        {"figure_id": f.get("figure_id")},
                    )
            for a in anns:
                _attach_blocks(
                    get_annotation_image_b64(a, results_base_dir),
                    "annotation",
                    {"annotation_id": a.get("id")},
                )

        # LLM call: Chat Completions via scillm (Chutes x-api-key)
        # SciLLM-only: no litellm session envs; use our run id
        sid = get_run_id()
        # Simple prompt path (text-only). When images are NOT included, we can
        # ask only for: reflow text + merge tables. This reduces provider
        # variance and avoids empty responses.
        SIMPLE = (os.getenv("STAGE07_SIMPLE_PROMPT", "1").lower() in ("1", "true", "yes", "y")) and (not include_images)
        if SIMPLE:
            try:
                logs_dir = ensure_logs_dir(results_base_dir, "07_reflow_section")

                # Build compact user prompt with Top Summary + Layout DSL + minimal inputs
                compact_user = _build_compact_prompt_simple(section_data, text_char_cap=int(os.getenv("STAGE07_CONTEXT_CHARS", "1200")))

                # Save artifacts for this section for review (prompt + sketch)
                try:
                    artifacts_dir = Path("scripts/artifacts")
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    sid_str = str(section_data.get("id", "section"))
                    (artifacts_dir / f"07_section_{sid_str}_prompt_compact.md").write_text(
                        compact_user, encoding="utf-8"
                    )
                    try:
                        # Persist the section's layout sketch we used for gating (if present)
                        sv = section_data.get("layout_sketch") or {}
                        (artifacts_dir / f"06b_section_{sid_str}_sketch_v2.json").write_text(
                            json.dumps(sv, ensure_ascii=False, indent=2, default=str)
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass

                messages_simple = [
                    {"role": "system", "content": "You respond with JSON only — no code fences, no prose."},
                    {"role": "user", "content": compact_user},
                ]

                try:
                    import time as _t
                    _router_s = _build_text_router()
                    _t0 = _t.monotonic()
                    _r_s = await _router_s.acompletion(
                        model="chutes/text",
                        messages=messages_simple,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=min(STAGE07_MAX_TOKENS, 1024),
                        timeout=max(30, int(os.getenv("STAGE07_TIMEOUT","90"))),
                    )
                    _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
                    _usage = getattr(_r_s, "usage", None) or {}
                    _model_served = getattr(_r_s, "model", None)
                    # Persist the exact request/response payloads in logs
                    try:
                        logs_dir = ensure_logs_dir(results_base_dir, "07_reflow_section")
                        req = {
                            "model": "chutes/text",
                            "messages": messages_simple,
                            "response_format": {"type": "json_object"},
                            "temperature": 0,
                            "max_tokens": min(STAGE07_MAX_TOKENS, 1024),
                            "timeout": max(30, int(os.getenv("STAGE07_TIMEOUT","90"))),
                        }
                        (logs_dir / f"request_payload_compact_section_{sid_str}.json").write_text(
                            json.dumps(req, ensure_ascii=False, indent=2, default=str)
                        )
                        resp_content = _router_content(_r_s)
                        (logs_dir / f"response_compact_section_{sid_str}.json").write_text(
                            json.dumps(resp_content, ensure_ascii=False, indent=2, default=str)
                            if isinstance(resp_content, (dict, list))
                            else str(resp_content)
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    log_timing(
                        "07_reflow_section",
                        {
                            "attempt": "strict_compact",
                            "outcome": "ok",
                            "route_name": "chutes/text",
                            "model": _model_served,
                            "latency_ms": _elapsed_ms,
                            "timeout_s": int(os.getenv("STAGE07_TIMEOUT","90")),
                            "tokens_in": _usage_get(_usage, "prompt_tokens"),
                            "tokens_out": _usage_get(_usage, "completion_tokens"),
                        },
                    )
                    content_simple = _router_content(_r_s)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    try:
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "strict_compact",
                                "outcome": "exception",
                                "route_name": "chutes/text",
                                "served_model": None,
                                "error": str(_ex)[:200],
                                "raw_preview": None,
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    content_simple = None

                result: dict[str, Any] | None = None
                if (isinstance(content_simple, (str, dict)) and str(content_simple).strip()) or isinstance(content_simple, dict):
                    # Accept dict-or-string
                    if isinstance(content_simple, dict):
                        result = content_simple
                    else:
                        try:
                            result = parse_json_strict(str(content_simple))
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            # Retry with control-char strip + cleaning
                            cleaned_raw = re.sub(r"[\\x00-\\x1F]", " ", str(content_simple))
                            cleaned = clean_json_string(cleaned_raw, return_dict=True)
                            if cleaned:
                                result = cleaned
                            else:
                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                raise
                if result is None:
                    try:
                        direct_content = await _direct_scillm_json(
                            messages_simple,
                            response_format={"type": "json_object"},
                            max_tokens=min(STAGE07_MAX_TOKENS, 1024),
                            timeout=max(30, int(os.getenv("STAGE07_TIMEOUT", "90"))),
                        )
                        if isinstance(direct_content, dict):
                            result = direct_content
                        elif isinstance(direct_content, str) and direct_content.strip():
                            try:
                                result = parse_json_strict(direct_content)
                            except Exception as exc:
                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                raise
                                cleaned_raw = re.sub(r"[\\x00-\\x1F]", " ", direct_content)
                                cleaned = clean_json_string(cleaned_raw, return_dict=True)
                                if cleaned:
                                    result = cleaned
                                else:
                                    raise
                        try:
                            (logs_dir / f"response_compact_direct_{sid_str}.json").write_text(
                                json.dumps(direct_content, ensure_ascii=False, indent=2, default=str)
                                if isinstance(direct_content, (dict, list))
                                else str(direct_content)
                            )
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            pass
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        result = None

                # Record per-section summary
                try:
                    artifacts_dir = Path("scripts/artifacts")
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    summary_path = artifacts_dir / "07_live_response_summary.json"
                    entry = {
                        "section_id": section_data.get("id"),
                        "transport": ("sdk" if result is not None else "none"),
                        "ok": bool(result and isinstance(result, dict) and result.get("reflowed_json")),
                        "timestamp": iso_now(),
                    }
                    try:
                        prev = json.loads(summary_path.read_text()) if summary_path.exists() else []
                        if not isinstance(prev, list):
                            prev = []
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        prev = []
                    prev.append(entry)
                    summary_path.write_text(json.dumps(prev, indent=2))
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass

                if isinstance(result, dict) and result.get("reflowed_json"):
                    return {**section_data, **result, "reflow_status": "success"}
                # If compact path failed to produce JSON, fall through to existing strict/relaxed branches
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass

        # Minimal forced path for smokes: bypass complex strict/compact branches for Gemini
        _force_minimal = os.getenv("STAGE07_FORCE_MINIMAL_CALL", "").lower() in ("1", "true", "yes", "y")
        if _force_minimal:
            try:
                logs_dir = results_base_dir / "07_reflow_section" / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                minimal_guard = "Return ONLY a JSON object. No prose, no code fences. Keep it short."
                minimal_user = f"{minimal_guard}\n\n{context_text[:1200]}"
                messages_min = [
                    {"role": "system", "content": "You output ONLY compact JSON."},
                    {"role": "user", "content": minimal_user},
                ]
                params_min = {
                    "model": LLM_MODEL,
                    "messages": messages_min,
                    "timeout": llm_timeout,
                    "temperature": 0,
                    "cache": {"no-cache": True},
                    # No response_format to avoid any param translation issues
                }
                # Log minimal payload (sanitized)
                try:
                    sanitized_min = sanitize_messages_for_return(messages_min, mode="truncate", max_str_len=48)
                    (logs_dir / f"request_payload_forced_min_{section_data.get('id','section')}.json").write_text(
                        json.dumps({"model": LLM_MODEL, "messages": sanitized_min, "kwargs": {k: v for k, v in params_min.items() if k not in ("model","messages")}}, ensure_ascii=False, indent=2, default=str)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                try:
                    import time as _t
                    _router_min = _build_text_router()
                    _t0 = _t.monotonic()
                    _r_min = await _router_min.acompletion(
                        model="chutes/text",
                        messages=messages_min,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=min(STAGE07_MAX_TOKENS, 512),
                        timeout=llm_timeout,
                    )
                    _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
                    _usage = getattr(_r_min, "usage", None) or {}
                    _model_served = getattr(_r_min, "model", None)
                    log_timing(
                        "07_reflow_section",
                        {
                            "attempt": "minimal_json",
                            "outcome": "ok",
                            "route_name": "chutes/text",
                            "model": _model_served,
                            "latency_ms": _elapsed_ms,
                            "timeout_s": llm_timeout,
                            "tokens_in": _usage_get(_usage, "prompt_tokens"),
                            "tokens_out": _usage_get(_usage, "completion_tokens"),
                        },
                    )
                    content_min = _router_content(_r_min)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    try:
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "minimal_json",
                                "outcome": "exception",
                                "route_name": "chutes/text",
                                "served_model": None,
                                "error": str(_ex)[:200],
                                "raw_preview": None,
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    content_min = None
                try:
                    (logs_dir / f"response_forced_min_{section_data.get('id','section')}.json").write_text(
                        json.dumps(content_min, ensure_ascii=False, indent=2, default=str) if isinstance(content_min, (dict, list)) else str(content_min)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                if isinstance(content_min, str) and content_min.strip():
                    content = content_min
                    # Parse immediately and build output for schema mode
                    try:
                        parsed = clean_json_string(content, return_dict=True)
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        parsed = {}
                    if SCHEMA_MODE == "reflow_json":
                        # Wrap into minimal reflowed_json
                        out = {**section_data}
                        out.update(
                            {
                                "reflowed_json": {
                                    "title": section_data.get("title") or "Untitled",
                                    "blocks": [json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, (dict, list)) else (parsed if isinstance(parsed, str) else content)],
                                },
                                "ocr_corrections": parsed.get("ocr_corrections", {}),
                                "improvements_made": parsed.get("improvements_made", ""),
                                "summary": parsed.get("summary", ""),
                                "reflow_status": "success",
                            }
                        )
                        return out
                    else:
                        # Put JSON (any) into reflowed_text string
                        if isinstance(parsed, (dict, list)):
                            parsed = {"reflowed_text": json.dumps(parsed, ensure_ascii=False)}
                        elif isinstance(parsed, str):
                            parsed = {"reflowed_text": parsed}
                        else:
                            parsed = {"reflowed_text": content}
                        out = {**section_data}
                        out.update(
                            {
                                "reflowed_text": parsed.get("reflowed_text", ""),
                                "ocr_corrections": parsed.get("ocr_corrections", {}),
                                "improvements_made": parsed.get("improvements_made", ""),
                                "reflow_status": "success",
                            }
                        )
                        return out
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # Fallback: try native Google client without schema, JSON mime only
            try:
                if ("gemini" in (LLM_MODEL or "").lower()) and (not ROUTER_ONLY):
                    from google import genai as _genai
                    logs_dir = results_base_dir / "07_reflow_section" / "logs"
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    _client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
                    resp = _client.models.generate_content(
                        model=(LLM_MODEL.split("/", 1)[1] if "/" in (LLM_MODEL or "") else LLM_MODEL),
                        contents=[minimal_user],
                        config={"temperature": 0, "response_mime_type": "application/json"},
                    )
                    text_out = None
                    try:
                        cand0 = resp.candidates[0]
                        parts = getattr(getattr(cand0, "content", None), "parts", None)
                        if parts:
                            for prt in parts:
                                t = getattr(prt, "text", None)
                                if isinstance(t, str) and t.strip():
                                    text_out = t
                                    break
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        text_out = None
                    try:
                        (logs_dir / f"response_forced_min_native_{section_data.get('id','section')}.json").write_text(
                            json.dumps({"text": text_out}, ensure_ascii=False, indent=2)
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    if isinstance(text_out, str) and text_out.strip():
                        try:
                            parsed = clean_json_string(text_out, return_dict=True)
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            parsed = text_out
                        out = {**section_data}
                        if SCHEMA_MODE == "reflow_json":
                            out.update(
                                {
                                    "reflowed_json": {
                                        "title": section_data.get("title") or "Untitled",
                                        "blocks": [json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, (dict, list)) else (parsed if isinstance(parsed, str) else text_out)],
                                    },
                                    "ocr_corrections": {},
                                    "improvements_made": "",
                                    "summary": "",
                                    "reflow_status": "success",
                                }
                            )
                        else:
                            out.update(
                                {
                                    "reflowed_text": json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, (dict, list)) else (parsed if isinstance(parsed, str) else text_out),
                                    "ocr_corrections": {},
                                    "improvements_made": "",
                                    "reflow_status": "success",
                                }
                            )
                        return out
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        # Attempt 1: Chat Completions with standardized messages (system + user text + image_url data URL)
        try:
            # Build image data URL for section image if present and attach to messages
            _image_data_url = None
            try:
                # prefer section image
                if sec_b64:
                    _image_data_url = f"data:image/png;base64,{sec_b64}"
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                _image_data_url = None
            # Prompt: compact vs full. Compact can help providers that stall on overly prescriptive prompts.
            _compact = os.getenv("STAGE07_COMPACT_PROMPT", "").lower() in ("1", "true", "yes", "y")
            system_text = PROMPT_REFLOW.get("system") or STRICT_JSON_GUARD

            def _is_gemini(m: str) -> bool:
                return "gemini" in (m or "").lower()

            # Use LiteLLM-standard parts: "text" and "image_url" for all providers.
            # We still place the JSON guard at the start of user content for Gemini by
            # inlining it into the first text part (instead of using input_text/input_image).
            _converted = list(image_blocks)

            # Build messages with a system role; inline a minimal schema hint
            user_text = PROMPT_REFLOW.get("user", "Return ONLY valid JSON.\n\n{context_text}").format(
                context_text=context_text
            )
            user_parts = [{"type": "text", "text": user_text}]
            if include_images and supports_vision and _converted:
                user_parts.extend(_converted)
            messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_parts},
            ]
            # No adapter path — Router-only per policy; fallbacks handled later via curl if needed

            extras = build_chat_extras(LLM_MODEL)
            # Avoid collisions: if using response_format for Gemini, drop generation_config from extras
            try:
                if ("gemini" in (LLM_MODEL or "").lower()) and (not ROUTER_ONLY):
                    extras.pop("generation_config", None)
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # JSON schema for strict structured output
            _json_schema = {
                "type": "object",
                "properties": {
                    "reflowed_json": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "blocks": {
                                "type": "array",
                                "items": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "title": {"type": "string"},
                                                "caption": {"type": "string"},
                                                "image_ref": {"type": "string"}
                                            },
                                            "required": ["type"],
                                            "additionalProperties": True,
                                        },
                                        {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "columns": {"type": "array", "items": {"type": "string"}},
                                                "rows": {
                                                    "type": "array",
                                                    "items": {"type": "array", "items": {"type": ["string", "number", "null"]}}
                                                }
                                            },
                                            "required": ["type", "columns", "rows"],
                                            "additionalProperties": True
                                        }
                                    ]
                                },
                            },
                        },
                        "required": ["title"],
                        "additionalProperties": True,
                    },
                    "ocr_corrections": {
                        "type": "object",
                        "properties": {"_": {"type": "string"}},
                        "additionalProperties": True,
                    },
                    "improvements_made": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["reflowed_json"],
                "additionalProperties": False,
            }

            call_params = {
                "model": LLM_MODEL,
                "messages": messages,
                **extras,
                "timeout": llm_timeout,
            }
            # Reduce variability
            call_params["temperature"] = 0
            # Important: Do NOT set max_output_tokens for Gemini (can cause empty responses)
            try:
                if "gemini" not in (LLM_MODEL or "").lower():
                    call_params["max_tokens"] = STAGE07_MAX_TOKENS
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # If images are included on Attempt 1 (non-Gemini), clamp tokens to image cap after generic max is set
            try:
                if include_images and supports_vision and "gemini" not in (LLM_MODEL or "").lower():
                    _img_cap = int(os.getenv("STAGE07_IMAGE_PROMPT_MAX_TOKENS", str(MAX_TOKENS_IMAGE)))
                    prior_max = int(call_params.get("max_tokens") or STAGE07_MAX_TOKENS)
                    call_params["max_tokens"] = min(prior_max, _img_cap)
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # Disable cache for strict JSON passes to avoid stale empties
            call_params["cache"] = {"no-cache": True}
            # Enforce JSON-only responses; allow minimal mode for Gemini via env
            _minimal_json = os.getenv("STAGE07_MINIMAL_JSON", "").lower() in ("1", "true", "yes", "y")
            if "gemini" in (LLM_MODEL or "").lower():
                try:
                    extras.pop("generation_config", None)
                    call_params.pop("generation_config", None)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                if _minimal_json:
                    call_params["response_format"] = {"type": "json_object"}
                else:
                    call_params["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {"schema": _json_schema},
                    }
            else:
                call_params["response_format"] = {"type": "json_object"}
            # Add stop fences for non-Gemini providers to avoid spillover
            # Do not set stop fences; some providers return empty content when stop is present
            # Instrumentation: write request summary now that messages exist
            try:
                logs_dir = results_base_dir / "07_reflow_section" / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)

                def _image_bytes_from_part(p: dict) -> int:
                    try:
                        if not (isinstance(p, dict) and p.get("type") == "image_url"):
                            return 0
                        img = p.get("image_url") or {}
                        url = img.get("url")
                        if not (isinstance(url, str) and "," in url):
                            return 0
                        b64 = url.split(",", 1)[1]
                        return int(len(b64) * 3 / 4)
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        return 0

                # Count image parts directly from user content
                user_parts_all: list[dict] = []
                try:
                    for m in messages:
                        if isinstance(m, dict) and isinstance(m.get("content"), list):
                            user_parts_all.extend([p for p in m["content"] if isinstance(p, dict)])
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass

                req_info = {
                    "model": LLM_MODEL,
                    "context_length": len(context_text),
                    "images_count": sum(1 for p in user_parts_all if p.get("type") == "image_url"),
                    "image_bytes": [
                        _image_bytes_from_part(p) for p in user_parts_all if p.get("type") == "image_url"
                    ],
                    "session_id": sid,
                }
                (logs_dir / f"request_info_{section_data.get('id','section')}.json").write_text(
                    json.dumps(req_info, indent=2)
                )
                # Also log a sanitized snapshot of the final request payload to confirm parameter mapping
                try:
                    sanitized_messages = sanitize_messages_for_return(messages, mode="truncate", max_str_len=48)
                    payload_dump = {
                        "model": LLM_MODEL,
                        "messages": sanitized_messages,
                        "kwargs": {k: v for k, v in call_params.items() if k not in ("model", "messages")},
                    }
                    (logs_dir / f"request_payload_strict_{section_data.get('id','section')}.json").write_text(
                        json.dumps(payload_dump, ensure_ascii=False, indent=2, default=str)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass

            # Run strict call via SciLLM Router (OpenAI-compatible JSON mode)
            try:
                _router = _build_text_router()
                import time as _t
                _t0 = _t.monotonic()
                with time_block(logs_dir, "attempt_strict", section_id=str(section_data.get("id","section")), **summarize_messages(messages)):
                    _r = await _router.acompletion(
                        model="chutes/text",
                        messages=messages,
                        response_format=call_params.get("response_format", {"type": "json_object"}),
                        temperature=0,
                        max_tokens=int(call_params.get("max_tokens") or 1024),
                        timeout=llm_timeout,
                    )
                content_obj = _router_content(_r)
                try:
                    _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
                    _usage = getattr(_r, "usage", None) or {}
                    _model_served = getattr(_r, "model", None)
                    log_timing(
                        "07_reflow_section",
                        {
                            "attempt": "strict_main",
                            "outcome": "ok",
                            "route_name": "chutes/text",
                            "served_model": _model_served,
                            "latency_ms": _elapsed_ms,
                            "timeout_s": llm_timeout,
                            "tokens_in": _usage_get(_usage, "prompt_tokens"),
                            "tokens_out": _usage_get(_usage, "completion_tokens"),
                        },
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                try:
                    log_timing(
                        "07_reflow_section",
                        {
                            "attempt": "strict_main",
                            "outcome": "exception",
                            "route_name": "chutes/text",
                            "served_model": None,
                            "error": str(_ex)[:200],
                            "raw_preview": None,
                        },
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                content_obj = None
            try:
                from loguru import logger as _logger
                _ok = True if (content_obj is not None) else False
                _logger.info(f"reflow_strict: model={LLM_MODEL} ok={_ok}")
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            resp = content_obj or ""
            try:
                (logs_dir / f"response_strict_{section_data.get('id','section')}.json").write_text(
                    json.dumps(resp, default=str, indent=2)
                    if isinstance(resp, dict)
                    else str(resp)
                )
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            resp = ""
        # Normalize (accept dict or string) using shared helper
        from extractor.pipeline.utils.response_utils import normalize_json_content
        raw_text, json_obj = normalize_json_content(resp) if resp is not None else ("", None)
        content = raw_text if isinstance(raw_text, str) else ""
        if not isinstance(content, str) or not content.strip():
            # Attempt 2 (strict-compact): reduce context + simplified guard to improve provider reliability
            try:
                # Build compact instruction
                compact_guard = (
                    "Return ONLY a minified JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. "
                    "No markdown, no code fences, no trailing commas. reflowed_json.blocks must be valid and _ordered."
                )
                use_compact = os.getenv("STAGE07_USE_COMPACT", "").lower() in ("1","true","yes","y")
                compact_user = f"{compact_guard}\n\n{context_text[:1500]}"
                if use_compact:
                    # Load sketch_v2 once
                    try:
                        skv2_path = results_base_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json"
                        skv2 = json.loads(skv2_path.read_text()) if skv2_path.exists() else {"sections": {}}
                        sk_by_sec = skv2.get("sections") or {}
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        sk_by_sec = {}
                    compact_user = _build_compact_prompt(
                        results_base_dir=results_base_dir,
                        section_data=section_data,
                        tables=section_data.get("tables", []),
                        figures=section_data.get("figures", []),
                        sketch_v2_by_sec=sk_by_sec,
                    )
                    # Persist the exact prompt for this section
                    try:
                        art = Path("scripts/artifacts")
                        art.mkdir(parents=True, exist_ok=True)
                        (art / f"07_{section_data.get('id','section')}_prompt_compact.md").write_text(compact_user, encoding="utf-8")
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                # Use plain string content for text-only reliability
                # Domain-aware system prompt (concise but explicit)
                sys_msg = (
                    "You are reflowing scientific/engineering hardware documents. "
                    "Return ONLY strict JSON (no markdown/fences). Merge contiguous tables with identical schema; "
                    "preserve column order and values; fix hyphenation inside words; limit to keys requested."
                )
                # Optional: include the section image (multimodal) if requested
                user_content: Any = compact_user
                try:
                    include_image = os.getenv("STAGE07_INCLUDE_SECTION_IMAGE", "").lower() in ("1","true","yes","y")
                    if include_image:
                        # Resolve a section image; prefer 04's visual_path on the section, else any 06b visual_path
                        vrel: Optional[str] = None
                        try:
                            vrel = str(section_data.get("visual_path") or "") or None
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            vrel = None
                        if not vrel:
                            try:
                                skv2_path = results_base_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json"
                                skv2 = json.loads(skv2_path.read_text()) if skv2_path.exists() else {"sections": {}}
                                sid = str(section_data.get("id"))
                                vrel = str(((skv2.get("sections") or {}).get(sid) or {}).get("visual_path") or "") or None
                            except Exception as exc:
                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                raise
                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                raise
                                log_stage_error('07_reflow_section', exc, {'context': '07'})
                                raise
                                vrel = None
                        if vrel:
                            from extractor.pipeline.utils.model_params import image_file_to_data_url as _img_to_data
                            vpath = (results_base_dir / vrel).resolve()
                            if vpath.exists():
                                user_content = [
                                    {"type": "text", "text": compact_user},
                                    {"type": "image_url", "image_url": {"url": _img_to_data(vpath)}},
                                ]
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                messages2 = [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_content},
                ]
                call_params2 = {"model": LLM_MODEL, "messages": messages2, "timeout": llm_timeout, **extras}
                call_params2["temperature"] = 0
                # Important: Do NOT set max_output_tokens for Gemini (can cause empty responses)
                try:
                    if "gemini" not in (LLM_MODEL or "").lower():
                        call_params2["max_tokens"] = STAGE07_MAX_TOKENS
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                call_params2["cache"] = {"no-cache": True}
                if "gemini" in (LLM_MODEL or "").lower():
                    try:
                        call_params2.pop("generation_config", None)
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    if _minimal_json:
                        call_params2["response_format"] = {"type": "json_object"}
                    else:
                        call_params2["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {"schema": _json_schema},
                        }
                else:
                    call_params2["response_format"] = {"type": "json_object"}
                # Stop fence for non-Gemini providers
                # Do not set stop fences; some providers return empty content when stop is present
                # Log sanitized compact request for debugging
                try:
                    logs_dir = ensure_logs_dir(results_base_dir, "07_reflow_section")
                    sanitized_messages2 = sanitize_messages_for_return(messages2, mode="truncate", max_str_len=48)
                    payload_dump2 = {
                        "model": LLM_MODEL,
                        "messages": sanitized_messages2,
                        "kwargs": {k: v for k, v in call_params2.items() if k not in ("model", "messages")},
                    }
                    (logs_dir / f"request_payload_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(payload_dump2, ensure_ascii=False, indent=2, default=str)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                # Compact strict pass via Router (JSON mode)
                try:
                    _router2 = _build_text_router()
                    import time as _t
                    _t0 = _t.monotonic()
                    with time_block(logs_dir, "attempt_compact", section_id=str(section_data.get("id","section")), **summarize_messages(messages2)):
                        _r2 = await _router2.acompletion(
                            model="chutes/text",
                            messages=messages2,
                            response_format=call_params2.get("response_format", {"type": "json_object"}),
                            temperature=0,
                            max_tokens=int(call_params2.get("max_tokens") or 1024),
                            timeout=llm_timeout,
                        )
                    content_obj2 = _router_content(_r2)
                    try:
                        _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
                        _usage = getattr(_r2, "usage", None) or {}
                        _model_served = getattr(_r2, "model", None)
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "compact_main",
                                "outcome": "ok",
                                "route_name": "chutes/text",
                                "served_model": _model_served,
                                "latency_ms": _elapsed_ms,
                                "timeout_s": llm_timeout,
                                "tokens_in": _usage_get(_usage, "prompt_tokens"),
                                "tokens_out": _usage_get(_usage, "completion_tokens"),
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    try:
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "compact_main",
                                "outcome": "exception",
                                "route_name": "chutes/text",
                                "served_model": None,
                                "error": str(_ex)[:200],
                                "raw_preview": None,
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    content_obj2 = None
                try:
                    from loguru import logger as _logger
                    _ok2 = True if (content_obj2 is not None) else False
                    _logger.info(f"reflow_strict_compact: model={LLM_MODEL} ok={_ok2}")
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                resp2 = content_obj2 or ""
                try:
                    (logs_dir / f"response_strict_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(resp2, default=str, indent=2) if isinstance(resp2, dict) else str(resp2)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                if isinstance(resp2, dict):
                    try:
                        content = json.dumps(resp2, ensure_ascii=False)
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        content = None
                else:
                    content = resp2 if isinstance(resp2, str) else None
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                content = None
        if not isinstance(content, str) or not content.strip():
            # Attempt Gemini native strict shim using google.genai to guarantee JSON
            try:
                if "gemini" in (LLM_MODEL or "").lower():
                    from google import genai as _genai
                    from google.genai import types as _gtypes
                    logs_dir = results_base_dir / "07_reflow_section" / "logs"
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    # Build Google contents from our messages (text + data URLs)
                    g_parts: list = []
                    for m in messages:
                        try:
                            cont = m.get("content") if isinstance(m, dict) else None
                            if isinstance(cont, list):
                                for p in cont:
                                    if isinstance(p, dict) and p.get("type") == "text":
                                        txt = p.get("text")
                                        if isinstance(txt, str) and txt.strip():
                                            g_parts.append(txt)
                                    elif isinstance(p, dict) and p.get("type") == "image_url":
                                        img = p.get("image_url") or {}
                                        url = img.get("url")
                                        if isinstance(url, str) and url.startswith("data:") and ";base64," in url:
                                            header, b64 = url.split(";base64,", 1)
                                            mime = header.split(":", 1)[1] if ":" in header else "image/png"
                                            import base64 as _b64
                                            try:
                                                g_parts.append(_gtypes.Part.from_bytes(data=_b64.b64decode(b64), mime_type=mime))
                                            except Exception as exc:
                                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                                raise
                                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                                raise
                                                log_stage_error('07_reflow_section', exc, {'context': '07'})
                                                raise
                                                pass
                            elif isinstance(cont, str) and cont.strip():
                                g_parts.append(cont)
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            continue

                    # Define a minimal response schema
                    schema = _gtypes.Schema(
                        type=_gtypes.Type.OBJECT,
                        properties={
                            "reflowed_json": _gtypes.Schema(type=_gtypes.Type.OBJECT),
                            "ocr_corrections": _gtypes.Schema(type=_gtypes.Type.OBJECT),
                            "improvements_made": _gtypes.Schema(type=_gtypes.Type.STRING),
                            "summary": _gtypes.Schema(type=_gtypes.Type.STRING),
                        },
                        required=["reflowed_json", "ocr_corrections", "improvements_made"],
                        additionalProperties=False,
                    )
                    # Client and call
                    _client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"), http_options={"timeout": llm_timeout * 1000})
                    resp = _client.models.generate_content(
                        model=(LLM_MODEL.split("/", 1)[1] if "/" in (LLM_MODEL or "") else LLM_MODEL),
                        contents=g_parts or [context_text[:1500]],
                        config={
                            "temperature": 0,
                            "response_schema": schema,
                            "response_mime_type": "application/json",
                        },
                    )
                    # Extract text
                    try:
                        cand0 = resp.candidates[0]
                        parts = getattr(getattr(cand0, "content", None), "parts", None)
                        if parts:
                            for prt in parts:
                                t = getattr(prt, "text", None)
                                if isinstance(t, str) and t.strip():
                                    content = t
                                    break
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    # Log shim response
                    try:
                        (logs_dir / f"response_gemini_native_{section_data.get('id','section')}.json").write_text(
                            json.dumps({
                                "raw": getattr(resp, "to_dict", lambda: str(resp))(),
                                "text": content,
                            }, ensure_ascii=False, indent=2, default=str)
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        if not isinstance(content, str) or not content.strip():
            # Fallback to legacy shape handling
            if isinstance(resp, str):
                content = resp
            elif isinstance(resp, dict):
                try:
                    if "output" in resp:
                        out = resp.get("output") or []
                        if out and isinstance(out, list):
                            content_items = out[0].get("content") or []
                            if content_items and isinstance(content_items, list):
                                text_item = next(
                                    (
                                        c
                                        for c in content_items
                                        if c.get("type") in ("output_text", "text")
                                    ),
                                    None,
                                )
                                if text_item:
                                    content = text_item.get("text") or text_item.get("content")
                    if not content:
                        choices = resp.get("choices") or []
                        if choices:
                            msg = choices[0].get("message") or {}
                            content = msg.get("content")
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    content = None
            else:
                if include_images and not supports_vision:
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "info",
                                "vision_not_supported",
                                "Model lacks vision; images not sent",
                                {},
                            )
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                ch = getattr(resp, "choices", None)
                if ch:
                    try:
                        ch0 = ch[0]
                        msg = getattr(ch0, "message", None)
                        if msg is not None and getattr(msg, "content", None) is not None:
                            content = msg.content  # type: ignore[attr-defined]
                        else:
                            txt = getattr(ch0, "text", None)
                            if isinstance(txt, str):
                                content = txt
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        content = None

        # Accept dict content directly when response_format={"type":"json_object"}
        if isinstance(content, dict):
            try:
                result = content  # treat as already-parsed JSON
                try:
                    (logs_dir / f"response_strict_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(result, indent=2)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                # short-circuit to final assembly for this section
                parsed = result
                # jump to downstream merge logic by setting a sentinel
                content = json.dumps(result)
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                content = None

        if not isinstance(content, str) or not content.strip():
            # Attempt 2: Compact strict JSON retry (shorter guard/context, lower caps)
            try:
                try:
                    _trim2 = int(os.getenv("STAGE07_RETRY1_TRIM_CHARS", "900"))
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    _trim2 = 900
                _guard2 = (
                    "Return ONLY a compact JSON object with keys: reflowed_json, ocr_corrections, "
                    "improvements_made, summary. No markdown, no code fences, and no trailing commas."
                )
                user_text2 = f"{_guard2}\n\n{context_text[:_trim2]}"
                messages2 = [
                    {"role": "system", "content": "You output ONLY compact JSON."},
                    {"role": "user", "content": user_text2},
                ]
                _retry1_cap = int(os.getenv("STAGE07_RETRY1_MAX_TOKENS", "1024"))
                try:
                    _router3 = _build_text_router()
                    _r3 = await _router3.acompletion(
                        model="chutes/text",
                        messages=messages2,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=_retry1_cap,
                        timeout=llm_timeout,
                    )
                    content2 = _router_content(_r3)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    try:
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "retry_compact",
                                "outcome": "exception",
                                "route_name": "chutes/text",
                                "served_model": None,
                                "error": str(_ex)[:200],
                                "raw_preview": None,
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    content2 = None
                # Accept dict content directly
                if isinstance(content2, dict):
                    try:
                        content = json.dumps(content2, ensure_ascii=False)
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        content = None
                elif isinstance(content2, str) and content2.strip():
                    content = content2
                try:
                    (logs_dir / f"response_strict_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(content2, ensure_ascii=False, indent=2, default=str)
                        if isinstance(content2, dict)
                        else str(content2)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass

        if not isinstance(content, str) or not content.strip():
            # Attempt 3: Relaxed mode (no response_format). Parse free-form via clean_json_string downstream.
            try:
                # Retry 2 shaping (no local sleep/backoff; global limiter handles pacing)

                try:
                    _trim = int(os.getenv("STAGE07_RETRY2_TRIM_CHARS", "1200"))
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    _trim = 1200
                _guard3 = (
                    "Return ONLY a minified JSON object with keys: reflowed_json, ocr_corrections, "
                    "improvements_made, summary. No markdown, no code fences, no comments or explanations, "
                    "no trailing commas, no NaN/Infinity. reflowed_json.blocks must be valid and _ordered."
                )
                user_parts3 = [{"type": "text", "text": f"{_guard3}\n\n{context_text[:_trim]}"}]
                messages3 = [
                    {"role": "system", "content": "You output ONLY compact JSON."},
                    {"role": "user", "content": user_parts3},
                ]

                call_params = {"model": LLM_MODEL, "messages": messages3, "timeout": llm_timeout, **extras}
                # lower temperature and cap tokens when supported
                call_params["temperature"] = 0
                call_params["cache"] = {"no-cache": True}
                try:
                    if "gemini" not in (LLM_MODEL or "").lower():
                        call_params["stop"] = STOP_FENCES
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                try:
                    _retry2_cap = int(os.getenv("STAGE07_RETRY2_MAX_TOKENS", "1536"))
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    _retry2_cap = 1536
                try:
                    if "gemini" not in (LLM_MODEL or "").lower():
                        call_params["max_tokens"] = min(int(call_params.get("max_tokens") or STAGE07_MAX_TOKENS), _retry2_cap)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass

                # Relaxed pass with scillm (still strict JSON)
                try:
                    _router4 = _build_text_router()
                    import time as _t
                    _t0 = _t.monotonic()
                    _r4 = await _router4.acompletion(
                        model="chutes/text",
                        messages=messages3,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=int(call_params.get("max_tokens") or 1024),
                        timeout=max(30, int(os.getenv("STAGE07_TIMEOUT","90"))),
                    )
                    resp2 = _router_content(_r4)
                    try:
                        _elapsed_ms = int((_t.monotonic() - _t0) * 1000)
                        _usage = getattr(_r4, "usage", None) or {}
                        _model_served = getattr(_r4, "model", None)
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "relaxed_json",
                                "outcome": "ok",
                                "route_name": "chutes/text",
                                "served_model": _model_served,
                                "latency_ms": _elapsed_ms,
                                "timeout_s": max(30, int(os.getenv("STAGE07_TIMEOUT","90"))),
                                "tokens_in": _usage_get(_usage, "prompt_tokens"),
                                "tokens_out": _usage_get(_usage, "completion_tokens"),
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    try:
                        log_timing(
                            "07_reflow_section",
                            {
                                "attempt": "relaxed_json",
                                "outcome": "exception",
                                "route_name": "chutes/text",
                                "served_model": None,
                                "error": str(_ex)[:200],
                                "raw_preview": None,
                            },
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
                    resp2 = None
                try:
                    from loguru import logger as _logger
                    _ok3 = True if (resp2 is not None) else False
                    _logger.info(f"reflow_relaxed: model={LLM_MODEL} ok={_ok3}")
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                try:
                    (logs_dir / f"response_relaxed_{section_data.get('id','section')}.json").write_text(
                        json.dumps(resp2, default=str, indent=2)
                        if isinstance(resp2, dict)
                        else str(resp2)
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                resp2 = ""
            # Normalize relaxed response (dict-or-string) before emptiness checks
            try:
                from extractor.pipeline.utils.response_utils import normalize_json_content as _nz
                _raw2, _obj2 = _nz(resp2)
                if isinstance(_obj2, dict):
                    content = json.dumps(_obj2, ensure_ascii=False)
                else:
                    content = _raw2 if isinstance(_raw2, str) and _raw2.strip() else (resp2 if isinstance(resp2, str) else None)
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                # Fallback: previous behavior
                if isinstance(resp2, dict):
                    try:
                        content = json.dumps(resp2, ensure_ascii=False)
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        content = None
                else:
                    content = resp2 if isinstance(resp2, str) else None
        if not isinstance(content, str) or not content.strip():
            fallback_json = await _direct_compact_fallback(
                section_data,
                results_base_dir=results_base_dir,
                timeout=llm_timeout,
            )
            if isinstance(fallback_json, dict):
                try:
                    content = json.dumps(fallback_json, ensure_ascii=False)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    content = str(fallback_json)
            elif isinstance(fallback_json, str) and fallback_json.strip():
                content = fallback_json
        if not isinstance(content, str) or not content.strip():
            logger.error("Stage 07: LLM returned empty content.")
            raise RuntimeError(
                "Stage 07: LLM returned empty content. Verify API keys and Chat Completions access; inspect logs in 07_reflow_section/logs for request_info and response dumps."
            )

        # Try unified normalization first (dict or string → dict); else strict → repair
        try:
            parsed = _content_to_json_dict(content)
            result = parsed
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            # Parse JSON: strict first (no repair). Optionally relax if allowed.
            try:
                parsed = parse_json_strict(content)
                result = parsed
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                if os.getenv("STAGE07_STRICT_PARSE_ONLY", "0").lower() in ("1", "true", "yes", "y"):
                    logger.warning(f"Strict JSON parse failed (no repair allowed): {_strict_err}")
                    raise
                logger.warning(f"Strict JSON parse failed; attempting relaxed repair: {_strict_err}")
                # Prefer project cleaner to handle stray fences/trailing commas, etc.
                parsed = clean_json_string(content, return_dict=True)
            # Optional: prune unexpected top-level keys for strictness (default ON)
            try:
                if os.getenv("STAGE07_PRUNE_TOPLEVEL_KEYS", "1").lower() in ("1", "true", "yes", "y"):
                    _allowed = {"reflowed_json", "ocr_corrections", "improvements_made", "summary"}
                    parsed = restrict_top_level_keys(parsed, _allowed)
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            if isinstance(parsed, dict):
                result = parsed
            elif isinstance(parsed, list):
                # If the model returned a top-level list, try using the first object
                result = (
                    parsed[0]
                    if parsed and isinstance(parsed[0], dict)
                    else {"reflowed_text": content}
                )
            elif isinstance(parsed, str):
                tmp = json.loads(parsed)
                result = tmp if isinstance(tmp, dict) else {"reflowed_text": content}
            else:
                result = {"reflowed_text": content}
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            logger.warning("Invalid JSON from LLM; failing per policy (no fallback)")
            try:
                sec_diags.append(
                    make_event(
                        "07_reflow_section",
                        "warning",
                        "llm_invalid_json",
                        "LLM returned invalid JSON",
                        {},
                    )
                )
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            raise ValueError(
                "Stage 07: LLM returned invalid JSON. See logs in 07_reflow_section/logs and verify the model returns strict JSON (no code fences) matching schema mode expectations."
            )

        # Enforce strict top-level keys for all successful parses
        try:
            _allowed = {"reflowed_json", "ocr_corrections", "improvements_made", "summary"}
            if isinstance(result, dict):
                result = restrict_top_level_keys(result, _allowed)
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass
        # Enforce schema presence; do not accept wrappers or missing keys
        if SCHEMA_MODE == "reflow_json":
            if not (isinstance(result, dict) and result.get("reflowed_json")):
                raise ValueError(
                    "Stage 07: Expected 'reflowed_json' in model output for schema mode but it was missing. Ensure the prompt instructs returning the exact schema."
                )
            out = {**section_data}
            out.update(
                {
                    "reflowed_json": result.get("reflowed_json"),
                    "ocr_corrections": result.get("ocr_corrections", {}),
                    "improvements_made": result.get("improvements_made", ""),
                    "summary": result.get("summary", ""),
                    "reflow_status": result.get("reflow_status", "success"),
                }
            )
            # Optional figure fallback for recovery scenarios only when explicitly enabled
            try:
                figs = section_data.get("figures") or []
                rj = out.get("reflowed_json") or {}
                blocks = rj.get("blocks") or []
                has_fig_block = any(isinstance(b, dict) and b.get("type") == "figure" for b in blocks)
                if figs and not has_fig_block:
                    f0 = figs[0]
                    cap = (f0.get("ai_description") or "").strip() or None
                    imgp = f0.get("image_path") or None
                    fig_block = {
                        "type": "figure",
                        "title": None,
                        "caption": cap,
                        "image_ref": imgp,
                        "source": {
                            "pages": [f0.get("page")] if f0.get("page") is not None else [],
                            "block_ids": [],
                        },
                    }
                    if f0.get("figure_id"):
                        fig_block["figure_id"] = f0.get("figure_id")
                    blocks = [fig_block] + (blocks if isinstance(blocks, list) else [])
                    rj["blocks"] = blocks
                    out["reflowed_json"] = rj
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "warning",
                                "figure_fallback_inserted",
                                "Figure block missing from LLM response; fallback block inserted.",
                                {"figure_id": f0.get("figure_id")},
                            )
                        )
                    except Exception as exc:
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                        raise
                        log_stage_error('07_reflow_section', exc, {'context': '07'})
                        raise
                        pass
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # Normalize figure blocks emitted by the model to Stage 06 canonical structure
            try:
                figs = section_data.get("figures") or []
                if figs:
                    canon_map = {}
                    for f in figs:
                        blk = _build_figure_block_from_stage06(f)
                        if blk and f.get("figure_id"):
                            canon_map[f.get("figure_id")] = blk
                    rj = out.get("reflowed_json") or {}
                    blocks = list(rj.get("blocks") or [])
                    updated: list[Any] = []
                    changed = False
                    for blk in blocks:
                        replaced = False
                        if isinstance(blk, dict) and blk.get("type") in {"figure", "figure_reference"}:
                            fid = blk.get("figure_id")
                            canon = canon_map.get(fid)
                            if not canon and figs:
                                canon = _build_figure_block_from_stage06(figs[0])
                            if canon:
                                merged = dict(canon)
                                for key in ("title", "caption", "alt", "image_ref"):
                                    if blk.get(key):
                                        merged[key] = blk.get(key)
                                updated.append(merged)
                                replaced = True
                                changed = True
                        if not replaced:
                            updated.append(blk)
                    if changed:
                        rj["blocks"] = updated
                        out["reflowed_json"] = rj
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # Ensure at least one table block is present when tables exist
            try:
                tabs = section_data.get("tables") or []
                rj = out.get("reflowed_json") or {}
                blocks = rj.get("blocks") or []
                has_tbl_block = any(isinstance(b, dict) and b.get("type") == "table" for b in blocks)
                if tabs and not has_tbl_block:
                    t0 = tabs[0]
                    tbl_block = _build_table_block_from_stage05(t0)
                    if tbl_block:
                        blocks = [tbl_block] + (blocks if isinstance(blocks, list) else [])
                        rj["blocks"] = blocks
                        out["reflowed_json"] = rj
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
            # Replace table blocks with canonical data only when the model produced invalid structures
            try:
                canonical_tables = [
                    b for b in (_build_table_block_from_stage05(t) for t in section_data.get("tables", [])) if b
                ]
                if canonical_tables:
                    rj = out.get("reflowed_json") or {}
                    blocks = list(rj.get("blocks") or [])
                    table_indices = [
                        idx
                        for idx, blk in enumerate(blocks)
                        if isinstance(blk, dict) and blk.get("type") == "table"
                    ]
                    # remove any extra table blocks beyond the canonical set
                    for extra_idx in sorted(table_indices[len(canonical_tables):], reverse=True):
                        blocks.pop(extra_idx)

                    # ensure at least canonical count slots exist and replace with sanitized data
                    while len(table_indices) < len(canonical_tables):
                        blocks.append({"type": "table", "columns": [], "rows": []})
                        table_indices.append(len(blocks) - 1)

                    for canon, idx in zip(canonical_tables, table_indices):
                        existing = blocks[idx] if 0 <= idx < len(blocks) else {}
                        merged = canon.copy()
                        if isinstance(existing, dict) and existing.get("title"):
                            merged["title"] = existing.get("title")
                        differences: list[dict[str, Any]] = []
                        try:
                            existing_rows = existing.get("rows") if isinstance(existing, dict) else None
                            if isinstance(existing_rows, list):
                                canon_cols = merged.get("columns") or []
                                for r_idx, (canon_row, existing_row) in enumerate(zip(merged.get("rows", []), existing_rows)):
                                    for c_idx, (canon_cell, existing_cell) in enumerate(zip(canon_row, existing_row)):
                                        if _normalize_table_text(existing_cell) != canon_cell:
                                            differences.append(
                                                {
                                                    "row": r_idx,
                                                    "column": canon_cols[c_idx] if c_idx < len(canon_cols) else c_idx,
                                                    "original": existing_cell,
                                                    "sanitized": canon_cell,
                                                }
                                            )
                        except Exception as exc:
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                            raise
                            log_stage_error('07_reflow_section', exc, {'context': '07'})
                            raise
                            pass
                        blocks[idx] = merged
                        if differences:
                            try:
                                sec_diags.append(
                                    make_event(
                                        "07_reflow_section",
                                        "info",
                                        "table_cells_sanitized",
                                        "Sanitized table cells to match canonical Stage 05 data.",
                                        {"differences": differences},
                                    )
                                )
                            except Exception as exc:
                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                raise
                                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                                raise
                                log_stage_error('07_reflow_section', exc, {'context': '07'})
                                raise
                                pass
                    rj["blocks"] = blocks
                    out["reflowed_json"] = rj
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        else:
            if not (isinstance(result, dict) and result.get("reflowed_text")):
                raise ValueError(
                    "Stage 07: Expected 'reflowed_text' in model output but it was missing. Ensure the prompt instructs returning the exact keys."
                )
            out = {**section_data}
            out.update(
                {
                    "reflowed_text": result.get("reflowed_text"),
                    "ocr_corrections": result.get("ocr_corrections", {}),
                    "improvements_made": result.get("improvements_made", ""),
                    "reflow_status": "success",
                }
            )
        if STAGE07_DEBUG:
            out["quick_summary"] = result.get(
                "summary",
                (section_data.get("merged_text") or section_data.get("raw_text", ""))[:280],
            )
        try:
            md = out.setdefault("metadata", {})
            md.setdefault("diagnostics", []).extend(sec_diags)
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass
        return out
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        # Always fail (no fallback)
        try:
            info = classify_llm_error(e)
            sec_diags.append(
                make_event(
                    "07_reflow_section",
                    "error",
                    info.get("code", "llm_error"),
                    info.get("message", str(e)),
                    {},
                )
            )
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass
        if allow_fallback:
            # Build a minimal fallback payload so downstream stages can proceed
            try:
                fallback_text = (
                    section_data.get("merged_text")
                    or section_data.get("source_text")
                    or section_data.get("raw_text")
                    or ""
                )
                out = {**section_data}
                if SCHEMA_MODE == "reflow_json":
                    out.update(
                        {
                            "reflowed_json": {
                                "section_id": section_data.get("id"),
                                "title": section_data.get("title"),
                                "blocks": [
                                    {
                                        "type": "paragraph",
                                        "text": fallback_text,
                                        "source": {"pages": [], "block_ids": []},
                                    }
                                ],
                            },
                            "ocr_corrections": {},
                            "improvements_made": "fallback (no LLM)",
                            "summary": "",
                            "reflow_status": "fallback",
                        }
                    )
                else:
                    out.update(
                        {
                            "reflowed_text": fallback_text,
                            "ocr_corrections": {},
                            "improvements_made": "fallback (no LLM)",
                            "reflow_status": "fallback",
                        }
                    )
                try:
                    md = out.setdefault("metadata", {})
                    md.setdefault("diagnostics", []).extend(sec_diags)
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                try:
                    log_metric(
                        "07_reflow_section",
                        {
                            "request_id": section_data.get("id"),
                            "model": LLM_MODEL,
                            "success": False,
                            "fallback_used": True,
                            "metadata": {
                                "doc_id": section_data.get("id"),
                                "section_title": section_data.get("title"),
                            },
                        },
                    )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                logger.warning("Stage 07: Falling back to merged text (no LLM)")
                return out
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        logger.error(f"Stage 07: LLM call failed: {e}")
        raise RuntimeError(
            "Stage 07 failed: LLM call did not return usable JSON. Check 07_reflow_section/logs, verify API keys, and confirm the configured Chat model is reachable."
        )


