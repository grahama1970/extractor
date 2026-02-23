#!/usr/bin/env python3
"""Scenario: HTML → UnifiedDocument → optional Arango insert.

Prefers sample: data/input/2505.03335v2.html or *.html under data/
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
    name = "html"
    sample: Optional[Path] = find_sample("input/2505.03335v2.html", "**/*.html", "**/*.htm")
    if not sample:
        logger.info("SKIP: no HTML sample found under data/")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="sample-missing",
            input_path=None,
            provider="HTMLProvider",
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

        HTMLProvider = import_provider("providers/html.py", "HTMLProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import HTMLProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="HTMLProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    doc = HTMLProvider().extract_document(sample)
    has_headings = any(str(getattr(b, "type", "")).split(".")[-1] == "HEADING" for b in doc.blocks)
    hierarchy_ok = (doc.hierarchy is not None) if has_headings else True
    counts, heads = summarise_unified(doc)
    try:
        from scenarios.extractors.common import write_unified_snapshot

        snap_path = write_unified_snapshot(
            "html", doc.id, doc.model_dump(by_alias=True, mode="json")
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
        provider="HTMLProvider",
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
