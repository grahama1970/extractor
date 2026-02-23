#!/usr/bin/env python3
"""
gate_s09.py - Gate for S09: Section Summarizer (LLM)

Reads expected values from fixture contract.
Usage: python gate_s09.py --fixture BHT_CV32A65X_test
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
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s09.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s09.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_summaries = expected.get("sections_with_summary")

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

    # Check if column exists
    try:
        con.execute("SELECT llm_summary FROM sections LIMIT 1")
    except Exception:
        raise GateError(
            message="llm_summary column missing",
            expected="column exists in sections table",
            actual="missing",
            file=str(db_path),
            hint="Run S09",
        )

    # Check count of non-null summaries
    actual_summaries = con.execute(
        "SELECT COUNT(*) FROM sections WHERE llm_summary IS NOT NULL"
    ).fetchone()[0]

    if expected_summaries is not None and actual_summaries < expected_summaries:
        raise GateError(
            message="Insufficient summaries",
            expected=f"at least {expected_summaries}",
            actual=actual_summaries,
            file=str(db_path),
            hint="Check S09 LLM execution",
        )

    print(f"✅ Sections with summary: {actual_summaries} >= {expected_summaries or 0}")
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S09: Section Summarizer")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S09: Section Summarizer", lambda: checks(args.fixture)))
