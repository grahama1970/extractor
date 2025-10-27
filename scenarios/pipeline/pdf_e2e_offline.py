#!/usr/bin/env python3
"""Scenario: Offline PDF E2E (Stages 01→10) via pipeline.run_all

SKIP by default. Runs only when SCENARIO_PDF_E2E=1 or PIPELINE_LIVE=1 is set.
Runs offline-friendly flags (no LLM/DB), writes a summary JSON artifact and
points to the pipeline output directory for manual inspection.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = Path(os.getenv("SCENARIOS_ARTIFACT_ROOT", ROOT / "scripts" / "artifacts"))
ART.mkdir(parents=True, exist_ok=True)


def ts() -> str:
    return (
        datetime.utcnow()
        .isoformat(timespec="seconds")
        .replace(":", "-")
        .split(".")[0]
        + "Z"
    )


def pick_pdf() -> Path | None:
    candidates = list((ROOT / "data").rglob("*.pdf"))
    if not candidates:
        return None
    # Prefer input/2505.03335v2.pdf when available
    for p in candidates:
        if "2505.03335v2.pdf" in str(p):
            return p
    return candidates[0]


def main() -> int:
    if os.getenv("SCENARIO_PDF_E2E", "").lower() not in {"1", "true", "yes"} and os.getenv(
        "PIPELINE_LIVE", ""
    ).lower() not in {"1", "true", "yes"}:
        print("SKIP: set SCENARIO_PDF_E2E=1 to run offline PDF E2E")
        return 0

    pdf_env = os.getenv("PDF_PATH")
    pdf_path = Path(pdf_env) if pdf_env else pick_pdf()
    if not pdf_path or not pdf_path.exists():
        print("SKIP: no PDF_PATH set and no data/*.pdf found")
        return 0

    out_dir = ROOT / "data" / "results" / "pipeline_runs" / ("pdf_e2e_" + ts())
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline",
        "--pdf",
        str(pdf_path),
        "--out",
        str(out_dir.parent),
        "--summary-only",
        "--skip-fig-descriptions",
        "--skip-export",
    ]
    env = os.environ.copy()
    log_path = ART / f"pdf_e2e_offline_{ts()}.log"
    with log_path.open("w", encoding="utf-8", errors="ignore") as fh:
        fh.write("COMMAND: " + " ".join(cmd) + "\n\n")
        fh.flush()
        code = subprocess.call(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)

    summary = {
        "ok": code == 0,
        "exit_code": code,
        "pdf": str(pdf_path),
        "results_parent": str(out_dir.parent),
        "log": str(log_path),
    }
    summary_path = ART / f"pdf_e2e_offline_{ts()}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"pdf_e2e_offline: exit={code} log={log_path} summary={summary_path}")
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
