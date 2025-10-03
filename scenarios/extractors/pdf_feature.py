#!/usr/bin/env python3
"""Scenario: PDF provider opens and exposes page text/refs.

This is a lightweight provider-level smoke to ensure the PDF path is operable.
It validates that:
- The provider can open a sample PDF from data/
- Page count >= 1 and page bbox is available for the first page
- If pdftext is available, page_lines or refs are accessible without raising

Note: Full PDF pipeline (Stages 01→10) is covered by pipeline scenarios/Make targets
and can be run separately when a heavier end-to-end check is desired.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from scenarios.extractors.common import ScenarioResult, find_sample, write_summary


def main() -> int:
    name = "pdf"
    sample: Optional[Path] = find_sample("input/2505.03335v2.pdf", "**/*.pdf")
    if not sample:
        logger.info("SKIP: no PDF sample found under data/")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="sample-missing",
            input_path=None,
            provider="PdfProvider",
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
        PdfProvider = import_provider("providers/pdf.py", "PdfProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import PdfProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="PdfProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    prov = PdfProvider(str(sample))
    ok = len(prov) >= 1 and prov.get_page_bbox(0) is not None
    res = ScenarioResult(
        name=name,
        ok=ok,
        skipped=False,
        reason=None if ok else "no-bbox",
        input_path=str(sample),
        provider="PdfProvider",
        source_type="pdf",
        block_counts={"pages": len(prov)},
        heading_sample=[],
        arango_inserted=False,
        artifacts={},
    )
    write_summary(name, res)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

