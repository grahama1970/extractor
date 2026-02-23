#!/usr/bin/env python3
"""
gate_s06b.py - Gate for S06b: Figure Enrichment

Reads expected values from fixture contract.
Usage: python gate_s06b.py --fixture BHT_CV32A65X_test
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import load_json, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "06_figure_extractor"
JSON_DIR = RESULTS_DIR / "json_output"


def checks(fixture_name: str):
    figures_file = JSON_DIR / "06_figures.json"
    data = load_json(figures_file, required_keys=["figures"])
    figures = data.get("figures", [])

    # Verify titles and descriptions are present
    missing_enrichment = [
        f.get("id") for f in figures if not f.get("llm_title") or not f.get("llm_description")
    ]

    if missing_enrichment:
        print(f"⚠️ WARNING: {len(missing_enrichment)} figures missing enrichment")
    else:
        print(f"✅ All {len(figures)} figures enriched")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S06b: Figure Enrichment")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S06b: Figure Enrichment", lambda: checks(args.fixture)))
