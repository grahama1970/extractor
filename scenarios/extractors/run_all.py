#!/usr/bin/env python3
"""Run all extractor feature scenarios and summarise results.

This script executes each scenario module in-process so the PATH/PYTHONPATH
setup in common.py applies uniformly.
"""
from __future__ import annotations

import importlib
from typing import List, Tuple

SCENARIOS = [
    "scenarios.extractors.markdown_feature",
    "scenarios.extractors.html_feature",
    "scenarios.extractors.docx_feature",
    "scenarios.extractors.epub_feature",
    "scenarios.extractors.rst_feature",
    "scenarios.extractors.xml_feature",
    "scenarios.extractors.spreadsheet_feature",
    "scenarios.extractors.pptx_feature",
    "scenarios.extractors.image_feature",
    "scenarios.extractors.pdf_feature",
    "scenarios.extractors.cross_format_similarity",
]


def main() -> int:
    results: List[Tuple[str, int]] = []
    for mod_name in SCENARIOS:
        try:
            mod = importlib.import_module(mod_name)
            code = int(mod.main())  # type: ignore[attr-defined]
            results.append((mod_name, code))
        except SystemExit as e:
            results.append((mod_name, int(e.code)))
        except Exception as e:
            print(f"[ERROR] {mod_name}: {e}")
            results.append((mod_name, 1))

    fails = sum(1 for _, c in results if c != 0)
    for name, code in results:
        status = "PASS" if code == 0 else "FAIL"
        print(f"{status:>4}  {name}")
    print(f"\nSummary: {len(results)-fails} passed, {fails} failed")
    return 0 if fails == 0 else fails


if __name__ == "__main__":
    raise SystemExit(main())
