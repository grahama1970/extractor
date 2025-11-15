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
from pathlib import Path
from typing import Any, Dict, List, Tuple

from loguru import logger

from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.section_builder_utils import canonical_block_order_key

STEP_NAME = "04a_layout_audit"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read JSON from %s", path)
    return {}


def _add_check(
    checks: List[Dict[str, Any]],
    *,
    section_title: str,
    ok: bool,
    reason: str | None = None,
    **meta: Any,
) -> None:
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
    except Exception:
        # Best‑effort logging; do not fail audit on print issues.
        pass


def run(results_root: Path | str = Path("data/results/pipeline")) -> Path:
    root = Path(results_root)
    stage_dir = root / STEP_NAME
    json_dir = stage_dir / "json_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    audit_path = json_dir / "04a_layout_audit.json"

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
                    i for i, (cur, want) in enumerate(zip(current_indices, sorted_indices)) if cur != want
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
    summary_payload = {
        "step": STEP_NAME,
        "ok": errors == 0,
        "errors": errors,
        "results_root": str(root),
        "sections_checked": sum(1 for c in checks if c.get("section_title") != "__GLOBAL__"),
        "checks": checks,
    }

    audit_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%s: errors=%s", STEP_NAME, errors)
    try:
        print(json.dumps(summary_payload, ensure_ascii=False))
    except Exception:
        pass

    if errors > 0:
        raise RuntimeError(f"{STEP_NAME}: {errors} layout ordering errors (see {audit_path})")
    return audit_path


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        raise SystemExit(sanity())
    print("Usage: python -m extractor.pipeline.steps.04a_layout_audit sanity", file=sys.stderr)
    raise SystemExit(2)
