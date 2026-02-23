#!/usr/bin/env python3
"""
Sanity Manifest - Maps pipeline steps to their required preflight sanity checks.

Philosophy:
- Before running a step, run ONLY the sanity checks it depends on.
- This prevents wasting time on steps that will fail due to missing dependencies.
- Sanity checks validate that project-crucial functionality works BEFORE coding.

Usage in run_pipeline.py:
    from sanity_manifest import get_step_sanity_checks, run_sanity_check

    for check in get_step_sanity_checks("s08"):
        run_sanity_check(check)
"""

import subprocess
import sys
from pathlib import Path
from typing import List

# Root of project (3 levels up: utils -> tasks_loop -> tools -> project)
ROOT = Path(__file__).resolve().parents[3]
SANITY_DIR = Path(__file__).resolve().parent.parent / "sanity"

# --------------------------------------------------------------------------
# STEP → SANITY MAPPING
# --------------------------------------------------------------------------

STEP_SANITY_MAP = {
    # S01: Requires PDF processing
    "s01": ["S1_pymupdf_open"],
    # S02: Requires Marker PDF extraction
    "s02": ["S1_pymupdf_open", "S2_marker_extract"],
    # S03: Requires LLM for header verification
    "s03": ["S5b_scillm_chutes"],
    # S04: Section building (no external deps beyond S02/S03 outputs)
    "s04": [],
    # S04a: Layout audit with section imaging
    "s04a": ["S1_pymupdf_open", "S6_section_image"],
    # S05: Table extraction via Camelot
    "s05": ["S3_camelot_extract_fixture", "S5d_table_extract_pdf"],
    # S05b: Table describing via VLM
    "s05b": ["S5c_vlm_image_call"],
    # S05c: Table merging
    "s05c": ["S5a_table_merge"],
    # S06: Figure extraction
    "s06": ["S1_pymupdf_open"],
    # S06b: Figure describing via VLM
    "s06b": ["S5c_vlm_image_call"],
    # S07: DuckDB ingestion
    "s07": ["S7_duckdb_basic", "S7b_duckdb_crud", "S7c_merged_content"],
    # S08: Requirements extraction via LLM
    "s08": ["S5b_scillm_chutes", "S7_duckdb_basic", "S8a_regex_requirements"],
    # S09: Section summarization via LLM
    "s09": ["S5b_scillm_chutes"],
    # S10: Markdown export (no external deps)
    "s10": ["S7_duckdb_basic"],
    # S11+: Lean4 proving
    "s11": ["S11_lean4_docker", "S11b_scillm_lean4"],
    # S14: Report generation (no external deps)
    "s14": ["S7_duckdb_basic"],
}


def get_step_sanity_checks(step_id: str) -> List[str]:
    """Get the list of sanity checks required for a step.

    Args:
        step_id: Step identifier (e.g., "s02", "s08", "05b")

    Returns:
        List of sanity check names (e.g., ["S1_pymupdf_open", "S2_marker_extract"])
    """
    # Normalize: strip leading zeros, lowercase, ensure "s" prefix
    normalized = step_id.lower().lstrip("s").lstrip("0")
    normalized = f"s{normalized}" if normalized else step_id.lower()

    # Try exact match first
    if normalized in STEP_SANITY_MAP:
        return STEP_SANITY_MAP[normalized]

    # Try with leading zero removed
    for key in STEP_SANITY_MAP:
        if key.lstrip("s").lstrip("0") == normalized.lstrip("s").lstrip("0"):
            return STEP_SANITY_MAP[key]

    return []


def run_sanity_check(check_name: str) -> bool:
    """Run a single sanity check by name.

    Args:
        check_name: Name of the sanity check (e.g., "S1_pymupdf_open")

    Returns:
        True if passed, False if failed.
    """
    # Look for .py or .sh file
    py_file = SANITY_DIR / f"{check_name}.py"
    sh_file = SANITY_DIR / f"{check_name}.sh"

    if py_file.exists():
        cmd = [sys.executable, str(py_file)]
    elif sh_file.exists():
        cmd = ["bash", str(sh_file)]
    else:
        print(f"⚠️ Sanity check not found: {check_name}")
        return False

    print(f"Running sanity: {check_name}...")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  ✅ {check_name}")
        return True
    else:
        print(f"  ❌ {check_name}")
        if result.stdout:
            print(f"     stdout: {result.stdout[:200]}")
        if result.stderr:
            print(f"     stderr: {result.stderr[:200]}")
        return False


def run_step_preflight(step_id: str) -> bool:
    """Run all sanity checks required for a step.

    Args:
        step_id: Step identifier

    Returns:
        True if all passed, False if any failed.
    """
    checks = get_step_sanity_checks(step_id)
    if not checks:
        return True

    print(f"== Preflight for {step_id}: {len(checks)} checks ==")
    all_passed = True
    for check in checks:
        if not run_sanity_check(check):
            all_passed = False

    return all_passed


if __name__ == "__main__":
    # Demo: run preflight for a step
    import argparse

    parser = argparse.ArgumentParser(description="Run preflight sanity checks for a step")
    parser.add_argument("step", help="Step ID (e.g., s02, s08)")
    args = parser.parse_args()

    if run_step_preflight(args.step):
        print(f"\n✅ All preflight checks passed for {args.step}")
        sys.exit(0)
    else:
        print(f"\n❌ Some preflight checks failed for {args.step}")
        sys.exit(1)
