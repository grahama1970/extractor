#!/usr/bin/env python3
"""
gate_s02.py - Gate for S02: Marker Blocks

Reads expected values from fixture contract.
Usage: python gate_s02.py --fixture BHT_CV32A65X_test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add utils to path for gate_utils import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import load_json, GateError, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "02_marker_extractor"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    """Load the contract for this step from the fixture."""
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s02.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s02.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    """Run all gate checks. Raises GateError on failure."""

    # Load expected from contract
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_block_count = expected.get("block_count")

    if expected_block_count is None and expected.get("block_count_min") is None:
        # If neither is specified, maybe it's a pass?
        # But we prefer explicit contracts.
        # Check if contract is default/empty
        if not expected:
            print("⚠️ WARNING: No expectations in contract (defaulting to pass)")
            return

        raise GateError(
            message="Contract missing block_count or block_count_min",
            expected="block_count or block_count_min",
            actual="missing",
            file=str(TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s02.json"),
            hint="Add block_count to expected in SPEC.md",
        )

    # Load actual results
    blocks_file = JSON_DIR / "02_marker_blocks.json"
    data = load_json(blocks_file, required_keys=["blocks"])

    blocks = data.get("blocks", [])
    actual_count = len(blocks)

    # Exact check
    if expected_block_count is not None and actual_count != expected_block_count:
        raise GateError(
            message="Block count mismatch",
            expected=expected_block_count,
            actual=actual_count,
            file=str(blocks_file),
            hint="Check S02 execution logs for extraction errors",
        )

    # Minimum check
    min_count = expected.get("block_count_min")
    if min_count is not None and actual_count < min_count:
        raise GateError(
            message="Block count below minimum",
            expected=f">={min_count}",
            actual=actual_count,
            file=str(blocks_file),
            hint="Check if pages were skipped or OCR failed",
        )

    msg = f"✅ Block count: {actual_count}"
    if expected_block_count:
        msg += f" == {expected_block_count}"
    if min_count:
        msg += f" (>= {min_count})"
    print(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S02: Marker Blocks")
    parser.add_argument("--fixture", required=True, help="Fixture name (e.g., BHT_CV32A65X_test)")
    args = parser.parse_args()

    sys.exit(run_gate("S02: Marker Blocks", lambda: checks(args.fixture)))
