#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Scenario: Direct check of Stage 10 flattening function (no pytest).

Loads the step module, calls `flatten_document_to_pdf_objects` with a
minimal input, and prints OK/FAIL. Exits non-zero on failure.
"""
from __future__ import annotations

import importlib.util
import sys


def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "stage10", "src/extractor/pipeline/steps/10_arangodb_exporter.py"
    )
    if not spec or not spec.loader:
        print("Scenario pipeline/check_stage10_flattened: FAIL (spec)")
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    fn = getattr(mod, "flatten_document_to_pdf_objects", None)
    if not callable(fn):
        print("Scenario pipeline/check_stage10_flattened: FAIL (no function)")
        sys.exit(1)

    pipeline_data = {
        "reflowed_sections": [
            {
                "id": "s1",
                "title": "Intro",
                "level": 1,
                "page_start": 0,
                "bbox": [0, 0, 100, 50],
                "reflow_status": "success",
                "reflowed_text": "Hello world",
                "tables": [
                    {
                        "title": "INFERRED: T1",
                        "headers": ["A"],
                        "page_index": 0,
                        "bbox": [0, 60, 200, 120],
                    }
                ],
                "figures": [
                    {"title": "F1", "ai_description": "desc", "page": 0, "bbox": [0, 130, 100, 200]}
                ],
            }
        ]
    }
    summaries = {
        "summaries": [
            {
                "section_id": "s1",
                "success": True,
                "summary_data": {"summary": "hi", "key_concepts": []},
            }
        ]
    }
    objs = fn(pipeline_data, summaries)
    ok = (
        isinstance(objs, list)
        and len(objs) >= 3
        and any(o.get("object_type") == "Text" for o in objs)
        and any(o.get("object_type") == "Table" for o in objs)
        and any(o.get("object_type") == "Figure" for o in objs)
        and all("object_index_in_doc" in o for o in objs)
    )
    if not ok:
        print("Scenario pipeline/check_stage10_flattened: FAIL")
        sys.exit(1)
    print("Scenario pipeline/check_stage10_flattened: OK")


if __name__ == "__main__":
    main()
