from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import find_dotenv
from loguru import logger


REDACT_KEYS = {
    "CHUTES_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
}


def _redact_value(k: str, v: str | None) -> str:
    if not v:
        return ""
    if k in REDACT_KEYS:
        return f"{v[:6]}***"
    return v


def log_env_snapshot(stage: str, extra: Dict[str, Any] | None = None) -> None:
    """Log a concise environment snapshot for provider/venv diagnosis.

    - Shows python exe + sys.prefix (venv), .env path, and key provider vars (redacted)
    - Records model slugs for the current stage
    """
    try:
        env = os.environ
        rows = {
            "stage": stage,
            "python_exe": sys.executable,
            "sys_prefix": sys.prefix,
            "cwd": str(Path.cwd()),
            "dotenv_path": find_dotenv(usecwd=True) or "(not found)",
            "CHUTES_API_BASE": env.get("CHUTES_API_BASE"),
            "OPENAI_BASE_URL": env.get("OPENAI_BASE_URL"),
            "CHUTES_API_KEY": _redact_value("CHUTES_API_KEY", env.get("CHUTES_API_KEY")),
            "OPENAI_API_KEY": _redact_value("OPENAI_API_KEY", env.get("OPENAI_API_KEY")),
            # Vision/text models (common names)
            "LITELLM_SMALL_VLM_MODEL": env.get("LITELLM_SMALL_VLM_MODEL"),
            "LITELLM_MED_VLM_MODEL": env.get("LITELLM_MED_VLM_MODEL"),
            "LITELLM_LARGE_VLLM_MODEL": env.get("LITELLM_LARGE_VLLM_MODEL") or env.get("LITELLM_LARGE_VLM_MODEL"),
            "LITELLM_DEFAULT_MODEL": env.get("LITELLM_DEFAULT_MODEL"),
        }
        if extra:
            rows.update(extra)
        logger.info("env_snapshot: {}", rows)
    except Exception as e:
        logger.warning("env_snapshot failed: {}", e)

