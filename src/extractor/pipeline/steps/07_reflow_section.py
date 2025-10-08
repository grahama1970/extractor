#!/usr/bin/env python3
"""
Pipeline Stage: LLM-Based Section Reflow (offline)

This script is the final text processing stage. It runs offline (no DB access)
to perform a powerful hybrid search for relevant annotations. This rich,
dynamically-fetched context is then used to guide a VLM in reflowing and
improving the section's content. All database and search logic is self-contained.
"""

import os
from typing import Dict, Any
import pandas as pd
import re

import typer
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache
from loguru import logger
from rich.console import Console
from tqdm.asyncio import tqdm_asyncio

from extractor.pipeline.utils.json_utils import clean_json_string
from extractor.pipeline.utils.litellm_response_utils import extract_content
from extractor.pipeline.utils.image_io import (
    get_section_image_b64,
    get_table_image_b64,
    get_figure_image_b64,
    get_annotation_image_b64,
)
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    iso_now,
    make_event,
    snapshot_resources,
    build_stage_timings,
    classify_llm_error,
    gpu_metrics_available,
)
from extractor.pipeline.utils.metrics_logger import log_metric
# SciLLM client is imported directly where needed (Router/acompletion)
from extractor.pipeline.utils.model_params import (
    build_chat_extras,
)
from extractor.pipeline.utils.vision import preflight_vision_support
from extractor.pipeline.utils.text_utils import sanitize_text
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow
from extractor.pipeline.utils.numeric_auditor import audit_section_reflow
from extractor.core.schema.unified_document import SourceType
from extractor.pipeline.utils.ann_index import build_ann_index, query_ann_index, load_ann_index
from extractor.pipeline.utils.log_utils import sanitize_messages_for_return
from extractor.pipeline.utils.embeddings import ensure_embedder as _ensure_embedder
# Ensure _trim_context is defined before any runtime use (some branches call it early)
def _trim_context(raw: str, limit: int) -> str:
    if not raw:
        return ""
    try:
        return raw if len(raw) <= limit else raw[:limit] + " ..."
    except Exception:
        return str(raw)[:limit] + " ..."

# Early defaults for trim constants to avoid NameError in early branches
try:
    CONTEXT_TRIM_CHARS
except NameError:  # pragma: no cover - define default if not yet declared
    CONTEXT_TRIM_CHARS = int(os.getenv("STAGE07_CONTEXT_TRIM_CHARS", "8000"))
try:
    RETRY_TRIM_CHARS
except NameError:  # pragma: no cover
    RETRY_TRIM_CHARS = int(os.getenv("STAGE07_RETRY_TRIM_CHARS", "2000"))
