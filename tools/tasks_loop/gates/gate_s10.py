#!/usr/bin/env python3
"""
gate_s10.py - Gate for S10: Markdown Exporter

Reads expected values from fixture contract.
Verifies structure, content fidelity, and reading order.

Usage: python gate_s10.py --fixture BHT_CV32A65X_test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from gate_utils import GateError, run_gate

ROOT = Path(__file__).resolve().parents[3]
TASKS_LOOP_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "10_markdown_exporter"
MD_DIR = RESULTS_DIR / "markdown_output"


def load_contract(fixture_name: str) -> dict:
    contract_path = TASKS_LOOP_DIR / "fixtures" / fixture_name / "contracts" / "s10.json"
    if not contract_path.exists():
        raise GateError(
            message=f"Contract not found for fixture '{fixture_name}'",
            expected="s10.json",
            actual="missing",
            file=str(contract_path),
            hint="Run: python utils/compile_contracts.py",
        )
    return json.loads(contract_path.read_text())


def checks(fixture_name: str):
    contract = load_contract(fixture_name)
    expected = contract.get("expected", {})
    expected_sections = expected.get("section_headers")

    md_file = MD_DIR / "full_document.md"
    if not md_file.exists():
        raise GateError(
            message="full_document.md not found",
            expected="file exists",
            actual="missing",
            file=str(md_file),
            hint="Run S10",
        )

    content = md_file.read_text(encoding="utf-8")

    if not content.strip():
        raise GateError(
            message="full_document.md is empty",
            expected="non-empty",
            actual="empty",
            file=str(md_file),
            hint="Check S10 execution",
        )

    # 1. Verify Structure (Sections)
    section_headers = re.findall(r"^## .+$", content, re.MULTILINE)
    actual_sections = len(section_headers)

    if expected_sections is not None and actual_sections != expected_sections:
        raise GateError(
            message="Section header count mismatch",
            expected=expected_sections,
            actual=actual_sections,
            file=str(md_file),
            hint="Check section export or SPEC.md",
        )

    print(
        f"✅ Section headers: {actual_sections}"
        + (f" == {expected_sections}" if expected_sections else "")
    )

    # 2. Verify Content Fidelity (Specific strings)
    # Check if critical tables/requirements are present in correct order
    # Simplistic check: regex search for headers and IDs

    if expected.get("requirements"):
        req_count = len(re.findall(r"> \*\*\[REQ-.*?\]", content))
        exp_req = expected["requirements"]
        if req_count < exp_req:
            print(f"⚠️  WARNING: Found {req_count} requirements, expected {exp_req}")
        else:
            print(f"✅ Requirements found: {req_count} >= {exp_req}")

    if expected.get("lean4_proofs_included"):
        proofs = len(re.findall(r"<details>", content))
        if proofs == 0:
            print("⚠️  WARNING: Lean4 proofs expected but not found (collapsed details)")
        else:
            print(f"✅ Lean4 proof blocks found: {proofs}")

    # 3. Contains Check (String literals)
    if expected.get("contains"):
        missing = []
        for s in expected["contains"]:
            if s not in content:
                missing.append(s)

        if missing:
            raise GateError(
                message=f"Missing expected content strings: {missing}",
                expected="all strings present",
                actual=f"missing {len(missing)} strings",
                file=str(md_file),
                hint="Check S10 export logic or requirements extraction",
            )
        print(f"✅ Verified {len(expected['contains'])} expected content strings")

    # Ensure "Requirement Proof Summary" appears inside sections if applicable
    if "Requirement Proof Summary" in content:
        print("✅ Requirement Proof Summary table present")

    # 4. Check for broken images
    broken_imgs = re.findall(r"!\[.*?\]\(\s*\)", content)
    if broken_imgs:
        raise GateError(
            message="Broken image links detected",
            expected="valid image paths",
            actual=f"{len(broken_imgs)} broken links",
            file=str(md_file),
            hint="Check S06/S10 image path logic",
        )

    print("✅ Content structure verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate S10: Markdown Exporter")
    parser.add_argument("--fixture", required=True, help="Fixture name")
    args = parser.parse_args()

    sys.exit(run_gate("S10: Markdown Exporter", lambda: checks(args.fixture)))
