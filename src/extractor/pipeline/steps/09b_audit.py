#!/usr/bin/env python3
"""Stage 09b – Milestone audit for stages 01 through 09a."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "09b_audit"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _exists(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 0
    except Exception:
        return False


def _add_check(
    checks: List[Dict[str, Any]],
    *,
    step: str,
    path: Path,
    ok: bool,
    severity: str = "error",
    reason: str | None = None,
    **meta: Any,
) -> None:
    payload: Dict[str, Any] = {
        "step": step,
        "path": str(path),
        "ok": bool(ok),
        "severity": severity,
    }
    if reason:
        payload["reason"] = reason
    if meta:
        payload.update(meta)
    checks.append(payload)
    try:
        print(json.dumps({"event": "audit_check", **payload}, ensure_ascii=False))
    except Exception:
        pass


def _count_list(data: Dict[str, Any], key: str) -> int:
    items = data.get(key)
    if isinstance(items, dict):
        return len(items)
    if isinstance(items, (list, tuple, set)):
        return len(items)
    return 0


def _sum_by_kind(by_kind: Dict[str, Any]) -> int:
    total = 0
    for val in (by_kind or {}).values():
        if isinstance(val, int):
            total += val
    return total


def run(results_root: Path | str = Path("data/results/pipeline")) -> Path:
    root = Path(results_root)
    stage_dir = root / STEP_NAME
    json_dir = stage_dir / "json_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    audit_path = json_dir / "09b_audit.json"

    checks: List[Dict[str, Any]] = []

    def required_json(step: str, rel: str, key: str | None = None, min_items: int = 1) -> None:
        path = root / rel
        data = _read_json(path)
        ok = bool(data) and (min_items <= 0 or (key and _count_list(data, key) >= min_items))
        reason = None
        meta = {}
        if key:
            meta[f"{key}_count"] = _count_list(data, key)
        if not ok:
            reason = "file missing" if not path.exists() else f"{key or 'items'} insufficient"
        _add_check(checks, step=step, path=path, ok=ok, reason=reason, **meta)

    # Required artifacts
    required_json("01_annotation_processor", "01_annotation_processor/json_output/01_annotations.json", "annotations", 1)
    required_json("02_marker_extractor", "02_marker_extractor/json_output/02_marker_blocks.json", "blocks", 1)
    required_json("03_suspicious_headers", "03_suspicious_headers/json_output/03_verified_blocks.json", "blocks", 1)
    required_json("04_section_builder", "04_section_builder/json_output/04_sections.json", "sections", 1)
    required_json("05_table_extractor", "05_table_extractor/json_output/05_tables.json", "tables", 1)
    required_json("06_figure_extractor", "06_figure_extractor/json_output/06_figures.json", "figures", 0)
    required_json("06b_layout_sketcher", "06b_layout_sketcher/json_output/06b_layout_sketch.json", "sections", 1)
    required_json("07_reflow_section", "07_reflow_section/json_output/07_reflowed.json", "reflowed_sections", 1)
    required_json("07_requirements_miner", "07_requirements_miner/json_output/07_requirements.json", "requirements", 1)

    # Stage 09 is optional when summary_only runs
    summaries_path = root / "09_section_summarizer" / "json_output" / "09_summaries.json"
    if summaries_path.exists():
        data = _read_json(summaries_path)
        ok = _count_list(data, "summaries") > 0
        _add_check(
            checks,
            step="09_section_summarizer",
            path=summaries_path,
            ok=ok,
            reason=None if ok else "summaries missing",
            summaries=_count_list(data, "summaries"),
        )
    else:
        _add_check(
            checks,
            step="09_section_summarizer",
            path=summaries_path,
            ok=False,
            severity="warning",
            reason="summary stage skipped or outputs absent",
        )

    # 09a annotations + legend + annotated PDF
    annotations_path = root / "09a_pdf_annotator" / "json_output" / "annotations.json"
    data = _read_json(annotations_path)
    overlays = _count_list(data, "overlays")
    summary = data.get("summary") or {}
    total = summary.get("total_overlays")
    by_kind = summary.get("by_kind") if isinstance(summary.get("by_kind"), dict) else {}
    calc_sum = _sum_by_kind(by_kind) if isinstance(by_kind, dict) else 0
    consistency = overlays > 0 and isinstance(total, int) and total == overlays == calc_sum
    _add_check(
        checks,
        step="09a_pdf_annotator",
        path=annotations_path,
        ok=bool(data) and consistency,
        reason=None if consistency else "overlay counts inconsistent",
        overlays=overlays,
        total_reported=total,
        total_by_kind=calc_sum,
    )

    legend_path = root / "09a_pdf_annotator" / "json_output" / "legend.json"
    _add_check(
        checks,
        step="09a_pdf_annotator_legend",
        path=legend_path,
        ok=_exists(legend_path),
        reason=None if _exists(legend_path) else "legend missing",
    )

    annotated_pdf = root / "09a_pdf_annotator" / "annotated.pdf"
    _add_check(
        checks,
        step="09a_pdf_annotator_pdf",
        path=annotated_pdf,
        ok=_exists(annotated_pdf),
        reason=None if _exists(annotated_pdf) else "annotated PDF missing",
    )

    errors = sum(1 for c in checks if not c["ok"] and c.get("severity") != "warning")
    warnings = sum(1 for c in checks if not c["ok"] and c.get("severity") == "warning")
    summary_payload = {
        "step": STEP_NAME,
        "ok": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "results_root": str(root),
        "checks": checks,
    }

    audit_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%s: errors=%s warnings=%s", STEP_NAME, errors, warnings)
    try:
        print(json.dumps(summary_payload, ensure_ascii=False))
    except Exception:
        pass
    if errors > 0:
        raise RuntimeError(f"{STEP_NAME}: {errors} blocking audit errors (see {audit_path})")
    return audit_path


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        raise SystemExit(sanity())
    print("Usage: python -m extractor.pipeline.steps.09b_audit sanity", file=sys.stderr)
    raise SystemExit(2)
