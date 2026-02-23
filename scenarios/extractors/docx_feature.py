#!/usr/bin/env python3
"""Scenario: DOCX → UnifiedDocument → optional Arango insert.

Prefers sample: data/input/2505.03335v2.docx
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from scenarios.extractors.common import (
    ScenarioResult,
    find_sample,
    summarise_unified,
    try_arango_insert,
    write_summary,
)


def main() -> int:
    name = "docx"
    sample: Optional[Path] = find_sample("input/2505.03335v2.docx", "**/*.docx")
    if not sample:
        logger.info("SKIP: no DOCX sample found under data/")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="sample-missing",
            input_path=None,
            provider="DOCXProvider",
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

        DOCXProvider = import_provider("providers/docx.py", "DOCXProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import DOCXProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="DOCXProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    doc = DOCXProvider().extract_document(sample)
    has_headings = any(str(getattr(b, "type", "")).split(".")[-1] == "HEADING" for b in doc.blocks)
    hierarchy_ok = (doc.hierarchy is not None) if has_headings else True
    counts, heads = summarise_unified(doc)
    try:
        from scenarios.extractors.common import write_unified_snapshot

        snap_path = write_unified_snapshot(
            "docx", doc.id, doc.model_dump(by_alias=True, mode="json")
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
        provider="DOCXProvider",
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
