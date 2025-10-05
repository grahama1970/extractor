"""
Compatibility shim for tests expecting extractor.pipeline.steps._07_reflow_section.
Loads sibling file "07_reflow_section.py" via importlib and re-exports its public symbols.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path

_FILE = Path(__file__).with_name("07_reflow_section.py")
_SPEC = importlib.util.spec_from_file_location(
    "extractor.pipeline.steps._07_reflow_section_proxy", str(_FILE)
)
if _SPEC and _SPEC.loader:
    _MOD = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_MOD)  # type: ignore[attr-defined]
    for _name in dir(_MOD):
        if not _name.startswith("_"):
            globals()[_name] = getattr(_MOD, _name)
else:
    raise ImportError(f"Cannot import Stage 07 reflow module from {_FILE}")
