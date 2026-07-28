#!/usr/bin/env python3
"""Batch extract all synthetic PDFs through the pipeline.

Runs with --skip flags for speed (no LLM, no figures, no requirements).
Only S00 (profile) and S05 (tables) matter for strategy outcome data.

Usage:
    python scripts/batch_extract_synthetic.py [--workers 4] [--limit 50]
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SYNTH_DIR = Path(__file__).resolve().parent.parent / "data" / "pdfs" / "synthetic"
OUTPUT_BASE = Path(__file__).resolve().parent.parent / "data" / "output" / "synthetic_validation"


def extract_one(pdf_path: Path, out_dir: Path) -> dict:
    """Run pipeline on one PDF. Returns result dict."""
    outcomes_file = out_dir / "05_table_extractor" / "visual_output" / "05_strategy_outcomes.jsonl"
    if outcomes_file.exists():
        return {"pdf": pdf_path.name, "status": "skip", "outcomes": outcomes_file}

    env = os.environ.copy()
    env["STRATEGY_SELECTOR_MODE"] = "shadow"

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "extractor.pipeline",
                str(pdf_path), "--out", str(out_dir),
                "--skip-fig-descriptions", "--skip-llm03", "--skip-reqs07",
                "--skip-annotator09a", "--skip-export", "--skip-proving",
                "--skip-scillm-preflight", "--skip-table-descriptions",
            ],
            capture_output=True, text=True, timeout=120, env=env,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        if result.returncode == 0:
            return {"pdf": pdf_path.name, "status": "ok"}
        else:
            return {"pdf": pdf_path.name, "status": "error", "msg": result.stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"pdf": pdf_path.name, "status": "timeout"}
    except Exception as e:
        return {"pdf": pdf_path.name, "status": "exception", "msg": str(e)}


def main():
    """Parse command-line arguments and prepare PDF files for processing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    pdfs = sorted(SYNTH_DIR.glob("synth_*.pdf"))
    if args.limit:
        pdfs = pdfs[:args.limit]

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    print(f"Batch extracting {len(pdfs)} synthetic PDFs with {args.workers} workers...")

    results = {"ok": 0, "skip": 0, "error": 0, "timeout": 0, "exception": 0}

    # Sequential to avoid ArangoDB contention — pipeline already uses ProcessPool internally
    for i, pdf in enumerate(pdfs):
        out_dir = OUTPUT_BASE / pdf.stem
        r = extract_one(pdf, out_dir)
        results[r["status"]] = results.get(r["status"], 0) + 1
        status = r["status"]
        msg = f"  [{i+1}/{len(pdfs)}] {status}: {pdf.name}"
        if status == "error":
            msg += f" — {r.get('msg', '')[:100]}"
        print(msg)

    print(f"\nResults: {json.dumps(results, indent=2)}")

    # Count strategy outcomes
    outcomes = list(OUTPUT_BASE.glob("**/05_strategy_outcomes.jsonl"))
    total_records = sum(
        sum(1 for _ in open(f)) for f in outcomes
    )
    print(f"\nStrategy outcome files: {len(outcomes)}")
    print(f"Total outcome records: {total_records}")


if __name__ == "__main__":
    main()
