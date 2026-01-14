from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def env_with_pythonpath() -> dict:
    env = os.environ.copy()
    src_root = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_root if not existing else f"{src_root}{os.pathsep}{existing}"
    return env


__all__ = ["ROOT", "env_with_pythonpath"]
