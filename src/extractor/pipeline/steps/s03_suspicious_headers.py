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

Operator notes
- Misclassification in Stage 02 is expected; this step is the main filter.
- Do not skip this step in “live” runs; for deterministic/offline use `skip_llm` which
  applies only the heuristic demotions.

Heuristic → Code map (keep in sync)
- Bullet prefix (• ● ▪ ‣ ⁃ – — - * + ·): auto-reject if unnumbered  (prep loop & offline branch via has_bullet_prefix)
- Short colon label (<=40 chars, ends “:”): auto-reject if unnumbered (prep loop)
- Caption patterns “Table|Figure N[.N][.:]”: auto-reject if unnumbered (prep loop)
- Sentence-like endings (“.” or “;”): auto-reject if unnumbered (prep loop)
- “(continued)” / “- continued”: policy demotion post-flatten
- Auto-accept strict numbered header with parsed number/title spans (prep loop via pdf_analyze_numbering)
"""

import asyncio
import base64
import json
import os
import warnings
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import fitz  # PyMuPDF
# Typer removed: use plain functions for easier debugging
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.headers.llm import verify_header_with_llm as _verify_header_with_llm
from extractor.pipeline.utils.headers import (
    normalize_model_alias as _normalize_model_alias,
    retrieve_prior_decisions as _retrieve_prior_decisions,
)
from extractor.pipeline.utils.headers.runner import process_pdf_pipeline, Config
from extractor.pipeline.utils.suspicious_headers_utils import (
    norm_text,
    text_sha1,
    has_bullet_prefix,
    ensure_first_span_color,
)
# Avoid hard dependency at import time; prefer adapter helper; direct scillm used only if present
from extractor.pipeline.utils.scillm_router import get_text_router, get_vlm_router
from extractor.pipeline.steps.scillm_preflight_validator import quick_scillm_check

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
from extractor.pipeline.utils.prompt_loader import load_prompt
from extractor.pipeline.utils.step_sanity import run_step_sanity

def _env_vlm_model() -> str:
    return os.getenv("CHUTES_VLM_MODEL", "")

from extractor.pipeline.utils.json_utils import STRICT_JSON_GUARD
def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# Cache initialization will be handled within command execution to avoid import-time side effects.


STAGE03_COLOR_ENRICH = os.getenv("STAGE03_COLOR_ENRICH", "1").lower() in {"1", "true", "yes", "y"}

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
## CLI removed: import and call run(...), or use a debug harness.



# ------------------------------------------------------------------
# PROMPT (loaded from centralized library)
# ------------------------------------------------------------------
PROMPT = load_prompt("03_suspicious_headers")

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
    # SciLLM preflight is enforced centrally in run_pipeline for online runs.
    # This step assumes any required preflight has already succeeded and does
    # not perform its own hard dependency check to keep offline/debug flows
    # (e.g. summary-only + skip-fig-descriptions) working.

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
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
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
                raw_text = (b.get("text") or "")
                is_numbered = bool(_re.match(r"^\s*\d+(?:[\.-]\d+){1,}\s+\S", raw_text))
                short_colon = len(raw_text) <= 40 and raw_text.endswith(":")
                bullet_prefix = has_bullet_prefix(raw_text)
                is_caption = bool(
                    _re.match(r"^\s*(Table|Figure)\s+\d+(?:[-–]\d+)?[.:]", raw_text, _re.IGNORECASE)
                )
                has_terminal_punct = raw_text.endswith(".") or raw_text.endswith(";")
                if (not is_numbered) and (short_colon or is_caption or has_terminal_punct or bullet_prefix):
                    # Demote to plain text; annotate reasons for downstream debugging if desired
                    b["block_type"] = "Text"
                    reasons = list(b.get("suspicious_reasons") or [])
                    tag = (
                        "not_header_colon" if short_colon else (
                            "caption_pattern" if is_caption else (
                                "bullet_prefix" if bullet_prefix else "not_header_sentence"
                            )
                        )
                    )
                    if tag not in [str(r) for r in reasons]:
                        reasons.append(tag)
                    b["suspicious_reasons"] = reasons
                    b["is_suspicious"] = True
                    b["suspicion_confidence"] = float(b.get("suspicion_confidence") or 0.9)
        data["suspicious_block_count"] = 0
        data["status"] = "Completed"
        data["suspicious_block_count"] = 0
        data["status"] = "Completed"
        out = json_output_dir / "03_markup.json"
        out.write_text(json.dumps(data, indent=2))
        print(f"[offline] Heuristic demotion applied; wrote {out}")
        # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
        return out

    # Configure logging sink per stage run
    try:
        from loguru import logger as _lg

        # _lg.remove()  # DO NOT REMOVE global handlers
        _lg.add(
            str(stage_output_dir / "stage_03_suspicious_headers.log"),
            level="DEBUG" if debug else "INFO",
            enqueue=True,
            backtrace=True,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass

    # Enforce design: defer ArangoDB until after Step 09
    if persist_headers:
        try:
            logger.warning(
                "Ignoring --persist-headers: ArangoDB persistence is deferred until after Step 09 (export stages handle DB)."
            )
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
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
    # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
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
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
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
    # Minimal entry: support `run <BLOCKS_JSON> <ANNO_DIR> -o <OUT>`
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception as exc:
        log_stage_error('03_suspicious_headers', exc, {'context': '03'})
        raise
        pass
    import sys
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.03_suspicious_headers <BLOCKS_JSON> <ANNO_DIR> [OUT_DIR]",
            file=sys.stderr,
        )
        sys.exit(2)
    if argv[0] == "sanity":
        sys.exit(sanity())
    if argv[0] == "run":
        try:
            blocks_json = Path(argv[1])
            anno_dir = Path(argv[2])
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            print("Missing args", file=sys.stderr)
            sys.exit(2)
        out_dir = Path("data/results/pipeline")
        if "-o" in argv:
            try:
                out_dir = Path(argv[argv.index("-o") + 1])
            except Exception as exc:
                log_stage_error('03_suspicious_headers', exc, {'context': '03'})
                raise
                pass
    else:
        try:
            blocks_json = Path(argv[0])
            anno_dir = Path(argv[1])
        except Exception as exc:
            log_stage_error('03_suspicious_headers', exc, {'context': '03'})
            raise
            print("Missing args", file=sys.stderr)
            sys.exit(2)
        out_dir = Path(argv[2]) if len(argv) > 2 else Path("data/results/pipeline")
    out = run(blocks_json, anno_dir, out_dir)
    print(str(out))
