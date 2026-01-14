#!/usr/bin/env python3
"""
gate_s05.py - Gate for S05: Table Extractor

Reads expected values from fixture contract.
Usage: python gate_s05.py --fixture BHT_CV32A65X_test
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
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s05.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s05.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py"
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_table_count = expected.get("table_count")
    
    tables_file = JSON_DIR / "05_tables.json"
    data = load_json(tables_file, required_keys=["tables"])
    
    tables = data.get("tables", [])
    actual_count = len(tables)
    
    if expected_table_count is not None:
        if actual_count < expected_table_count:
            raise GateError(
                message="Table count below expected",
                expected=f">={expected_table_count}",
                actual=actual_count,
                file=str(tables_file),
                hint="Check Camelot extraction (maybe tables missed?)"
            )
        elif actual_count > expected_table_count:
            print(f"⚠️  Table count higher than expected ({actual_count} > {expected_table_count}). Assuming splits.")
        else:
            print(f"✅ Table count: {actual_count} == {expected_table_count}")
    else:
        print(f"✅ Table count: {actual_count} (No contract)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S05: Table Extractor")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S05: Table Extractor", lambda: checks(args.fixture)))
