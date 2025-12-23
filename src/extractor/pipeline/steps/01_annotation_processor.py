#!/usr/bin/env python3
"""
PDF Annotation Extract → Context Capture → LLM Interpretation → Clean PDF → ArangoDB
Function-first with a minimal __main__ for VS Code debugging.
"""

import os
import json
import base64
import asyncio
import textwrap
from pathlib import Path
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, cast
from datetime import datetime
import time

# Import log_stage_error early so it can be used in import-time exception handling
from extractor.pipeline.utils.reliability import log_stage_error

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None  # type: ignore

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 01 requires it.", file=sys.stderr)
    raise
from loguru import logger
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.debug_utils import log_timing
from extractor.pipeline.steps.scillm_preflight_validator import (
    validate_scillm_env_sync,
    require_scillm_preflight,
    quick_scillm_check
)
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.annots.runner import run

from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    make_event,
    classify_llm_error,
)
from extractor.pipeline.utils.prompt_loader import load_prompt

# Use pipeline-local JSON utilities to avoid heavy core service deps during this stage
from extractor.pipeline.utils.json_utils import clean_json_string
# SciLLM-only policy: avoid importing legacy LiteLLM cache to prevent
# background threads or side effects that can block process exit.

# ------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------
DEBUG = False
RENDER_DPI = 200
ANNOT_FREETEXT = "FreeText"
STEP_NAME = "01_annotation_processor"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


## CLI removed: call run(...) or debug_bundle(...) from Python or use a tiny debug script.


"""Relevant-to rules config (optional file-based)."""


def _load_relevant_rules() -> Dict[str, Any]:
    """Load relevant rules from config/relevant_rules.json if present; otherwise use defaults."""
    try:
        here = Path(__file__).resolve().parent.parent / "config" / "relevant_rules.json"
        if here.exists():
            with open(here, "r") as f:
                return cast(Dict[str, Any], json.load(f))
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
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
        except Exception as exc:
            log_stage_error('01_annotation_processor', exc, {'context': '01'})
            raise
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
            except Exception as exc:
                log_stage_error('01_annotation_processor', exc, {'context': '01'})
                raise
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
            except Exception as exc:
                log_stage_error('01_annotation_processor', exc, {'context': '01'})
                raise
                continue
    except Exception as exc:
        log_stage_error('01_annotation_processor', exc, {'context': '01'})
        raise
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
            # SciLLM-only: do not consult LITELLM/DEFAULT_LITELLM envs
            "",
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
PROMPT = load_prompt("01_annotation_processor")


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


