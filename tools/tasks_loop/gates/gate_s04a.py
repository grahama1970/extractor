#!/usr/bin/env python3
"""
gate_s04a.py - Gate for S04a: Layout Audit

TIGHTLY COUPLED to PIPELINE_SPEC.md:

DETERMINISTIC:
- ok: true
- errors: 0

FUZZY: None (audit is deterministic)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = ROOT / "data" / "results" / "pipeline" / "04a_layout_audit"


def main() -> int:
    print("== Gate S04a: Layout Audit ==")
    print("DETERMINISTIC assertions:")
    print("  - ok: true")
    print("  - errors: 0")
    print("FUZZY assertions: None")
    print()

    # === DETERMINISTIC CHECKS ===

    json_output_dir = RESULTS_DIR / "json_output"
    audit_file = json_output_dir / "04a_layout_audit.json"
    if not audit_file.exists():
        print(f"❌ FAIL: {audit_file} not found")
        return 1

    with open(audit_file) as f:
        audit = json.load(f)

    if not audit.get("ok", False):
        errors = audit.get("errors", 0)
        print(f"❌ FAIL: ok != true, errors field: {errors}")
        return 1
    print("✅ ok: true")

    errors = audit.get("errors", 0)
    if errors != 0:
        print(f"❌ FAIL: Expected 0 error count, got {errors}")
        return 1
    print("✅ errors: 0")

    # === FUZZY CHECKS === (none for this step)

    print()
    print("✅ Gate S04a PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
