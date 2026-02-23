#!/usr/bin/env python3
"""
gate_s01.py - Gate for S01: Annotation Processor

Reads expected values from fixture contract.
Usage: python gate_s01.py --fixture BHT_CV32A65X_test
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "01_annotation_processor"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    """Load the contract for this step from the fixture."""
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s01.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s01.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    """Run all gate checks."""
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_count = expected.get("annotation_count")

    annotations_file = JSON_DIR / "01_annotations.json"
    data = load_json(annotations_file, required_keys=["annotations"])

    annotations = data.get("annotations", [])
    actual_count = len(annotations)

    if expected_count is not None and actual_count != expected_count:
        raise GateError(
            message="Annotation count mismatch",
            expected=expected_count,
            actual=actual_count,
            file=str(annotations_file),
            hint="Check PDF annotations or SPEC.md",
        )

    print(
        f"✅ Annotation count: {actual_count}" + (f" == {expected_count}" if expected_count else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S01: Annotation Processor")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S01: Annotation Processor", lambda: checks(args.fixture)))
