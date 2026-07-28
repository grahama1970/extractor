#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(p: Path) -> Dict[str, Any]:
    """Load JSON data from a file path into a dictionary."""
    return json.loads(p.read_text(encoding="utf-8"))


def derive_from_expected(expected_root: Path) -> Dict[str, Any]:
    """Build a dictionary of derived data from expected root."""
    checks: List[Dict[str, Any]] = []
    out_dir = "data/results/pipeline"  # default; invariants verifier uses this

    # Stage 04: sections and titles
    s04 = expected_root / "04_section_builder/json_output/04_sections.json"
    if s04.exists():
        o4 = load_json(s04)
        sections = o4.get("sections") or []
        checks.append(
            {
                "id": "stage04_sections_eq",
                "path": "04_section_builder/json_output/04_sections.json",
                "json_pointer": "/sections",
                "metric": "len",
                "op": "==",
                "value": len(sections),
                "why": f"Exact section count from expected ({len(sections)})",
            }
        )
        for idx, sec in enumerate(sections):
            title = sec.get("title")
            if isinstance(title, str):
                checks.append(
                    {
                        "id": f"stage04_title_{idx}",
                        "path": "04_section_builder/json_output/04_sections.json",
                        "json_pointer": f"/sections/{idx}/title",
                        "metric": "text",
                        "op": "==",
                        "value": title,
                        "why": f"Ordered section title {idx}",
                    }
                )

    # Stage 05: tables count
    s05 = expected_root / "05_table_extractor/json_output/05_tables.json"
    if s05.exists():
        o5 = load_json(s05)
        tables = o5.get("tables") or []
        checks.append(
            {
                "id": "stage05_tables_eq",
                "path": "05_table_extractor/json_output/05_tables.json",
                "json_pointer": "/tables",
                "metric": "len",
                "op": "==",
                "value": len(tables),
                "why": f"Exact table count from expected ({len(tables)})",
            }
        )

    # Stage 06: figures count
    s06 = expected_root / "06_figure_extractor/json_output/06_figures.json"
    if s06.exists():
        o6 = load_json(s06)
        figs = o6.get("figures") or []
        checks.append(
            {
                "id": "stage06_figures_eq",
                "path": "06_figure_extractor/json_output/06_figures.json",
                "json_pointer": "/figures",
                "metric": "len",
                "op": "==",
                "value": len(figs),
                "why": f"Exact figure count from expected ({len(figs)})",
            }
        )

    return {
        "version": 1,
        "defaults": {"out_dir": out_dir},
        "checks": checks,
    }


def main() -> int:
    """Generate invariants JSON from expected outputs and save to specified path."""
    ap = argparse.ArgumentParser(description="Derive invariants JSON from expected outputs")
    ap.add_argument("expected_root", type=Path, help="Path like data/expected/pipeline/<slug>")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("config/pipeline_invariants.json"),
        help="Output invariants JSON path",
    )
    args = ap.parse_args()

    inv = derive_from_expected(args.expected_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(inv, indent=2, ensure_ascii=False))
    print(f"Wrote invariants to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
