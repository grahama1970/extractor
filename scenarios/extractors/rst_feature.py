#!/usr/bin/env python3
"""Scenario: reStructuredText (RST) → UnifiedDocument → optional Arango insert.

Searches for any *.rst under data/; if none, synthesises a tiny RST sample in tmp.
Skips gracefully when docutils or provider dependencies are missing.
"""
from __future__ import annotations

import tempfile
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


def _synth_sample() -> Path:
    content = (
        "Sample RST\n==========\n\nSection A\n---------\n\nParagraph text.\n\nSection B\n---------\n\n- Item 1\n- Item 2\n"
    )
    fp = Path(tempfile.gettempdir()) / "scenario_sample.rst"
    fp.write_text(content, encoding="utf-8")
    return fp


def main() -> int:
    name = "rst"
    sample: Optional[Path] = find_sample("**/*.rst") or _synth_sample()

    try:
        from scenarios.extractors.common import import_provider
        RSTProvider = import_provider("providers/rst.py", "RSTProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import RSTProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="RSTProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    doc = RSTProvider().extract_document(sample)
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
        provider="RSTProvider",
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
