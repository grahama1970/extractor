from __future__ import annotations

"""
Local SciLLM shim to satisfy imports in tests and adapters.

Design
- Provide a minimal `Router` class exposing `.completion/.acompletion`.
- Re-export lightweight `completion/acompletion` that delegate to the sibling
  litellm-backed implementation if available (../litellm/scillm).
- Extend package `__path__` to include the sibling `scillm` folder so that
  `scillm.extras.*` imports continue to work without vendoring.

This avoids tight coupling while honoring the repo's SciLLM-first policy.
"""

from typing import Any, Dict, List, Optional
import importlib.util as _ilu
import os as _os
import sys as _sys

# Make sibling `../litellm/scillm` discoverable for `scillm.extras.*`
_HERE = _os.path.dirname(__file__)
_SIBLING = _os.path.abspath(_os.path.join(_HERE, "..", "..", "..", "litellm", "scillm"))
if _os.path.isdir(_SIBLING) and _SIBLING not in __path__:  # type: ignore[name-defined]
    __path__.append(_SIBLING)  # type: ignore[name-defined]


def _load_sibling() -> Optional[object]:
    path = _os.path.join(_SIBLING, "__init__.py")
    if not _os.path.isfile(path):
        return None
    spec = _ilu.spec_from_file_location("_scillm_sibling", path)
    if spec is None or spec.loader is None:
        return None
    mod = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[assignment]
        return mod
    except Exception:
        return None


_SIBLING_MOD = _load_sibling()


def completion(*args, **kwargs):  # pragma: no cover - passthrough
    if _SIBLING_MOD and hasattr(_SIBLING_MOD, "completion"):
        return _SIBLING_MOD.completion(*args, **kwargs)  # type: ignore[attr-defined]
    raise RuntimeError("scillm.completion unavailable (sibling module not found)")


async def acompletion(*args, **kwargs):  # pragma: no cover - passthrough
    if _SIBLING_MOD and hasattr(_SIBLING_MOD, "acompletion"):
        return await _SIBLING_MOD.acompletion(*args, **kwargs)  # type: ignore[attr-defined]
    raise RuntimeError("scillm.acompletion unavailable (sibling module not found)")


class Router:
    """Minimal Router wrapper that forwards to completion/acompletion.

    Accepts `model_list` entries shaped like:
      {"model_name": str, "litellm_params": { ... OpenAI-like params ... }}
    """

    def __init__(self, *, model_list: List[Dict[str, Any]] | None = None) -> None:
        self.model_list: List[Dict[str, Any]] = list(model_list or [])

    def _merge(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.model_list:
            return dict(kwargs)
        entry = self.model_list[0]
        lp = dict(entry.get("litellm_params", {}) or {})
        out = dict(lp)
        out.update(kwargs)
        # Honor explicit response_format shorthand
        rf = out.get("response_format")
        if isinstance(rf, str):
            out["response_format"] = {"type": rf}
        return out

    def completion(self, *args, **kwargs):
        return completion(*args, **self._merge(kwargs))

    async def acompletion(self, *args, **kwargs):
        return await acompletion(*args, **self._merge(kwargs))


__all__ = ["Router", "completion", "acompletion"]

