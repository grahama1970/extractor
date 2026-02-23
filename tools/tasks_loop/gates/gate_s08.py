#!/usr/bin/env python3
"""
gate_s08.py - Gate for S08: Requirements Extraction

Reads expected values from fixture contract.
Usage: python gate_s08.py --fixture BHT_CV32A65X_test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    sys.exit("DuckDB required: pip install duckdb")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import GateError, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "data" / "results" / "pipeline"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s08.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s08.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_req_count = expected.get("requirement_count")

    # Find database
    db_path = PIPELINE_DIR / "pipeline.duckdb"
    if not db_path.exists():
        db_path = PIPELINE_DIR / "corpus.duckdb"
    if not db_path.exists():
        raise GateError(
            message="DuckDB not found",
            expected="pipeline.duckdb",
            actual="missing",
            file=str(PIPELINE_DIR),
            hint="Run S07 first",
        )

    con = duckdb.connect(str(db_path), read_only=True)

    # Check requirements table exists
    try:
        result = con.execute("SELECT COUNT(*) FROM requirements").fetchone()
        actual_count = result[0]
    except Exception as e:
        raise GateError(
            message="Requirements table missing",
            expected="requirements table exists",
            actual=str(e),
            file=str(db_path),
            hint="Run S08",
        )

    if expected_req_count is not None and actual_count != expected_req_count:
        raise GateError(
            message="Requirement count mismatch",
            expected=expected_req_count,
            actual=actual_count,
            file=str(db_path),
            hint="Check S08 extraction or SPEC.md",
        )

    print(
        f"✅ Requirements: {actual_count}"
        + (f" == {expected_req_count}" if expected_req_count else "")
    )
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S08: Requirements Extraction")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S08: Requirements Extraction", lambda: checks(args.fixture)))
