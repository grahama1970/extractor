#!/usr/bin/env python3
"""
Stage 04a – Section layout audit.

Purpose
-------
Run immediately after Stage 04 (section builder) to assert that section
blocks are in deterministic reading order. This is a structural guardrail:
later stages (layout sketcher, reflow, annotations) must not have to guess
about block order.

Behaviour
---------
* Reads: 04_section_builder/json_output/04_sections.json
* For each section:
  - Verifies that blocks are sorted by (page, y0, x0) according to their
    bbox and page indices.
  - Emits a failing check when the stored order disagrees with this
    canonical sort.
* Writes: 04a_layout_audit/json_output/04a_layout_audit.json

This step is intentionally deterministic and light‑weight: no LLMs, no
vision, only bbox maths.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error

from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.section_builder_utils import canonical_block_order_key

STEP_NAME = "04a_layout_audit"


def _read_json(path: Path) -> Dict[str, Any]:
    """Return JSON data from a file path or an empty dict on failure."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_stage_error("04a_layout_audit", exc, {"context": "04a"})
        raise
    return {}


def _add_check(
    checks: List[Dict[str, Any]],
    *,
    section_title: str,
    ok: bool,
    reason: str | None = None,
    **meta: Any,
) -> None:
    """Add a check result to the list with optional metadata."""
    payload: Dict[str, Any] = {
        "section_title": section_title,
        "ok": bool(ok),
    }
    if reason:
        payload["reason"] = reason
    if meta:
        payload.update(meta)
    checks.append(payload)
    try:
        print(json.dumps({"event": "layout_audit_check", **payload}, ensure_ascii=False))
    except Exception as exc:
        log_stage_error("04a_layout_audit", exc, {"context": "04a"})
        raise
        # Best‑effort logging; do not fail audit on print issues.
        pass


def run(
    results_root: Path | str = Path("data/results/pipeline"),
    preset_config: Optional[Dict[str, Any]] = None,
) -> Path:
    """Create output directories for a pipeline step."""
    root = Path(results_root)
    stage_dir = root / STEP_NAME
    json_dir = stage_dir / "json_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    audit_path = json_dir / "04a_layout_audit.json"
    visual_dir = stage_dir / "visual_output"
    visual_dir.mkdir(parents=True, exist_ok=True)

    sections_path = root / "04_section_builder" / "json_output" / "04_sections.json"
    data = _read_json(sections_path)
    sections = data.get("sections") or []

    checks: List[Dict[str, Any]] = []

    if not isinstance(sections, list) or not sections:
        _add_check(
            checks,
            section_title="__GLOBAL__",
            ok=False,
            reason="no_sections",
            path=str(sections_path),
        )
    else:
        for idx, sec in enumerate(sections):
            title = str(sec.get("title") or f"section_{idx}")
            blocks = sec.get("blocks") or []
            if not isinstance(blocks, list) or not blocks:
                _add_check(
                    checks,
                    section_title=title,
                    ok=True,
                    reason="no_blocks",
                    section_index=idx,
                )
                continue

            # Compute canonical sort order and compare with stored order.
            keys = [canonical_block_order_key(b) for b in blocks]
            sorted_indices = [i for i, _k in sorted(enumerate(keys), key=lambda t: t[1])]
            current_indices = list(range(len(blocks)))
            ok = sorted_indices == current_indices

            meta: Dict[str, Any] = {
                "section_index": idx,
                "block_count": len(blocks),
            }
            if not ok:
                # Report a small sample of out‑of‑order block types for debugging.
                diff_positions = [
                    i
                    for i, (cur, want) in enumerate(zip(current_indices, sorted_indices))
                    if cur != want
                ]
                sample = diff_positions[:5]
                meta.update(
                    {
                        "out_of_order_positions": sample,
                        "first_block_type": blocks[0].get("block_type") or blocks[0].get("type"),
                    }
                )
            _add_check(
                checks,
                section_title=title,
                ok=ok,
                reason=None if ok else "blocks_not_in_canonical_reading_order",
                **meta,
            )

    errors = sum(1 for c in checks if not c["ok"])
    visuals: List[Dict[str, Any]] = []

    summary_payload = {
        "step": STEP_NAME,
        "ok": errors == 0,
        "errors": errors,
        "results_root": str(root),
        "sections_checked": sum(1 for c in checks if c.get("section_title") != "__GLOBAL__"),
        "checks": checks,
        "visuals": visuals,
    }

    # Copy or derive visuals for audited sections (debug tooling expects visuals).
    try:
        source_pdf = data.get("source_pdf")
        doc = None
        if source_pdf:
            try:
                import fitz

                doc = fitz.open(str(source_pdf))
            except Exception:
                doc = None

        for idx, sec in enumerate(sections):
            sid = sec.get("id") or f"section_{idx}"
            out_path = visual_dir / f"{sid}.png"
            src_rel = sec.get("visual_path") or sec.get("image_path")
            src_path = None
            if src_rel:
                cand = Path(str(src_rel))
                if not cand.is_absolute():
                    cand = root / cand
                if cand.exists():
                    src_path = cand
            if src_path:
                if not out_path.exists():
                    shutil.copy2(src_path, out_path)
                visuals.append(
                    {
                        "section_id": sid,
                        "visual_path": str(out_path.relative_to(root)),
                    }
                )
                continue
            if doc is not None:
                try:
                    page_idx = int(sec.get("page_start", 0) or 0)
                    if page_idx < 0 or page_idx >= len(doc):
                        page_idx = 0
                    page = doc[page_idx]
                    bbox = sec.get("bbox") or []
                    if not isinstance(bbox, list) or len(bbox) != 4:
                        bbox = [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1]
                    rect = fitz.Rect(*[float(v) for v in bbox])
                    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
                        rect = fitz.Rect(page.rect)
                    rect = rect & page.rect
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                    pix.save(str(out_path))
                    visuals.append(
                        {
                            "section_id": sid,
                            "visual_path": str(out_path.relative_to(root)),
                        }
                    )
                except Exception:
                    continue
        if doc is not None:
            doc.close()
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {"context": "visual_copy"})

    audit_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("%s: errors=%s", STEP_NAME, errors)
    try:
        print(json.dumps(summary_payload, ensure_ascii=False))
    except Exception as exc:
        log_stage_error("04a_layout_audit", exc, {"context": "04a"})
        raise

    if errors > 0:
        logger.warning(
            "%s: %d layout ordering errors out of %d sections (see %s)",
            STEP_NAME, errors, summary_payload.get("sections_checked", 0), audit_path,
        )
    return audit_path


def sanity() -> int:
    """Run sanity check for the step."""
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 04a: Layout Audit")
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    args = parser.parse_args()

    try:
        run(args.pipeline_dir)
    except Exception as e:
        logger.error(f"S04a execution failed: {e}")
        sys.exit(1)
