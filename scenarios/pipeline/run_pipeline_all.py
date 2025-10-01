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

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART_ROOT = Path(os.getenv("SCENARIOS_ARTIFACT_ROOT", ROOT / "scripts" / "artifacts"))
ART_ROOT.mkdir(parents=True, exist_ok=True)

def ts() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds").replace(":", "-").replace(".", "-") + "Z"


def main() -> None:
    stamp = ts()
    log = ART_ROOT / f"pipeline_all_{stamp}.log"
    summary_path = ART_ROOT / f"pipeline_all_{stamp}.json"
    args = [sys.executable, str(ROOT / "src" / "extractor" / "pipeline" / "run_all.py")]
    extra = os.getenv("PIPELINE_ARGS", "").strip()
    if extra:
        args.extend(extra.split())

    t0 = time.time()
    with log.open("w", encoding="utf-8", errors="ignore") as fh:
        fh.write("COMMAND: " + " ".join(args) + "\n\n")
        fh.flush()
        proc = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT)
        code = proc.returncode
    elapsed = round(time.time() - t0, 3)

    summary = {"command": args, "exit_code": code, "elapsed_sec": elapsed, "artifacts": {"log": str(log)}}
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"pipeline/run_pipeline_all: exit={code} log={log} summary={summary_path}")
    sys.exit(code)


if __name__ == "__main__":
    main()
