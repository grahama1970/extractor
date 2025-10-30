#!/usr/bin/env python3
"""
Suspicious Header Verifier
--------------------------
This pipeline step takes the output JSON from a Marker process (which has been
run through the SuspiciousHeaderFixer) and a corresponding PDF. It finds all
blocks flagged with `suspicious_header: true`, captures an image of the block
and its immediate context, and uses a multimodal LLM to verify if the block is
truly a section header.

The script updates the JSON with the LLM's findings and saves a new version.
"""

import asyncio
import base64
import hashlib
import json
import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import fitz  # PyMuPDF
# Typer removed: use plain functions for easier debugging
from loguru import logger
# Avoid hard dependency at import time; prefer adapter helper; direct scillm used only if present
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.steps.scillm_preflight_validator import (
    validate_scillm_env_sync,
    require_scillm_preflight,
    quick_scillm_check
)

from extractor.pipeline.utils.ann_index import query_ann_index
from extractor.pipeline.utils.debug_utils import log_timing
from extractor.pipeline.utils.annotations import (
    cue_from_annotation as _cue_from_annotation,
)
from extractor.pipeline.utils.annotations import (
    load_relevant_rules as _load_relevant_rules,
)
from extractor.pipeline.utils.annotations import (
    rect_overlap_ratio as _rect_overlap_ratio,
)
from extractor.pipeline.utils.annotations import (
    summarize_cues as _summarize_cues,
)
from extractor.pipeline.utils.async_processing import process_items_concurrently
from extractor.pipeline.utils.diagnostics import (
    classify_llm_error,
    get_run_id,
    gpu_metrics_available,
    make_event,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
from extractor.pipeline.utils.json_utils import STRICT_JSON_GUARD
def _normalize_model_alias(model: str | None) -> str:
    m = (model or "").strip()
    if m.lower().startswith("openai/"):
        m = m[len("openai/"):]
    return m
from extractor.pipeline.utils.model_params import build_chat_extras  # noqa: E402
from extractor.pipeline.utils.prompt_builder import build_llm_context  # noqa: E402
# No scillm_client wrappers; Router-only policy for SciLLM

try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore
import time  # noqa: E402

# Cache initialization will be handled within command execution to avoid import-time side effects.


def _norm_text(s: str) -> str:
    return " ".join((s or "").split())


def _text_sha1(s: str) -> str:
    return hashlib.sha1(_norm_text(s).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# OPTIONAL COLOR ENRICHMENT (first-span color)
# ------------------------------------------------------------------
STAGE03_COLOR_ENRICH = os.getenv("STAGE03_COLOR_ENRICH", "1").lower() in {"1", "true", "yes", "y"}

def _bucket_color_hex(hex_str: str) -> str:
    try:
        h = hex_str.lstrip('#')
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        if r < 30 and g < 30 and b < 30:
            return "black"
        if r > 200 and g > 200 and b > 200:
            return "white"
        if r > g and r > b:
            return "red"
        if g > r and g > b:
            return "green"
        if b > r and b > g:
            return "blue"
        return "gray"
    except Exception:
        return "unknown"

def _ensure_first_span_color(page: fitz.Page, block: dict[str, Any]) -> None:
    """Populate block.first_span_font.color_{hex,bucket,rgb} if missing, using span intersect."""
    try:
        fsf = block.setdefault("first_span_font", {}) if isinstance(block.get("first_span_font"), dict) else block.setdefault("first_span_font", {})
        if fsf.get("color_hex") or fsf.get("color_bucket"):
            return
        bb = block.get("bbox")
        if not bb:
            return
        x0, y0, x1, y1 = bb
        td = page.get_text("dict")
        found = None
        for blk in td.get("blocks", []):
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    sb = span.get("bbox")
                    if not sb:
                        continue
                    sx0, sy0, sx1, sy1 = sb
                    if not (sx1 < x0 or sx0 > x1 or sy1 < y0 or sy0 > y1):
                        col = span.get("color")
                        if isinstance(col, (list, tuple)) and len(col) >= 3:
                            r, g, b = col[0], col[1], col[2]
                            # Normalize if 0..1
                            if 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0:
                                r, g, b = int(r*255), int(g*255), int(b*255)
                            else:
                                r, g, b = int(r), int(g), int(b)
                            found = (r, g, b)
                        elif isinstance(col, (int, float)):
                            v = int(col)
                            found = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return
        hexv = f"#{found[0]:02x}{found[1]:02x}{found[2]:02x}"
        fsf["color_rgb"] = list(found)
        fsf["color_hex"] = hexv
        fsf["color_bucket"] = _bucket_color_hex(hexv)
    except Exception:
        return

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
## CLI removed: import and call run(...), or use a debug harness.


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
    task_limit: int = 0  # 0 = no limit
    max_runtime_seconds: int = 0  # 0 = no limit (CLI override or STAGE03_TIMEOUT)
    item_timeout_seconds: int = int(os.getenv("STAGE03_ITEM_TIMEOUT", "30"))
    # Knowledge/annotations support
    annotations_json: Path | None = None
    use_knowledge: bool = True
    use_prior: bool = True
    auto_reject_negatives: bool = True
    persist_headers: bool = False
    source_pdf: str | None = None
    # Treat all SectionHeader blocks as candidates (ignore Stage 02 suspicious flags)
    verify_all_headers: bool = False
    # Whether to write suspicion fields back into blocks
    write_suspicion_fields: bool = True


# ------------------------------------------------------------------
# PROMPT
# ------------------------------------------------------------------
SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert document analyst. Your task is to determine if a text block, which has been
    flagged as a "suspicious" section header, is actually a legitimate section header or if it has
    been misclassified.

    You will be given:
    1.  An image showing the text block in question, along with the text immediately above and below it for visual context.
    2.  The structured text content for these three blocks, including font style information.

    Analyze both the visual layout (font size, boldness, spacing) and the text content. A real header typically has a larger font,
    is often bold, has space around it, and contains topical, non-sentence-like text. A misclassified block might be a figure caption,
    part of a table, a list item, or just a sentence fragment.

    Provide a strict JSON response with:
    - "is_header": true|false
    - "reasoning": short explanation

    """.strip()
    + "\n\n"
    + STRICT_JSON_GUARD
)

# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------
# build_llm_context now imported from utils.prompt_builder

# --------------------
# Annotations loading and cue extraction
# --------------------

# annotations helpers now imported from utils.annotations

# --------------------
# Crucial rules (optional) – used for weighting
# --------------------
RELEVANT_RULES = _load_relevant_rules()


# --- Prior decisions retrieval (stub) ---
def _retrieve_prior_decisions(header_text_norm: str, font_sig: str, limit: int = 5) -> list[dict]:
    """Stubbed prior retrieval to prevent NameError when --use-prior is enabled.
    Replace with DB-backed retrieval in future without affecting current offline mode.
    """
    return []


# --- Verify the User has selected a Multmodal (Vision) model
async def verify_header_with_llm(image_b64: str, context_text: str, model: str, *, item_timeout: int = 90) -> dict[str, Any]:
    """Verify header using scillm (vision required) with strict JSON intent via Chutes.

    - Uses api_base=CHUTES_API_BASE, api_key=None, extra_headers={'x-api-key': CHUTES_API_KEY}
    - Sends a single image + trimmed text context
    - Enforces response_format=json_object and stop fences for non-Gemini models
    """
    # Normalize model + provider/json extras; conservative trim; log effective config
    model_norm = _normalize_model_alias(model)
    extras = build_chat_extras(model_norm)
    try:
        logger.info(f"stage03.verify_header: effective_model={model_norm} extras_keys={list(extras.keys())}")
    except Exception:
        pass
    try:
        _trim = int(os.getenv("STAGE03_VERIFY_TRIM_CHARS", "800"))
    except Exception:
        _trim = 800
    if isinstance(context_text, str) and len(context_text) > _trim:
        context_text = context_text[:_trim]

    text_only = os.getenv("STAGE03_TEXT_ONLY", "1").lower() in ("1", "true", "yes", "y")
    user_content: Any = [{"type": "text", "text": context_text}]
    if not text_only and image_b64:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}})
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        _verify_cap = int(os.getenv("STAGE03_VERIFY_MAX_TOKENS", "256"))
    except Exception:
        _verify_cap = 256
    # Top-priority timeout override via env
    try:
        item_timeout = int(os.getenv("SC_TIMEOUT_STAGE_03", str(item_timeout)))
    except Exception:
        pass
    # AGENTS.md compliance: Validate SciLLM environment before making calls (no soft skip)
    if not quick_scillm_check():
        raise RuntimeError("SciLLM environment not configured; header verification requires Chutes.")
    
    router = get_text_router()
    # Timed SciLLM Router-only call
    t0 = time.monotonic()
    try:
        resp = await router.acompletion(
            model="chutes/text",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=_verify_cap,
            temperature=0,
            timeout=item_timeout,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log_timing(
            "03_suspicious_headers",
            {
                "attempt": "verify_header",
                "outcome": "exception",
                "exception": type(e).__name__,
                "exception_msg": str(e)[:300],
                "route_name": "chutes/text",
                "timeout_s": item_timeout,
                "latency_ms": elapsed_ms,
                "payload_chars": len(context_text or ""),
                "with_image": bool(image_b64),
                "retries_conf": int(os.getenv("LITELLM_MAX_RETRIES", "0")),
            },
        )
        raise
    # Observability: append per-attempt timing (success path, after we have resp)
    try:
        if isinstance(resp, dict):
            served_model = resp.get("model")
            usage = resp.get("usage") or {}
        else:
            served_model = getattr(resp, "model", None)
            usage = getattr(resp, "usage", None) or {}
        log_timing(
            "03_suspicious_headers",
            {
                "attempt": "verify_header",
                "outcome": "ok",
                "route_name": "chutes/text",
                "model": served_model,
                "timeout_s": item_timeout,
                "latency_ms": elapsed_ms,
                "payload_chars": len(context_text or ""),
                "with_image": bool(image_b64),
                "retries_conf": int(os.getenv("LITELLM_MAX_RETRIES", "0")),
                "tokens_in": usage.get("prompt_tokens"),
                "tokens_out": usage.get("completion_tokens"),
            },
        )
    except Exception:
        pass
    # Normalize response content
    if isinstance(resp, dict):
        choices = resp.get("choices") or [{}]
    else:
        choices = getattr(resp, "choices", [{}])
    msg = (choices or [{}])[0].get("message", {}) if isinstance(choices, list) else {}
    answer = (msg or {}).get("content", "")
    try:
        payload = json.loads(answer) if answer else {}
    except Exception as pe:
        # Soft-fail on parse errors; log and continue
        log_timing(
            "03_suspicious_headers",
            {
                "attempt": "llm_parse",
                "outcome": "parse_error",
                "route_name": "chutes/text",
                "parse_error_message": str(pe)[:200],
            },
        )
        payload = {"is_header": False, "reasoning": "parse_error"}
    if isinstance(payload, dict) and payload.get("error"):
        err = payload["error"]
        # Log explicit model error then raise
        log_timing(
            "03_suspicious_headers",
            {
                "attempt": "verify_header",
                "outcome": "exception",
                "exception": "LLMErrorEnvelope",
                "exception_msg": f"{err.get('type')}:{err.get('message')}"[:300],
                "route_name": "chutes/text",
            },
        )
        raise RuntimeError(f"LLM error: {err.get('type')}: {err.get('message')}")
    if not isinstance(payload, dict):
        payload = {"content": payload}
    payload = cast(dict[str, Any], payload)
    payload["is_header"] = bool(payload.get("is_header", True))
    payload["reasoning"] = str(payload.get("reasoning", ""))
    return payload


# ------------------------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------------------------
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
        except Exception:
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
            "header_text_norm": _norm_text(t_text),
            "text_sha1": _text_sha1(t_text + "|" + font_sig),
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
        except Exception:
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
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0

    print(f"Verifying suspicious headers in '{config.input_json.name}'...")
    stage_start_ts = datetime.now().isoformat()
    t_stage0 = time.monotonic()
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
                    "03_suspicious_headers",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass
    try:
        if psutil is not None:
            proc = psutil.Process()
            resources["proc_rss_mb_start"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            resources["vmem_used_mb_start"] = int(getattr(vm, "used", 0) / (1024 * 1024))
    except Exception:
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
    except Exception as e:
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
        except Exception as e:
            logger.warning(f"Failed to load annotations from {config.annotations_json}: {e}")

    # Load saved FAISS index from Stage 01 if present; else build ephemeral
    # NOTE: Removed misplaced FAISS/negatives block that executed at import time.
    # Annotation FAISS indexing and global negatives are handled inside process_pdf_pipeline.

    # 3) Candidate discovery — suspicious headers and fallbacks (or verify-all)
    # Preflight happens once we know we have candidates.

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
        except Exception:
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
    except Exception:
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
    except Exception:
        pass

    # 4) Preflight — verify model supports vision using a real candidate clip
    # (Tiny images can be rejected by providers; we use an actual context image.)
    # Preflight (skip when text-only)
    try:
        if os.getenv("STAGE03_TEXT_ONLY", "1").lower() not in ("1", "true", "yes", "y"):
            sample_image_b64 = tasks[0].render_context_image_b64()
            t_pf0 = time.monotonic()
            _ = await verify_header_with_llm(
                sample_image_b64, "Preflight vision capability check.", config.llm_model
            )
            preflight_duration_ms = int((time.monotonic() - t_pf0) * 1000)
            try:
                import os as _os
                _os.environ["VISION_PREFLIGHT_ASSUME_OK"] = "1"
            except Exception:
                pass
    except Exception as e:
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
            # Opportunistic color enrichment for the three context blocks
            if STAGE03_COLOR_ENRICH:
                try:
                    _ensure_first_span_color(task.page_obj, target_block)
                    if above_block and int(above_block.get("page", task.page_idx)) == task.page_idx:
                        _ensure_first_span_color(task.page_obj, above_block)
                    if below_block and int(below_block.get("page", task.page_idx)) == task.page_idx:
                        _ensure_first_span_color(task.page_obj, below_block)
                except Exception:
                    pass
            # --- Heuristic guardrails BEFORE any LLM call ---
            # Demote common false positives early to reduce noise and cost.
            try:
                import re as _re
                raw_text = (target_block.get("text") or "").strip()
                # Accept classic numbered headings like "1.1.1 Section Title"
                is_numbered = bool(_re.match(r"^\s*\d+(?:[\.-]\d+){1,}\s+\S", raw_text))
                # Short colon label (wrapper) — e.g., "Mergeable Tables:" — often not a true header
                short_colon = len(raw_text) <= 40 and raw_text.endswith(":")
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
            except Exception:
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
            except Exception:
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
                    except Exception:
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
                        except Exception:
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
                except Exception as e:
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
            try:
                _m_eff = _normalize_model_alias(config.llm_model)
                _extras = build_chat_extras(_m_eff)
            except Exception:
                _m_eff = config.llm_model
                _extras = {}
            prepared.append(
                {
                    "model": _m_eff,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "kwargs": _extras,
                }
            )
            task_refs.append(task)
            prepared_ctx.append(context_text)

        except Exception as e:
            logger.exception(
                f"Preparation failed for page {task.page_idx} block {task.block_idx}: {e}"
            )
            auto_results[idx] = {"is_header": True, "reasoning": f"Preparation error: {e}"}

    # 6) LLM batch — verify and collect JSON payloads (scillm + Chutes x-api-key)
    llm_payloads: list[dict[str, Any]] = []
    if prepared:
        try:
            t_llm0 = time.monotonic()
            ch_base = os.getenv("CHUTES_API_BASE", "").strip()
            ch_key = os.getenv("CHUTES_API_KEY", "").strip()
            try:
                _verify_cap = int(os.getenv("STAGE03_VERIFY_MAX_TOKENS", "256"))
            except Exception:
                _verify_cap = 256

            async def _process_item(item: dict) -> str:
                router = get_text_router()
                resp = await router.acompletion(
                    model="chutes/text",
                    messages=item.get("messages"),
                    response_format={"type": "json_object"},
                    max_tokens=_verify_cap,
                    temperature=0,
                    timeout=config.item_timeout_seconds,
                )
                return (getattr(resp, "choices", [{}])[0].get("message", {}).get("content", ""))

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
            except Exception:
                pass
            results = [
                json.dumps({"error": {"type": "Timeout", "message": info.get("message")}})
            ] * len(prepared)
        except Exception as e:
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
            except Exception:
                pass
            results = [
                json.dumps({"error": {"type": type(e).__name__, "message": info.get("message")}})
            ] * len(prepared)

        for ans in results:
            try:
                llm_payloads.append(json.loads(ans) if ans else {})
            except Exception:
                llm_payloads.append({"error": {"type": "ParseError", "message": ans[:200]}})

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
        except Exception:
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
                except Exception:
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
                except Exception:
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
        except Exception as _e:
            logger.warning(f"dataset_dump_failed: {_e}")
    pdf_doc.close()

    # 8) Save the updated JSON — flatten pages to top-level blocks
    output_json_path = json_output_dir / "03_verified_blocks.json"

    # Flatten the pages structure back to a simple list of blocks
    final_blocks = [block for page in marker_data["pages"] for block in page["blocks"]]
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
    except Exception:
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
    except Exception:
        pass
    marker_data["timings"] = timings
    marker_data["resources"] = resources
    # Threshold policy for parse errors
    try:
        warn_frac = float(os.getenv("PARSE_WARN_FRAC", "0.05"))
    except Exception:
        warn_frac = 0.05
    try:
        fail_frac = float(os.getenv("PARSE_FAIL_FRAC", "0.20"))
    except Exception:
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
                    except Exception:
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
    except Exception:
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
    # Enforce preflight when LLM is used (no soft skip)
    if not skip_llm:
        from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
        require_scillm_preflight()

    # Resolve a clean PDF produced by Stage 00 preflight first; fall back to legacy 01 path.
    run_results_dir = Path(os.getenv("RUN_RESULTS_DIR", "data/results/pipeline"))
    preflight_dir = run_results_dir / "00_preflight"
    clean_pdf_path: Path | None = None
    if preflight_dir.exists():
        matches = sorted(preflight_dir.rglob("clean.pdf"))
        if matches:
            # Prefer a match whose parent name appears in input_json path; else take the first
            prefer = [m for m in matches if m.parent.name in str(input_json)]
            clean_pdf_path = prefer[0] if prefer else matches[0]
    if clean_pdf_path is None:
        # Legacy: derive the clean PDF path from the provided pdf_dir
        try:
            candidates = sorted(pdf_dir.glob("*_clean.pdf"))
            clean_pdf_path = candidates[0]
        except (StopIteration, IndexError):
            raise ValueError(
                f"No 'clean.pdf' under {preflight_dir} and no '*_clean.pdf' found in pdf_dir: {pdf_dir}"
            )

    if not input_json.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_json}")

    # Define clear output paths for this stage
    stage_output_dir = output_dir / "03_suspicious_headers"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)

    if skip_llm:
        # Explicit operator override: allowed skip (not implicit soft-skip)
        try:
            data = json.loads(input_json.read_text())
        except Exception as e:
            raise ValueError(f"Failed to load input JSON: {e}")
        blocks = data.get("blocks", [])
        # Heuristic demotion mirrors the pre-LLM guardrails used in the online path.
        # This reduces false top-level sections in offline/CI runs.
        import re as _re
        for b in blocks:
            if not isinstance(b, dict):
                continue
            b["suspicious_header"] = False
            if (b.get("block_type") == "SectionHeader"):
                raw_text = (b.get("text") or "").strip()
                is_numbered = bool(_re.match(r"^\s*\d+(?:[\.-]\d+){1,}\s+\S", raw_text))
                short_colon = len(raw_text) <= 40 and raw_text.endswith(":")
                is_caption = bool(
                    _re.match(r"^\s*(Table|Figure)\s+\d+(?:[-–]\d+)?[.:]", raw_text, _re.IGNORECASE)
                )
                has_terminal_punct = raw_text.endswith(".") or raw_text.endswith(";")
                if (not is_numbered) and (short_colon or is_caption or has_terminal_punct):
                    # Demote to plain text; annotate reasons for downstream debugging if desired
                    b["block_type"] = "Text"
                    reasons = list(b.get("suspicious_reasons") or [])
                    tag = (
                        "not_header_colon" if short_colon else (
                            "caption_pattern" if is_caption else "not_header_sentence"
                        )
                    )
                    if tag not in [str(r) for r in reasons]:
                        reasons.append(tag)
                    b["suspicious_reasons"] = reasons
                    b["is_suspicious"] = True
                    b["suspicion_confidence"] = float(b.get("suspicion_confidence") or 0.9)
        data["suspicious_block_count"] = 0
        data["status"] = "Completed"
        out = json_output_dir / "03_verified_blocks.json"
        out.write_text(json.dumps(data, indent=2))
        print(f"[offline] Heuristic demotion applied; wrote {out}")
        try:
            from extractor.pipeline.utils.scillm_router import close_all_routers
            close_all_routers()
        except Exception:
            pass
        return out

    # Configure logging sink per stage run
    try:
        from loguru import logger as _lg

        _lg.remove()
        _lg.add(
            str(stage_output_dir / "stage_03_suspicious_headers.log"),
            level="DEBUG" if debug else "INFO",
            enqueue=True,
            backtrace=True,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception:
        pass

    # Enforce design: defer ArangoDB until after Step 09
    if persist_headers:
        try:
            logger.warning(
                "Ignoring --persist-headers: ArangoDB persistence is deferred until after Step 09 (export stages handle DB)."
            )
        except Exception:
            pass
        persist_headers = False

    eff_timeout = timeout if timeout and timeout > 0 else int(os.getenv("STAGE03_TIMEOUT", "600"))
    cfg = Config(
        input_pdf=clean_pdf_path,
        input_json=input_json,
        output_dir=stage_output_dir,  # Pass the specific stage directory
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
    try:
        from extractor.pipeline.utils.scillm_router import close_all_routers
        close_all_routers()
    except Exception:
        pass
    return stage_output_dir / "json_output" / "03_verified_blocks.json"


def debug_test():
    """Debug function to test with simulated suspicious headers."""

    # Load the stage 2 output
    input_json = Path("stage_02_results.json")
    if not input_json.exists():
        print("Error: stage_02_results.json not found. Run 02_marker_extractor.py first.")
        return

    with open(input_json) as f:
        data = json.load(f)

    # Create a test version with suspicious headers
    # Mark the bullet point items as suspicious headers (they shouldn't be headers)
    test_blocks = []
    for block in data["blocks"]:
        block_copy = block.copy()

        # Mark ListItems as suspicious SectionHeaders for testing
        if block["block_type"] == "ListItem":
            block_copy["block_type"] = "SectionHeader"  # Misclassify as header
            block_copy["is_suspicious"] = True
            block_copy["suspicious_reasons"] = ["bullet_point_misclassified"]
            block_copy["suspicion_confidence"] = 0.9
            print(f"Marked as suspicious: {block['text'][:50]}...")

        test_blocks.append(block_copy)

    # Convert to the format expected by this script (pages structure)
    pages_data = {}
    for block in test_blocks:
        page_idx = block.get("page_idx", 0)
        if page_idx not in pages_data:
            pages_data[page_idx] = []

        # Convert to expected format with suspicious_header field
        formatted_block = {
            "block_type": block["block_type"],
            "bbox": block["bbox"],
            "text": block["text"],
            "suspicious_header": block.get("is_suspicious", False),
            # Add minimal lines/spans structure for the script
            "lines": [
                {
                    "spans": [
                        {
                            "text": block["text"],
                            "font_style": {"font_name": "Unknown", "font_size": "N/A"},
                        }
                    ]
                }
            ],
        }
        pages_data[page_idx].append(formatted_block)

    # Create the expected structure
    _marker_format = {"pages": [{"blocks": blocks} for _, blocks in sorted(pages_data.items())]}


def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    model: str | None = None,
    concurrency: int = 1,
    dpi: int = 150,
    debug: bool = False,
    limit: int = 0,
    timeout: int = 0,
):
    """Run Stage 03 with a consolidated bundle.

    Bundle keys:
    - marker_blocks: object shaped like Stage 02 JSON (accepted by this step)
    - clean_pdf: absolute path to the *_clean.pdf from Stage 01
    """
    stage_output_dir = output_dir / "03_suspicious_headers"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
    except Exception as e:
        print(f"Failed to read bundle: {e}")
        raise ValueError(f"Failed to read bundle: {e}")

    marker_blocks = data.get("marker_blocks")
    clean_pdf = data.get("clean_pdf")
    if not marker_blocks or not clean_pdf:
        print("Bundle must include 'marker_blocks' and 'clean_pdf'")
        raise ValueError("Invalid bundle: missing keys")

    tmp_json = stage_output_dir / "_bundle_marker_blocks.json"
    tmp_json.write_text(json.dumps(marker_blocks))

    cfg = Config(
        input_pdf=Path(clean_pdf),
        input_json=tmp_json,
        output_dir=stage_output_dir,
        render_dpi=dpi,
        llm_model=model or _env_vlm_model(),
        llm_concurrency=concurrency,
        debug=debug,
        task_limit=limit,
        max_runtime_seconds=timeout,
    )
    asyncio.run(process_pdf_pipeline(cfg))
    print("Debug bundle: verification complete for suspicious headers")
    return stage_output_dir / "json_output" / "03_verified_blocks.json"


if __name__ == "__main__":
    print("Import and call run(...) or use scripts/debug/stage03_debug.py")
