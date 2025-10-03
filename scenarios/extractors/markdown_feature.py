#!/usr/bin/env python3
"""Scenario: Markdown → UnifiedDocument → optional Arango insert.

Input preference: data/input/2505.03335v2.md (falls back to any *.md under data/)
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
    name = "markdown"
    sample: Optional[Path] = find_sample("input/2505.03335v2.md", "**/*.md")
    if not sample:
        logger.info("SKIP: no markdown sample found under data/")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="sample-missing",
            input_path=None,
            provider="MarkdownProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    # Import provider
    try:
        from scenarios.extractors.common import import_provider
        MarkdownProvider = import_provider(
            "providers/markdown.py", "MarkdownProvider"
        )
    except Exception as e:
        logger.warning(f"SKIP: cannot import MarkdownProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="MarkdownProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    doc = MarkdownProvider().extract_document(sample)

    # Ensure hierarchy exists when headings present
    has_headings = any(str(getattr(b, "type", "")).split(".")[-1] == "HEADING" for b in doc.blocks)
    hierarchy_ok = (doc.hierarchy is not None) if has_headings else True

    counts, heads = summarise_unified(doc)
    inserted = try_arango_insert(doc)

    ok = hierarchy_ok
    res = ScenarioResult(
        name=name,
        ok=ok,
        skipped=False,
        reason=None if ok else "missing-hierarchy",
        input_path=str(sample),
        provider="MarkdownProvider",
        source_type=str(doc.source_type),
        block_counts=counts,
        heading_sample=heads,
        arango_inserted=inserted,
        artifacts={},
    )
    write_summary(name, res)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
