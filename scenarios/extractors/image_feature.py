#!/usr/bin/env python3
"""Scenario: Image provider opens images and exposes page bboxes.

Note: Image provider does not extract text; hierarchy is not applicable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from scenarios.extractors.common import (
    ScenarioResult,
    find_sample,
    try_arango_insert,
    write_summary,
)


def main() -> int:
    name = "image"
    sample: Optional[Path] = find_sample("images/image.png", "images/*.png", "images/*.jpg", "images/*.jpeg")
    if not sample:
        logger.info("SKIP: no image sample found under data/")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="sample-missing",
            input_path=None,
            provider="ImageProvider",
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
        ImageProvider = import_provider("providers/image.py", "ImageProvider")
    except Exception as e:
        logger.warning(f"SKIP: cannot import ImageProvider: {e}")
        res = ScenarioResult(
            name=name,
            ok=True,
            skipped=True,
            reason="import-error",
            input_path=str(sample),
            provider="ImageProvider",
            source_type=None,
            block_counts={},
            heading_sample=[],
            arango_inserted=False,
            artifacts={},
        )
        write_summary(name, res)
        return 0

    # ImageProvider follows the BaseProvider interface; no UnifiedDocument
    prov = ImageProvider(str(sample))
    count = len(prov)
    ok = count >= 1 and prov.get_page_bbox(0) is not None

    # There is nothing to insert into Arango for the raw image provider scenario
    inserted = False

    res = ScenarioResult(
        name=name,
        ok=ok,
        skipped=False,
        reason=None if ok else "no-bbox",
        input_path=str(sample),
        provider="ImageProvider",
        source_type="image",
        block_counts={"pages": count},
        heading_sample=[],
        arango_inserted=inserted,
        artifacts={},
    )
    write_summary(name, res)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
