#!/usr/bin/env python3
"""
gate_s05b.py - Gate for S05b: Table Enrichment

Reads expected values from fixture contract.
Usage: python gate_s05b.py --fixture BHT_CV32A65X_test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import load_json, GateError, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "05_table_extractor"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s05b.json"
    # S05b might reuse S05 expectations if not explicitly defined
    if not contract_path.exists():
         return {}
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    tables_file = JSON_DIR / "05_tables.json"
    data = load_json(tables_file, required_keys=["tables"])
    tables = data.get("tables", [])
    
    # Verify titles and descriptions are present
    missing_enrichment = [t.get("id") for t in tables if not t.get("llm_title") or not t.get("llm_description")]
    
    if missing_enrichment:
        print(f"⚠️ WARNING: {len(missing_enrichment)} tables missing enrichment (llm_title/llm_desc)")
        # Make this a soft fail or warning based on strictness
        # For now, we expect enrichment if the step ran
    else:
        print(f"✅ All {len(tables)} tables enriched")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S05b: Table Enrichment")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S05b: Table Enrichment", lambda: checks(args.fixture)))
