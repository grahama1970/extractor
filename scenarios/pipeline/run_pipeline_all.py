#!/usr/bin/env python3
"""Scenario: Run the full pipeline driver and capture a summary.

Notes
- Steps are non-deterministic; this scenario only orchestrates and captures logs.
- It does not enforce strict expectations beyond exit code; downstream
  consumers can inspect the saved stdout/stderr artifacts.

Env knobs (optional)
- PIPELINE_ARGS: extra CLI args to pass to run_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "scripts" / "artifacts"
ART.mkdir(parents=True, exist_ok=True)

def ts() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds").replace(":", "-").replace(".", "-") + "Z"


def main() -> None:
    log = ART / f"pipeline_all_{ts()}.log"
    args = [sys.executable, str(ROOT / "src" / "extractor" / "pipeline" / "run_all.py")]
    extra = os.getenv("PIPELINE_ARGS", "").strip()
    if extra:
        args.extend(extra.split())

    with log.open("w", encoding="utf-8", errors="ignore") as fh:
        fh.write("COMMAND: " + " ".join(args) + "\n\n")
        fh.flush()
        proc = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT)
        code = proc.returncode
    print(f"pipeline/run_pipeline_all: exit={code} log={log}")
    # Treat non-zero as failure to surface issues, but do not attempt to parse content
    sys.exit(code)


if __name__ == "__main__":
    main()

