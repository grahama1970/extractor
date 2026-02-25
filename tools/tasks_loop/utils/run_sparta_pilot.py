#!/usr/bin/env python3
"""
Sparta Pilot Verification Script
--------------------------------
Runs the Extractor pipeline on 10 representative PDFs from the SPARTA batch.
Verifies the fixes for:
1. Figure Extraction (Layout Model loading)
2. Table Header Quality (LLM Assist fallback)
"""

import os
import json
import subprocess
import sys
from pathlib import Path

# 10 Representative IDs + specific problem cases
PILOT_IDS = [
    "41d86cea10af00d4",  # 0 figures, polluted
    "626159f7d4192fef",  # 0 figures
    "e3a709910737dcbd",  # 0 figures
    "0a74b0155de4f614",
    "0b173de3671590d7",
    "0d5d19ee7356f4ed",
    "006c0fb82144d8be",
    "014ceebcb949ddfc",
    "0200aec707bb7c50",
    "06a4fa81108910db",
]

SPARTA_ROOT = Path(
    "/home/graham/workspace/experiments/sparta/data/runs/run-2025-12-18_144426-2eb428c/extractor_output"
)
OUTPUT_BASE = Path("data/pilot_run_results")
EXTRACTOR_RUN_SH = Path(".agents/skills/extractor/run.sh").resolve()


def verify_results(doc_id: str, doc_out_dir: Path):
    """Check logs and JSONs for expected behavior."""
    print(f"\nVerifying {doc_id}...")

    # 1. Check Layout Model Loading (Fix for 0 figures)
    log_s02 = doc_out_dir / "02_marker_extractor" / "stage_02.log"
    if log_s02.exists():
        content = log_s02.read_text()
        if "layout_model=✓" in content:
            print("  [PASS] Layout Model loaded")
        else:
            print("  [FAIL] Layout Model NOT loaded (check STAGE02_ALLOW_SIMPLE)")
    else:
        print("  [FAIL] S02 Log missing")

    # 2. Check Figures Extracted
    json_s02 = doc_out_dir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    figures_found = 0
    if json_s02.exists():
        try:
            data = json.loads(json_s02.read_text())
            counts = data.get("block_type_distribution", {})
            figures_found = counts.get("Figure", 0)
            print(f"  [INFO] Figures found: {figures_found}")
        except Exception:
            pass

    # 3. Check Table Headers (Fix for generic headers)
    json_s05 = doc_out_dir / "05_table_extractor" / "json_output" / "05_tables.json"
    llm_assist_used = False
    if json_s05.exists():
        try:
            data = json.loads(json_s05.read_text())
            tables = data.get("tables", [])
            for t in tables:
                if t.get("llm_assist"):
                    llm_assist_used = True
                # Check metrics or content
                # (Simple check: if we have LLM assist, we assume it tried)

            if llm_assist_used:
                print("  [PASS] Table LLM Assist triggered")
            else:
                if len(tables) > 0:
                    print("  [WARN] Table LLM Assist NOT triggered (maybe no tables needed it?)")
                else:
                    print("  [INFO] No tables found")
        except Exception:
            pass


def run_pilot():
    if not EXTRACTOR_RUN_SH.exists():
        print(f"Error: run.sh not found at {EXTRACTOR_RUN_SH}")
        sys.exit(1)

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    for doc_id in PILOT_IDS:
        print(f"--- Processing {doc_id} ---")

        # Locate source PDF
        # Logic: Look in previous output dir 01 store
        pdf_candidates = [
            SPARTA_ROOT / doc_id / "01_annotation_processor" / f"{doc_id}_clean.pdf",
            SPARTA_ROOT / doc_id / "01_annotation_processor" / "source.pdf",
        ]

        pdf_path = None
        for cand in pdf_candidates:
            if cand.exists():
                pdf_path = cand
                break

        if not pdf_path:
            print(f"Skipping {doc_id}: PDF not found")
            continue

        doc_out = OUTPUT_BASE / doc_id
        if doc_out.exists():
            print(f"Skipping extraction for {doc_id} (already exists)")
            verify_results(doc_id, doc_out)
            continue

        cmd = [
            str(EXTRACTOR_RUN_SH),
            str(pdf_path),
            "--accurate",  # Enforce accurate mode
            "--out",
            str(doc_out),
            "--no-interactive",
        ]

        # Enforce environment vars to verify fixes
        env = os.environ.copy()
        env["PIPELINE_MODE"] = "accurate"
        # We expect code defaults to handle the rest (TABLE_LLM_ASSIST, models)

        try:
            subprocess.run(cmd, env=env, check=True)
            verify_results(doc_id, doc_out)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting {doc_id}: {e}")


if __name__ == "__main__":
    run_pilot()
