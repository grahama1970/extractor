#!/usr/bin/env python3
"""
gate_s03.py - Gate for S03: Suspicious Headers (LLM)

Reads expected values from fixture contract.
Usage: python gate_s03.py --fixture BHT_CV32A65X_test
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "03_suspicious_headers"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s03.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s03.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py"
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_verified = expected.get("llm_verification_present")
    
    blocks_file = JSON_DIR / "03_verified_blocks.json"
    data = load_json(blocks_file, required_keys=["blocks"])
    
    blocks = data.get("blocks", [])
    
    # Check if LLM verification ran (look for llm_verification field in at least one block)
    if expected_verified:
        has_verification = any("llm_verification" in b for b in blocks)
        if not has_verification:
            raise GateError(
                message="LLM verification missing",
                expected="llm_verification fields present",
                actual="missing",
                file=str(blocks_file),
                hint="Check S03 execution or skipped LLM calls"
            )
        print(f"✅ LLM verification present")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S03: Suspicious Headers")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S03: Suspicious Headers", lambda: checks(args.fixture)))
