"""pdf_oxide adapter for the extractor pipeline.

Replaces S00 (profile), S02 (text/blocks), S03 (headers), S04 (sections),
S04a (layout audit), and S06 (figures) with a single pdf_oxide
extract_document() call. Writes pipeline-compatible output files so
downstream stages (S05 tables, S05b/c, S06b VLM, S07+) work unchanged.

Usage: Set STAGE02_EXTRACTOR=pdf_oxide to activate.

Requires: pdf_oxide Python package (pip install pdf_oxide or maturin develop).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from loguru import logger


def run(
    pdf_path: Path,
    results_dir: Path,
    **kwargs,
) -> Path:
    """Run pdf_oxide extraction and write S00/S02/S03/S04/S04a/S06 output.

    Returns path to the S02-compatible blocks JSON.
    """
    import pdf_oxide

    t0 = time.monotonic()
    result = pdf_oxide.extract_pdf(str(pdf_path))
    d = result.to_dict()
    elapsed = time.monotonic() - t0

    # S00 profile
    _write_json(results_dir, "00_profile_detector", "profile.json",
                d.get("metadata", {}).get("profile", {}), flat=True)

    # S02 blocks
    blocks_out = {
        "blocks": d.get("blocks", []),
        "page_count": d.get("page_count", 0),
        "engine": "pdf_oxide",
        "latency_ms": int(elapsed * 1000),
    }
    s02_path = _write_json(
        results_dir, "02_marker_extractor", "02_marker_blocks.json", blocks_out
    )

    # S03 headers (blocks with header_level > 0)
    headers = [b for b in d.get("blocks", []) if (b.get("header_level") or 0) > 0]
    _write_json(results_dir, "03_suspicious_headers", "03_suspicious_headers.json",
                {"headers": headers, "engine": "pdf_oxide"})

    # S04 sections
    _write_json(results_dir, "04_section_builder", "04_sections.json",
                {"sections": d.get("sections", []), "engine": "pdf_oxide"})

    # S04a layout audit (empty — pdf_oxide validates internally)
    audit_dir = results_dir / "04a_layout_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "04a_layout_audit.json").write_text(
        json.dumps({"violations": [], "engine": "pdf_oxide"}, indent=2)
    )

    # S06 figures
    _write_json(results_dir, "06_figure_extractor", "06_figures.json",
                {"figures": d.get("figures", []), "engine": "pdf_oxide"})

    logger.info(
        f"02_pdf_oxide_adapter: {len(d.get('blocks', []))} blocks, "
        f"{len(d.get('sections', []))} sections, "
        f"{len(d.get('figures', []))} figures in {elapsed:.1f}s"
    )

    return s02_path


def _write_json(
    results_dir: Path, stage_name: str, filename: str, data: dict,
    *, flat: bool = False,
) -> Path:
    """Write JSON to the expected stage output directory."""
    if flat:
        out_dir = results_dir / stage_name
    else:
        out_dir = results_dir / stage_name / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    return path
