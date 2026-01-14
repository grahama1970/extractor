#!/usr/bin/env python3
"""
gate_s07.py - Gate for S07: DuckDB Ingest

Reads expected values from fixture contract.
Usage: python gate_s07.py --fixture BHT_CV32A65X_test
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
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s07.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s07.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py"
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    
    # Find database
    db_path = PIPELINE_DIR / "pipeline.duckdb"
    if not db_path.exists():
        db_path = PIPELINE_DIR / "corpus.duckdb"
    if not db_path.exists():
        raise GateError(
            message="DuckDB not found",
            expected="pipeline.duckdb or corpus.duckdb",
            actual="missing",
            file=str(PIPELINE_DIR),
            hint="Run S07 first"
        )
    
    con = duckdb.connect(str(db_path), read_only=True)
    
    # Check tables exist
    required_tables = ["sections", "blocks", "tables", "figures", "merged_content"]
    for table in required_tables:
        result = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        if result is None:
            raise GateError(
                message=f"Table {table} missing or empty",
                expected="table exists",
                actual="missing",
                file=str(db_path),
                hint=f"Check S07 ingestion for {table}"
            )
        print(f"✅ Table {table}: {result[0]} rows")
    
    # Check expected row counts
    if expected.get("sections_rows"):
        actual = con.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        if actual != expected["sections_rows"]:
            raise GateError(
                message="Sections row count mismatch",
                expected=expected["sections_rows"],
                actual=actual,
                file=str(db_path),
                hint="Check S04 output"
            )
    
    con.close()
    print(f"✅ DuckDB structure verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S07: DuckDB Ingest")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S07: DuckDB Ingest", lambda: checks(args.fixture)))
