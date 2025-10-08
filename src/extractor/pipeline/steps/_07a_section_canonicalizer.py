from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_target = Path(__file__).with_name("07a_section_canonicalizer.py")
_name = "steps_07a_section_canonicalizer"
_spec = importlib.util.spec_from_file_location(_name, str(_target))
if _spec and _spec.loader:
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
    sys.modules[_name] = _mod
    run = getattr(_mod, "run")
else:
    raise ImportError("Unable to load 07a_section_canonicalizer module")

