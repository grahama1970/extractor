#!/usr/bin/env python3
"""Scenario: Negative E2E with corrupt/invalid PDF input (offline-friendly)

Runs only when SCENARIO_NEGATIVE=1 or PIPELINE_LIVE=1 is set.
Verifies non-zero exit and writes a summary artifact to scripts/artifacts.
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = Path(os.getenv("SCENARIOS_ARTIFACT_ROOT", ROOT / "scripts" / "artifacts"))
ART.mkdir(parents=True, exist_ok=True)


def ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds").replace(":", "-").split(".")[0] + "Z"


def main() -> int:
    if os.getenv("SCENARIO_NEGATIVE", "").lower() not in {"1", "true", "yes"} and os.getenv(
        "PIPELINE_LIVE", ""
    ).lower() not in {"1", "true", "yes"}:
        print("SKIP: set SCENARIO_NEGATIVE=1 to run corrupt-PDF negative scenario")
        return 0

    # Create a bogus input (not a PDF)
    bogus = ROOT / "data" / "input" / "pipeline" / f"corrupt_{ts()}.pdf"
    bogus.parent.mkdir(parents=True, exist_ok=True)
    bogus.write_text("this is not a PDF", encoding="utf-8")

    out_dir = ROOT / "data" / "results" / "pipeline_runs" / ("neg_corrupt_" + ts())
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline",
        "--pdf",
        str(bogus),
        "--out",
        str(out_dir.parent),
        "--summary-only",
        "--skip-fig-descriptions",
        "--skip-export",
    ]
    env = os.environ.copy()
    log_path = ART / f"pdf_negative_corrupt_{ts()}.log"
    with log_path.open("w", encoding="utf-8", errors="ignore") as fh:
        fh.write("COMMAND: " + " ".join(cmd) + "\n\n")
        fh.flush()
        code = subprocess.call(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)

    summary = {
        "ok": code != 0,  # non-zero expected
        "exit_code": code,
        "pdf": str(bogus),
        "results_parent": str(out_dir.parent),
        "log": str(log_path),
        "negative_case": "corrupt_pdf",
    }
    summary_path = ART / f"pdf_negative_corrupt_{ts()}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"pdf_negative_corrupt: exit={code} log={log_path} summary={summary_path}")
    # Do not fail the scenario runner; we assert correctness via 'ok'
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
