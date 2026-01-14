#!/usr/bin/env python3
"""
gate_s06.py - Gate for S06: Figure Extractor

Reads expected values from fixture contract.
Usage: python gate_s06.py --fixture BHT_CV32A65X_test
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
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "06_figure_extractor"
JSON_DIR = RESULTS_DIR / "json_output"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s06.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s06.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py"
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_figure_count = expected.get("figure_count")
    
    figures_file = JSON_DIR / "06_figures.json"
    data = load_json(figures_file, required_keys=["figures"])
    
    figures = data.get("figures", [])
    actual_count = len(figures)
    
    if expected_figure_count is not None and actual_count != expected_figure_count:
        raise GateError(
            message="Figure count mismatch",
            expected=expected_figure_count,
            actual=actual_count,
            file=str(figures_file),
            hint="Check figure extraction or SPEC.md"
        )
    
    # Verify image files exist
    for fig in figures:
        img_path = fig.get("image_path")
        if img_path:
            full_path = ROOT / img_path if not Path(img_path).is_absolute() else Path(img_path)
            if not full_path.exists():
                raise GateError(
                    message="Figure image missing",
                    expected="image file exists",
                    actual="missing",
                    file=str(full_path),
                    hint="Check figure extraction"
                )
    
    print(f"✅ Figure count: {actual_count}" + (f" == {expected_figure_count}" if expected_figure_count else ""))
    print(f"✅ All figure images exist")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S06: Figure Extractor")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()
    
    sys.exit(run_gate("S06: Figure Extractor", lambda: checks(args.fixture)))
