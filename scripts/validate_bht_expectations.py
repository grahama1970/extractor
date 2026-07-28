#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main(results_dir: str) -> int:
    """Validate existence of required JSON files in results directory."""
    base = Path(results_dir)
    sections_path = base / "04_section_builder" / "json_output" / "04_sections.json"
    figures_path = base / "06_figure_extractor" / "json_output" / "06_figures.json"
    reflow_path = base / "07_reflow_section" / "json_output" / "07_reflowed.json"

    if not sections_path.exists() or not figures_path.exists() or not reflow_path.exists():
        print("Missing one or more expected files.")
        return 2

    sections = json.loads(sections_path.read_text(encoding="utf-8"))
    figures = json.loads(figures_path.read_text(encoding="utf-8"))
    reflow = json.loads(reflow_path.read_text(encoding="utf-8"))

    # 1 section expected
    sec_count = len(sections.get("sections") or sections.get("result", {}).get("sections") or [])
    # 1 figure expected
    fig_count = len(
        figures.get("figures") or figures.get("result", {}).get("figures") or figures or []
    )
    # 1 merged table expected in reflow
    rsecs = reflow.get("reflowed_sections") or reflow.get("sections") or []
    merged_tables = 0
    if rsecs:
        # assume first section
        s0 = rsecs[0]
        merged_tables = len(s0.get("tables") or [])

    ok = sec_count == 1 and fig_count == 1 and merged_tables == 1
    print(
        f"Sections: {sec_count} (expect 1), Figures: {fig_count} (expect 1), Merged tables: {merged_tables} (expect 1)"
    )
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_bht_expectations.py <results_dir>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
