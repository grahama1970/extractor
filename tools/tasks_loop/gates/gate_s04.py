#!/usr/bin/env python3
"""
gate_s04.py - Gate for S04: Section Builder

Reads expected values from fixture contract.
Usage: python gate_s04.py --fixture BHT_CV32A65X_test
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "04_section_builder"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s04.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s04.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_section_count = expected.get("section_count")

    sections_file = JSON_DIR / "04_sections.json"
    data = load_json(sections_file, required_keys=["sections"])

    sections = data.get("sections", [])
    actual_count = len(sections)

    # Relaxed matching (min/max/exact)
    min_count = expected.get("section_count_min")
    max_count = expected.get("section_count_max")

    if expected_section_count is not None and actual_count != expected_section_count:
        raise GateError(
            message="Section count mismatch",
            expected=expected_section_count,
            actual=actual_count,
            file=str(sections_file),
            hint="Check S04 or update SPEC.md",
        )

    if min_count is not None and actual_count < min_count:
        raise GateError(
            message="Section count below minimum",
            expected=f">={min_count}",
            actual=actual_count,
            file=str(sections_file),
            hint="Check S04 or update SPEC.md",
        )

    if max_count is not None and actual_count > max_count:
        raise GateError(
            message="Section count above maximum",
            expected=f"<={max_count}",
            actual=actual_count,
            file=str(sections_file),
            hint="Check S04 or update SPEC.md",
        )

    print(f"✅ Section count: {actual_count} == {expected_section_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S04: Section Builder")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S04: Section Builder", lambda: checks(args.fixture)))
