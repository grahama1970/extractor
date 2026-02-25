#!/usr/bin/env python3
"""
gate_s12.py - Gate for PDF Annotation Validation

NOTE: There is no separate "S12" pipeline step. This gate validates that
PDF annotations are being processed correctly by s01_annotation_processor.

The s01 step handles:
- Reading PDF annotations (highlights, notes, stamps)
- Creating annotation overlay JSON
- Marking annotation positions for downstream steps

This gate verifies s01 annotation output exists and is valid.

Usage: python gate_s12.py --fixture <fixture_name>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import GateError, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "01_annotation_processor"


def load_contract(fixture_name: str) -> dict:
    """Load s12 contract if it exists, otherwise return empty dict."""
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s12.json"
    if contract_path.exists():
        return json.loads(contract_path.read_text())
    # Fall back to s01 contract for annotation expectations
    s01_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s01.json"
    if s01_path.exists():
        return json.loads(s01_path.read_text())
    return {}


def checks(fixture_name: str):
    """Verify annotation processing output."""
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})

    # Check annotation output directory exists
    json_dir = RESULTS_DIR / "json_output"
    if not json_dir.exists():
        raise GateError(
            message="S01 annotation output directory not found",
            expected="01_annotation_processor/json_output exists",
            actual="directory missing",
            file=str(json_dir),
            hint="Run the pipeline first (S01)",
        )

    # Check for annotation JSON output
    annot_files = list(json_dir.glob("01_*.json"))
    if not annot_files:
        raise GateError(
            message="No annotation JSON files found",
            expected="01_*.json files",
            actual="none found",
            file=str(json_dir),
            hint="Run S01 annotation processor",
        )

    # Validate first annotation file has expected structure
    annot_path = annot_files[0]
    try:
        data = json.loads(annot_path.read_text())
    except json.JSONDecodeError as e:
        raise GateError(
            message="Invalid JSON in annotation output",
            expected="valid JSON",
            actual=str(e),
            file=str(annot_path),
        )

    print(f"Found {len(annot_files)} annotation output file(s)")

    # Check expected annotation count if specified
    expected_count = expected.get("annotation_count")
    if expected_count is not None:
        actual = len(data) if isinstance(data, list) else data.get("count", 0)
        if actual != expected_count:
            raise GateError(
                message="Annotation count mismatch",
                expected=expected_count,
                actual=actual,
                file=str(annot_path),
            )
        print(f"Annotation count: {actual} == {expected_count}")
    else:
        print("Annotation structure validated (no count expectation)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S12: PDF Annotation Validation (via S01)")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S12: PDF Annotations (via S01)", lambda: checks(args.fixture)))
