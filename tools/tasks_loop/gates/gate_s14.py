#!/usr/bin/env python3
"""
gate_s14.py - Gate for S14: Report Generator

Reads expected values from fixture contract.
Usage: python gate_s14.py --fixture BHT_CV32A65X_test
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "14_report_generator"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s14.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s14.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py"
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_status = expected.get("status", "PASS")
    
    # Check JSON report exists
    json_path = RESULTS_DIR / "json_output" / "final_report.json"
    if not json_path.exists():
        raise GateError(
            message="final_report.json not found",
            expected="file exists",
            actual="missing",
            file=str(json_path),
            hint="Run S14"
        )
    
    report = load_json(json_path, required_keys=["verification"])
    
    # Check verification status
    verification = report.get("verification", {})
    actual_status = verification.get("status")
    
    if actual_status != expected_status:
        issues = verification.get("issues", [])
        raise GateError(
            message="Report status mismatch",
            expected=expected_status,
            actual=actual_status,
            file=str(json_path),
            hint=f"Issues: {issues[:3]}"
        )
    
    print(f"✅ final_report.json exists")
    print(f"✅ Status: {actual_status} == {expected_status}")
    
    # Check MD report exists
    md_path = RESULTS_DIR / "text_output" / "report.md"
    if not md_path.exists():
        raise GateError(
            message="report.md not found",
            expected="file exists",
            actual="missing",
            file=str(md_path),
            hint="Check S14 execution"
        )
    
    print(f"✅ report.md exists")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S14: Report Generator")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S14: Report Generator", lambda: checks(args.fixture)))
