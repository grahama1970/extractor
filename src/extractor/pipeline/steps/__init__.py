"""Pipeline steps package.

Notes on import names
- Step files are named with numeric prefixes (e.g., `09_section_summarizer.py`).
- Python identifiers cannot start with digits, which makes direct imports
  like `from . import 09_section_summarizer` invalid.

To make these importable in tests and tooling, we dynamically load each step
module under a stable alias of the form `sXX_name` (e.g., `s09_section_summarizer`).

Example usage:
    from extractor.pipeline.steps import s09_section_summarizer as step09
    app = step09.build_cli()
"""

from __future__ import annotations

import re
import sys
import importlib.util
from pathlib import Path
from typing import List

__all__: List[str] = []


def __getattr__(name: str):  # noqa: D401
    """Lazy-load a step module under alias `sXX_name` when accessed.

    This avoids import-time side effects from unrelated step modules.
    """
    m = re.match(r"^s(\d{2})_([A-Za-z0-9_]+)$", name)
    if not m:
        raise AttributeError(name)
    num, stem = m.groups()
    filename = f"{num}_{stem}.py"
    file_path = Path(__file__).parent / filename
    if not file_path.exists():
        raise AttributeError(name)

    module_name = f"extractor.pipeline.steps.{name}"
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if not spec or not spec.loader:
        raise AttributeError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    sys.modules[module_name] = module
    globals()[name] = module
    if name not in __all__:
        __all__.append(name)
    return module
