#!/usr/bin/env python3
"""
gate_s05c.py - Gate for S05c: Table Merger

Reads expected values from fixture contract.
Usage: python gate_s05c.py --fixture BHT_CV32A65X_test
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "05c_table_merger"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s05c.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s05c.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_tables = expected.get("merged_table_count")

    merged_file = JSON_DIR / "05c_merged_tables.json"

    if not merged_file.exists():
        if expected_tables == 0:
            print("✅ Merged tables: 0 (File not created, matches expected)")
            return
        raise GateError(
            message="Output file not found",
            expected="05c_merged_tables.json",
            actual="missing",
            file=str(merged_file),
            hint="Did S05c fail?",
        )

    data = load_json(merged_file, required_keys=["tables"])

    tables = data.get("tables", [])
    actual_count = len(tables)

    if expected_tables is not None and actual_count != expected_tables:
        raise GateError(
            message="Merged table count mismatch",
            expected=expected_tables,
            actual=actual_count,
            file=str(merged_file),
            hint="Check table merging logic or SPEC.md",
        )

    # Check for empty tables
    for t in tables:
        # S05c might drop CSV to force S07 regeneration. Check pandas_df.
        df = t.get("pandas_df")
        if not df or (isinstance(df, list) and not df):
            raise GateError(
                message=f"Table {t.get('id', '?')} is empty",
                expected="non-empty pandas_df",
                actual="empty",
                file=str(merged_file),
                hint="Check extraction",
            )

    print(
        f"✅ Merged tables: {actual_count}" + (f" == {expected_tables}" if expected_tables else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S05c: Table Merger")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S05c: Table Merger", lambda: checks(args.fixture)))
