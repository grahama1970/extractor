"""Load and cache prompt definitions from JSON files in the pipeline prompts directory."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptLoadError(RuntimeError):
    """Signal failure to load a prompt."""
    pass


@lru_cache(maxsize=None)
def load_prompt(name: str) -> Dict[str, str]:
    """Load a prompt definition from src/extractor/pipeline/prompts/<name>.json.

    The file must be a JSON object with at least "system" and "user" string fields.
    Cached to avoid repeated disk I/O across calls.
    """
    path = PROMPTS_DIR / f"{name}.json"
    if not path.exists():
        raise PromptLoadError(f"Prompt file not found: {path}")
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        raise PromptLoadError(f"Failed to parse prompt {name}: {exc}") from exc

    if not isinstance(data, dict):
        raise PromptLoadError(f"Prompt {name} must be a JSON object with system/user fields")
    for key in ("system", "user"):
        if key not in data or not isinstance(data[key], str) or not data[key].strip():
            raise PromptLoadError(f"Prompt {name} missing required field: {key}")
    return data  # type: ignore[return-value]
