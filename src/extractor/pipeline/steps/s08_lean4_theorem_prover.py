#!/usr/bin/env python3
import asyncio
"""
Pipeline Stage 8: Lean 4 Theorem Proving for Requirements
=========================================================

What this stage does (read before editing)
- Input: Stage 07 reflowed sections (07_reflowed.json).
- Step A: For each section, call SciLLM (Router, chutes/text, JSON mode) to extract
  requirement candidates + table constraints (single LLM call per section).
- Step B: Prove each requirement via:
    * SciLLM extras `certainly_prove` (preferred paved path) — flow:
        1) send requirement + strategy to Certainly/Lean4 bridge (LLM writes Lean code),
        2) bridge returns multiple candidate theorems,
        3) container compiles each in Lean4,
        4) pick a compiling candidate (or return failure with compiler feedback).
    * OR external CLI if `LEAN4_CLI_CMD` is set (stdin/file JSON/JSONL contracts).
- Output: 08_theorems.json (proof results, diagnostics).

Paved-path + safety
- No manual headers or raw HTTP; SciLLM Router handles auth/headers.
- Preflight enforced via `require_scillm_preflight`.
- Heavy calls are throttled by MAX_CONCURRENT_LLM and MAX_CONCURRENT_LEAN4 envs.
- Long-running proofs: 30–300s each; treat as LLM-like service.

When this stage runs
- Only when proving is enabled (not in deterministic/offline runs).
- If Lean4 CLI or SciLLM extras aren’t available, proofs will fail; ensure one of them
  is configured (LEAN4_CLI_CMD or certainly_prove via scillm extras).
"""

import asyncio
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import textwrap
import time

# Import what we need from lean4_prover
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# Direct imports - fail fast
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from extractor.pipeline.utils.debug_utils import log_llm_call
from rich.console import Console
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
try:
    from scillm.extras.providers import certainly_prove  # type: ignore
except Exception:  # pragma: no cover - keep import-time side effects minimal
    def certainly_prove(*args, **kwargs):  # type: ignore
        raise RuntimeError("SciLLM extras/providers unavailable in this environment")
from tqdm.asyncio import tqdm
# httpx not used for LLM calls; SciLLM-only policy

from extractor.pipeline.utils.diagnostics import (
    build_stage_timings,
    get_run_id,
    gpu_metrics_available,
    iso_now,
    make_event,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
# Import from new utils/prover package (extracted execution functions)
from extractor.pipeline.utils.prover import (
    ProofResult as _ProofResult,
    prove_via_cli as _prove_via_cli,
    prove_batch_via_cli as _prove_batch_via_cli,
    execute_lean_code_docker as _execute_lean_code_docker,
    get_cli_cmd,
)
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD
from extractor.pipeline.utils.step_sanity import run_step_sanity

# Import JSON utilities
from scillm.extras.json_utils import clean_json_string

try:
    from lean4_prover.core.validation_models import get_validation_strategy
except Exception:
    get_validation_strategy = None  # type: ignore[assignment]
try:
    from lean4_prover.core.prove_requirement import ProofResult, generate_lean_code
except Exception:

    @dataclass
    class ProofResult:  # type: ignore[no-redef]
        success: bool
        lean_code: str
        stdout: str
        stderr: str
        return_code: int
        test_filename: str
        error_messages: list[str] | None = None
        proof_output: str | None = None

    async def generate_lean_code(requirement: str, strategy):  # type: ignore[no-redef]
        # Minimal stub: produce a comment-only Lean snippet to fail fast but safely
        return (
            f"-- requirement: {requirement}\n"
            f"-- strategy: {getattr(strategy, 'validation_approach', 'unknown')}\n"
        )


# --- Initialization ---
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)

# SciLLM-only: legacy litellm cache disabled; define a no-op initializer
try:
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except Exception:  # pragma: no cover
    def initialize_litellm_cache():  # type: ignore
        return None

initialize_litellm_cache()

# Logger configured per run (see CLI commands below) to align with prior stages.

console = Console()
STEP_NAME = "08_lean4_theorem_prover"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# LLM Configuration
LEAN4_MODEL = os.getenv("LEAN4_MODEL", "openai/gpt-5-mini")  # extraction LLM
LEAN4_PROVER_MODEL = os.getenv("LEAN4_PROVER_MODEL", os.getenv("LEAN4_MODEL", "certainly/lean4"))
# Throttle defaults to be gentle on Chutes / prover: lower by default
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", 1))
MAX_CONCURRENT_LEAN4 = int(
    os.getenv("MAX_CONCURRENT_LEAN4_CALLS", 1)
)  # Lean 4 is heavy (30-300s per theorem)

# Optional external CLI integration (portable; avoids Docker coupling)
# Provide the full command template via LEAN4_CLI_CMD, e.g.:
#  - Stdin JSON mode: "python /path/to/cli_mini.py prove --json {stdin}"
#  - File mode:       "python /path/to/cli_mini.py prove --input {input} --output {output}"
LEAN4_CLI_CMD = os.getenv("LEAN4_CLI_CMD", "").strip()

# --- Streamlined Requirement Extraction ---


