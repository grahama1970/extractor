#!/usr/bin/env python3
"""Scenario: EPUB → UnifiedDocument → optional Arango insert.

Searches for any *.epub under data/.
Skips gracefully when ebooklib/bs4 are not installed or no sample exists.
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
    name = "epub"
    sample: Optional[Path] = find_sample("**/*.epub")
    if not sample:
        # Synthesize a minimal EPUB if none present
        try:
            from ebooklib import epub  # type: ignore
            tmp = Path(tempfile.gettempdir()) / "scenario_sample.epub"
            book = epub.EpubBook()
            book.set_title("Scenario Sample")
            book.add_author("Extractor")
            c1 = epub.EpubHtml(title="Intro", file_name="intro.xhtml", lang="en")
            c1.content = "<h1>Intro</h1><p>Hello EPUB</p>"
            book.add_item(c1)
            book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
            book.spine = ["nav", c1]
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            epub.write_epub(str(tmp), book)
            sample = tmp
        except Exception as e:
            logger.info(f"SKIP: cannot synthesize EPUB sample: {e}")
            res = ScenarioResult(
                name=name,
                ok=True,
                skipped=True,
                reason="sample-missing",
                input_path=None,
                provider="EPUBProvider",
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
        EPUBProvider = import_provider("providers/epub.py", "EPUBProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import EPUBProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="EPUBProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    try:
        doc = EPUBProvider().extract_document(sample)
    except Exception as e:
        logger.error(f"EPUB extraction failed: {e}")
        res = ScenarioResult(
            name=name,
            ok=False,
            skipped=False,
            reason=str(e),
            input_path=str(sample),
            provider="EPUBProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 1

    has_headings = any(str(getattr(b, "type", "")).split(".")[-1] == "HEADING" for b in doc.blocks)
    hierarchy_ok = (doc.hierarchy is not None) if has_headings else True
    counts, heads = summarise_unified(doc)
    try:
        from scenarios.extractors.common import write_unified_snapshot
        snap_path = write_unified_snapshot("epub", doc.id, doc.model_dump(by_alias=True, mode="json"))
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
        provider="EPUBProvider",
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
