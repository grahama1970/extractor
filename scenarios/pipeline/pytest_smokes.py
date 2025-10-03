#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest>=8.0.0",
# ]
# ///
"""Scenario: Run legacy pytest smokes under tests/smoke/ as live checks.

This bridges remaining smokes into the scenarios framework without
reorganizing deterministic unit tests under tests/.

Environment:
  - SMOKE_FILTER: optional path or keyword to pass to pytest (e.g.,
    'tests/smoke/test_stage05_tables_smoke.py::test_basic')
  - PYTEST_FLAGS: extra flags (e.g., '-q -k smoke')
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    smoke_root = root / "tests" / "smoke"
    if not smoke_root.exists():
        print("Scenario pipeline/pytest_smokes: SKIP (no tests/smoke)")
        sys.exit(0)

    # Default to a narrow, environment-light smoke
    filt = os.getenv("SMOKE_FILTER", "tests/smoke/test_stage10_flatten_smoke.py").strip()
    import shlex
    extra = os.getenv("PYTEST_FLAGS", "-q").strip()
    cmd = [sys.executable, "-m", "pytest"]
    if extra:
        cmd += shlex.split(extra)
    cmd += [filt or str(smoke_root)]

    print("Running:", " ".join(cmd))
    try:
        rc = subprocess.call(cmd, cwd=str(root))
    except FileNotFoundError as e:
        print("Scenario pipeline/pytest_smokes: FAIL (pytest missing)", e)
        sys.exit(1)
    if rc == 0 or rc == 5:  # 5 = no tests collected (acceptable for deprecated/ignored smokes)
        print("Scenario pipeline/pytest_smokes: OK")
        sys.exit(0)
    else:
        print(f"Scenario pipeline/pytest_smokes: FAIL (code {rc})")
        sys.exit(rc)


if __name__ == "__main__":
    main()
