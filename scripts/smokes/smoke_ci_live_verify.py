#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    out = Path(os.environ.get("OUT", "data/results/pipeline_live_ci"))
    sec = json.loads((out / "04_section_builder" / "json_output" / "04_sections.json").read_text())
    sections = sec.get("sections") or []

    tgt = os.environ.get("CONTRACT_EXPECT_SECTIONS")
    if tgt:
        want = int(tgt)
        # top-level count equals base-level count
        levels = [s.get("level") for s in sections if isinstance(s.get("level"), int)]
        base = min(levels) if levels else 1
        got = sum(1 for s in sections if int(s.get("level", base)) == base)
        if got != want:
            fail(f"sections top-level count {got} != expected {want}")

    ann = json.loads((out / "09a_pdf_annotator" / "json_output" / "annotations.json").read_text())
    merged = int((ann.get("summary") or {}).get("merged_table_groups", 0))
    if merged < 1:
        fail("expected at least one merged table group in annotations.json")

    req = json.loads(
        (out / "07_requirements_miner" / "json_output" / "07_requirements_summary.json").read_text()
    )
    total = int(req.get("total_requirements", req.get("total", 0)))
    if total < 12:
        fail("expected >=12 requirements")
    # Accept any of the known keys for conditional counts
    cond = int(
        req.get("conditional_requirements")
        or req.get("conditional")
        or req.get("with_condition", 0)
        or 0
    )
    if cond < 2:
        fail("expected >=2 conditional requirements (live)")

    print("[OK] live verify passed: merged groups, section count, and requirements")


if __name__ == "__main__":
    main()
