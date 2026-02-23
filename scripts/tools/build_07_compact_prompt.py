#!/usr/bin/env python3
"""
Build a compact, string-only Stage 07 prompt for a single section using
existing pipeline artifacts (04 sections, 06b sketch, 05/06 enriched).

Outputs under scripts/artifacts/:
 - 07_section0_prompt_compact.md (exact prompt string)
 - 07_section0_payload_compact.json (OpenAI-compatible JSON body)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def _read_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _table_merge_candidates(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for t in tables or []:
        key = f"{t.get('logical_table_id') or ''}|{t.get('header_norm') or ''}"
        if key.strip("|"):
            by_key.setdefault(key, []).append(t)
    for key, group in by_key.items():
        if len(group) >= 2:
            ids = [t.get("id") or t.get("table_id") or f"tbl_{i}" for i, t in enumerate(group)]
            out.append({"logical": key, "parts": ids})
    return out


def build_prompt(base: Path, section_idx: int = 0) -> str:
    sec_p = base / "04_section_builder" / "json_output" / "04_sections.json"
    sk_v2_p = base / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json"
    tabs_p = base / "06a_title_caption_enricher" / "json_output" / "05_tables.enriched.json"
    figs_p = base / "06a_title_caption_enricher" / "json_output" / "06_figures.enriched.json"
    sec = _read_json(sec_p)
    skv2 = _read_json(sk_v2_p)
    tabs = _read_json(tabs_p)
    figs = _read_json(figs_p)
    sections = sec.get("sections") or []
    if not sections:
        raise SystemExit("no sections in 04_sections.json")
    try:
        sec_id = str(sections[section_idx]["id"])
    except Exception:
        # fallback to first available key in sketch v2
        sec_id = next(iter((skv2.get("sections") or {}).keys()), "section_0")
    sketch = (skv2.get("sections") or {}).get(sec_id, {})
    # Counts
    all_tabs = tabs.get("tables") or []
    all_figs = figs.get("figures") or []
    tabs_for_sec = [t for t in all_tabs if str(t.get("section_id")) == sec_id]
    figs_for_sec = [f for f in all_figs if str(f.get("section_id")) == sec_id]
    merges = _table_merge_candidates(tabs_for_sec)
    # Top summary (short)
    lines: List[str] = []
    lines.append(
        "You output ONLY a compact JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. No markdown, no code fences."
    )
    lines.append("")
    lines.append(f"Section id: {sec_id}")
    lines.append(f"Tables: {len(tabs_for_sec)} | Figures: {len(figs_for_sec)}")
    if merges:
        for m in merges[:4]:
            lines.append(f"Merge candidate: logical={m['logical']} parts={','.join(m['parts'])}")
    # Minimal sketch insert
    if sketch:
        # emit a minimal JSON slice with objects ids and bbox grid
        objs = sketch.get("objects") or []
        mini = []
        for o in objs[:20]:
            mini.append(
                {
                    "id": o.get("id"),
                    "type": o.get("type"),
                    "page": o.get("page"),
                    "grid_bbox": o.get("grid_bbox"),
                    "header_norm": o.get("header_norm"),
                    "logical_table_id": o.get("logical_table_id"),
                    "summary": o.get("summary"),
                }
            )
        lines.append("")
        lines.append("Sketch (minimal):")
        lines.append(json.dumps(mini, ensure_ascii=False))
    # Minimal inputs: table headers/titles and figure titles
    if tabs_for_sec:
        lines.append("")
        lines.append("Tables heads/titles:")
        for t in tabs_for_sec[:8]:
            hid = t.get("id") or t.get("table_id")
            lines.append(f"- {hid}: header_norm={t.get('header_norm')} title={t.get('title')}")
    if figs_for_sec:
        lines.append("")
        lines.append("Figures titles:")
        for f in figs_for_sec[:6]:
            fid = f.get("id") or f.get("figure_id")
            lines.append(f"- {fid}: title={f.get('title')} caption={f.get('caption')}")
    lines.append("")
    lines.append("Return ONLY the JSON; keep it compact.")
    return "\n".join(lines)


def main() -> None:
    base = Path(os.environ.get("RESULTS_BASE", "data/results/pipeline_xtrace")).resolve()
    section_idx = int(os.environ.get("SECTION_INDEX", "0"))
    prompt = build_prompt(base, section_idx)
    art = Path("scripts/artifacts")
    art.mkdir(parents=True, exist_ok=True)
    (art / "07_section0_prompt_compact.md").write_text(prompt, encoding="utf-8")
    payload = {
        "model": os.environ.get("CHUTES_TEXT_MODEL", ""),
        "messages": [
            {"role": "system", "content": "You output ONLY compact JSON."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1024,
        "temperature": 0,
    }
    (art / "07_section0_payload_compact.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(str((art / "07_section0_prompt_compact.md").resolve()))


if __name__ == "__main__":
    main()
