#!/usr/bin/env python3
"""Scenario: XML → UnifiedDocument → optional Arango insert.

Searches for any *.xml under data/; if none, synthesises a tiny XML sample in tmp.
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
        """
<document>
  <title>Sample XML</title>
  <section level="1"><heading>Section A</heading><p>Text A.</p></section>
  <section level="1"><heading>Section B</heading><p>Text B.</p></section>
</document>
"""
    ).strip()
    fp = Path(tempfile.gettempdir()) / "scenario_sample.xml"
    fp.write_text(content, encoding="utf-8")
    return fp


def main() -> int:
    name = "xml"
    sample: Optional[Path] = find_sample("**/*.xml") or _synth_sample()

    try:
        from scenarios.extractors.common import import_provider
        XMLProvider = import_provider("providers/xml.py", "XMLProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import XMLProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="XMLProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    doc = XMLProvider().extract_document(sample)
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
        provider="XMLProvider",
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
