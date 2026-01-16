#!/usr/bin/env python3
"""
gate_s00.py - Gate for S00: Profile Detector

Validates that Step 00 correctly assessed the PDF characteristics.
Reads expected values from fixture contract (s00.json).

Usage: python gate_s00.py --fixture arxiv_archetype
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "00_profile_detector"


def load_contract(fixture_name: str) -> dict:
    """Load the contract for this step from the fixture."""
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s00.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s00.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py --fixture " + fixture_name
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    """Run all gate checks for Step 00."""
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    
    # Load Step 00 output
    profile_file = RESULTS_DIR / "profile.json"
    profile = load_json(profile_file, required_keys=["domain"])
    
    # Check domain
    expected_domain = expected.get("domain")
    if expected_domain:
        actual = profile.get("domain")
        if actual != expected_domain:
            raise GateError(
                message="Domain mismatch",
                expected=expected_domain,
                actual=actual,
                file=str(profile_file),
                hint="Check s00_profile_detector domain inference"
            )
        print(f"✅ Domain: {actual}")
    
    # Check layout
    expected_layout = expected.get("layout", {})
    if expected_layout:
        actual_layout = profile.get("layout", {})
        exp_cols = expected_layout.get("columns")
        act_cols = actual_layout.get("columns")
        if exp_cols and act_cols != exp_cols:
            raise GateError(
                message="Column count mismatch",
                expected=exp_cols,
                actual=act_cols,
                file=str(profile_file),
                hint="Check pymupdf4llm multi-column detection"
            )
        print(f"✅ Layout: {actual_layout.get('columns')}-column")
    
    # Check route
    expected_route = expected.get("route")
    if expected_route:
        actual_route = profile.get("route")
        if actual_route != expected_route:
            raise GateError(
                message="Route mismatch",
                expected=expected_route,
                actual=actual_route,
                file=str(profile_file),
                hint="Check complexity thresholds in presets.py"
            )
        print(f"✅ Route: {actual_route}")
    
    # Check elements
    expected_elements = expected.get("elements", {})
    if expected_elements:
        actual_elements = profile.get("elements", {})
        for key, exp_val in expected_elements.items():
            act_val = actual_elements.get(key)
            if exp_val is not None and act_val != exp_val:
                raise GateError(
                    message=f"Element '{key}' mismatch",
                    expected=exp_val,
                    actual=act_val,
                    file=str(profile_file),
                    hint=f"Check {key} detection in s00_profile_detector"
                )
        print(f"✅ Elements: {actual_elements}")
    
    # Summary
    print(f"\n✅ Step 00 Profile validated for fixture '{fixture_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S00: Profile Detector")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S00: Profile Detector", lambda: checks(args.fixture)))
