#!/usr/bin/env python3
"""Scenario: Spreadsheet (XLSX/ODS) → UnifiedDocument → optional Arango insert.

Searches for any *.xlsx/*.ods under data/.
Skips gracefully when openpyxl/odfpy are not installed or no sample exists.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger
import tempfile

from scenarios.extractors.common import (
    ScenarioResult,
    find_sample,
    summarise_unified,
    try_arango_insert,
    write_summary,
)


def main() -> int:
    name = "spreadsheet"
    sample: Optional[Path] = find_sample("**/*.xlsx", "**/*.ods")
    if not sample:
        # Synthesize a tiny XLSX sheet if none present
        try:
            from openpyxl import Workbook  # type: ignore

            tmp = Path(tempfile.gettempdir()) / "scenario_sample.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            ws.append(["A", "B", "C"])  # header row
            ws.append([1, 2, 3])
            ws.append([4, 5, 6])
            wb.save(str(tmp))
            sample = tmp
        except Exception as e:
            logger.info(f"SKIP: cannot synthesize XLSX sample: {e}")
            res = ScenarioResult(
                name=name,
                ok=True,
                skipped=True,
                reason="sample-missing",
                input_path=None,
                provider="SpreadsheetProvider",
                source_type=None,
                block_counts={},
                heading_sample=[],
                arango_inserted=False,
                artifacts={},
            )
            write_summary(name, res)
            return 0

    try:
        from scenarios.extractors.common import import_provider

        SpreadsheetProvider = import_provider("providers/spreadsheet.py", "SpreadsheetProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import SpreadsheetProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="SpreadsheetProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    doc = SpreadsheetProvider().extract_document(sample)
    # Spreadsheet provider builds a workbook/sheet/table hierarchy
    hierarchy_ok = doc.hierarchy is not None
    counts, heads = summarise_unified(doc)
    try:
        from scenarios.extractors.common import write_unified_snapshot

        snap_path = write_unified_snapshot(
            "spreadsheet", doc.id, doc.model_dump(by_alias=True, mode="json")
        )
    except Exception:
        snap_path = None
    inserted = try_arango_insert(doc)

    ok = hierarchy_ok
    res = ScenarioResult(
        name=name,
        ok=ok,
        skipped=False,
        reason=None if ok else "missing-hierarchy",
        input_path=str(sample),
        provider="SpreadsheetProvider",
        source_type=str(doc.source_type),
        block_counts=counts,
        heading_sample=heads,
        arango_inserted=inserted,
        artifacts={"unified": snap_path} if snap_path else {},
    )
    write_summary(name, res)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
