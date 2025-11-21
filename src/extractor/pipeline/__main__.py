#!/usr/bin/env python3
from __future__ import annotations

# Ensure the local SciLLM/litellm repo is importable first so scillm.paved
# is available for preflight and router helpers when running the pipeline.
try:
    import sys
    from pathlib import Path

    _litellm_repo = Path.home() / "workspace" / "experiments" / "litellm"
    if _litellm_repo.exists():
        _litellm_str = str(_litellm_repo)
        if _litellm_str not in sys.path:
            sys.path.insert(0, _litellm_str)
except Exception:
    # Best-effort; do not block pipeline run on this convenience hook.
    pass

from .run_pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
