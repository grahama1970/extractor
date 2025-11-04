#!/usr/bin/env python3
"""
Stage 07½ — Requirements Miner

Deterministic, offline‑friendly identification of requirement candidates after reflow (Stage 07).

Inputs
- 07_reflowed.json from Stage 07

Outputs
- 07_requirements.json (see docs/tasks/009_requirements_miner_and_workbench.md)
- 07_requirements_summary.json (counts and simple histograms)

Notes
- No LLM required. Optional assists can be added behind env toggles later.
- Keeps the Happy Path single surface; run by run_all between 07 and 08.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
import hashlib
import os

## CLI removed: import and call run(...), or use a debug harness.


MODALITY_RE = re.compile(r"\b(shall|must|should|will|may|might|could|can)\b", re.IGNORECASE)
STRICT_MODAL = {"shall", "must", "will"}
EXCLUDED_MODAL = {"should", "may", "might", "could", "can"}
MIN_LEN = 40  # drop obvious fragments
REQID_RE = re.compile(r"\bREQ[-_][A-Z0-9]+[-_]?\d+\b")
# Conditional detector: default permissive; strict mode via env
_strict = os.getenv("STAGE07REQ_STRICT_CONDITIONAL", "1").lower() in ("1", "true", "yes", "y")
COND_RE = re.compile(
    r"^\s*if\b.*?\b(shall|must|will)\b" if _strict else r"\b(if|when|unless)\b.*?\b(shall|must|will|should)\b",
    re.IGNORECASE | re.DOTALL,
)
INTRO_COLON_RE = re.compile(r"\b(shall|must|should|will)\b[^\n:]*:\s*$", re.IGNORECASE)
FOLLOWING_HINT_RE = re.compile(r"\b(the\s+following|as\s+follows)\b", re.IGNORECASE)


@dataclass
class SourceRef:
    section_id: str | None
    page_num: int | None
    bbox: list[float] | None
    block_ids: list[str]
    section_title: str | None = None
    heading_path: list[str] | None = None
    section_path: str | None = None

def _normalize_req_id(reqid: str | None) -> str | None:
    if not reqid:
        return None
    t = reqid.strip().upper()
    t = t.replace("_", "-")
    return t

def _text_sha1(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def _confidence(text: str, has_id: bool, where: str) -> float:
    score = 0.0
    if MODALITY_RE.search(text):
        score += 0.5
    if has_id:
        score += 0.2
    if where == "paragraph":
        score += 0.2
    elif where == "bullet":
        score += 0.15
    elif where == "table_cell":
        score += 0.1
    score = min(1.0, score)
    return float(score)


def _sentences(text: str) -> list[str]:
    # Simple, robust splitter; avoids over-splitting decimals/IDs
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _mine_from_paragraph(block: dict[str, Any], section_id: str | None, section_title: str | None, heading_path: list[str] | None, section_path: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw = str(block.get("text") or block.get("content") or "").strip()
    if not raw:
        return out
    for sent in _sentences(raw):
        if len(sent.strip()) < MIN_LEN:
            continue
        m = MODALITY_RE.search(sent)
        if not m:
            continue
        modality = m.group(1).lower()
        if modality in EXCLUDED_MODAL:
            continue
        rid = REQID_RE.search(sent)
        cond = COND_RE.search(sent)
        src = SourceRef(
            section_id=section_id,
            page_num=int(block.get("page", block.get("page_idx", 0))) if block.get("page") is not None or block.get("page_idx") is not None else None,
            bbox=(block.get("bbox") if isinstance(block.get("bbox"), list) else None),
            block_ids=[str(block.get("id") or "")],
            section_title=section_title,
            heading_path=heading_path,
            section_path=section_path,
        )
        out.append(
            {
                "from": "paragraph",
                "text_raw": sent,
                "text_canonical": sent,  # editable later in UX
                "modality": modality,
                "condition": cond.group(0) if cond else None,
                "confidence": _confidence(sent, bool(rid), "paragraph"),
                "source": {
                    "section_id": src.section_id,
                    "page_num": src.page_num,
                    "bbox": src.bbox,
                    "block_ids": src.block_ids,
                    "section_title": src.section_title,
                    "heading_path": src.heading_path,
                    "section_path": src.section_path,
                },
                "tags": [],
                "units": [],
                "requirement_id": _normalize_req_id(rid.group(0)) if rid else None,
                "req_id_hint": rid.group(0) if rid else None,
                "text_sha1": _text_sha1(sent),
            }
        )
    return out


def _list_items_from_block(block: dict[str, Any]) -> list[str]:
    items = []
    raw_items = block.get("items") or block.get("list_items") or []
    if isinstance(raw_items, list):
        for it in raw_items:
            if isinstance(it, dict):
                t = (it.get("text") or it.get("content") or "").strip()
                if t:
                    items.append(t)
            elif isinstance(it, str):
                if it.strip():
                    items.append(it.strip())
    return items


def _mine_from_list(
    list_block: dict[str, Any], section_id: str | None, intro_text: str | None, section_title: str | None, heading_path: list[str] | None, section_path: str | None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    items = _list_items_from_block(list_block)
    if not items:
        return out
    intro = (intro_text or "").strip()
    intro_m = MODALITY_RE.search(intro)
    intro_has_modality = bool(intro_m)
    intro_is_colon = bool(INTRO_COLON_RE.search(intro)) or bool(FOLLOWING_HINT_RE.search(intro))
    # Only treat as requirements when an intro with modality leads into the list
    if not (intro and intro_has_modality and intro_is_colon):
        return out
    # Enforce strict modality for list inheritance
    intro_modality = intro_m.group(1).lower() if intro_m else None
    if intro_modality not in STRICT_MODAL:
        return out
    cond = COND_RE.search(intro)
    page_num = int(list_block.get("page", list_block.get("page_idx", 0))) if list_block.get("page") is not None or list_block.get("page_idx") is not None else None
    bbox = list_block.get("bbox") if isinstance(list_block.get("bbox"), list) else None
    in_order = bool(re.search(r"in\s+the\s+order|ordered|sequence", intro, re.IGNORECASE))
    for idx, text in enumerate(items, start=1):
        if not text:
            continue
        if len(text.strip()) < MIN_LEN:
            continue
        rid = REQID_RE.search(text)
        out.append(
            {
                "from": "bullet",
                "text_raw": text,
                "text_canonical": text,
                "modality": intro_modality,  # type: ignore[arg-type]
                "condition": cond.group(0) if cond else None,
                "confidence": _confidence(text, bool(rid), "bullet"),
                "source": {
                    "section_id": section_id,
                    "page_num": page_num,
                    "bbox": bbox,
                    "block_ids": [str(list_block.get("id") or "")],
                    "section_title": section_title,
                    "heading_path": heading_path,
                    "section_path": section_path,
                },
                "tags": ["bullet"],
                "units": [],
                "requirement_id": _normalize_req_id(rid.group(0)) if rid else None,
                "req_id_hint": rid.group(0) if rid else None,
                "text_sha1": _text_sha1(text),
                "sequence": idx,
                "group_intro": intro,
                "in_order": in_order,
            }
        )
    return out


def _mine_from_table(table: dict[str, Any], section_id: str | None, section_title: str | None, heading_path: list[str] | None, section_path: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rows = table.get("pandas_df") or []
    if not isinstance(rows, list):
        return out
    page_num = int(table.get("page_index", table.get("page_number", 0)))
    bbox = table.get("bbox") if isinstance(table.get("bbox"), list) else None
    # rows are list of dicts with string keys; iterate cells
    for r_idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        for c_key, cell in row.items():
            text = str(cell).strip()
            if not text:
                continue
            if len(text.strip()) < MIN_LEN:
                continue
            m = MODALITY_RE.search(text)
            if not m:
                continue
            if m.group(1).lower() in EXCLUDED_MODAL:
                continue
            rid = REQID_RE.search(text)
            cond = COND_RE.search(text)
            out.append(
                {
                    "from": "table_cell",
                    "text_raw": text,
                    "text_canonical": text,
                    "modality": m.group(1).lower(),  # type: ignore[arg-type]
                    "condition": cond.group(0) if cond else None,
                    "confidence": _confidence(text, bool(rid), "table_cell"),
                    "source": {
                        "section_id": section_id,
                        "page_num": page_num,
                        "bbox": bbox,
                        "block_ids": [f"table[r{r_idx},c{c_key}]"],
                        "section_title": section_title,
                        "heading_path": heading_path,
                        "section_path": section_path,
                    },
                    "tags": ["table"],
                    "units": [],
                    "requirement_id": _normalize_req_id(rid.group(0)) if rid else None,
                    "req_id_hint": rid.group(0) if rid else None,
                    "text_sha1": _text_sha1(text),
                }
            )
    return out


def _table_level_requirement(table: dict[str, Any], section_id: str | None, section_title: str | None, heading_path: list[str] | None, section_path: str | None) -> dict[str, Any] | None:
    """Emit a table-level requirement item for every table, regardless of modal verbs.

    Canonical, deterministic text designed to be consumed by Stage 08. We include a compact
    payload (headers + small preview) for downstream context while keeping the main text concise.
    """
    try:
        page_num = int(table.get("page_index", table.get("page_number", 0))) if table.get("page_index") is not None or table.get("page_number") is not None else None
        bbox = table.get("bbox") if isinstance(table.get("bbox"), list) else None
        tid = table.get("id") or table.get("table_id") or table.get("table_index")
        # Headers
        headers = []
        if isinstance(table.get("header"), list) and table.get("header"):
            headers = [str(h) for h in table.get("header")[:12]]
        elif isinstance(table.get("columns"), list) and table.get("columns"):
            headers = [str(h) for h in table.get("columns")[:12]]
        else:
            rows0 = table.get("pandas_df") or table.get("pandas_df_raw") or []
            if isinstance(rows0, list) and rows0:
                r0 = rows0[0]
                if isinstance(r0, dict):
                    headers = [str(k) for k in list(r0.keys())[:12]]
        # Preview
        preview_rows = []
        rows = table.get("pandas_df") or []
        if isinstance(rows, list) and rows:
            for r in rows[:3]:
                if isinstance(r, dict):
                    preview_rows.append({k: str(v) for k, v in list(r.items())[:len(headers) or 8]})
        # Canonical requirement text
        hdr_text = " | ".join(headers) if headers else "(no headers)"
        rid_hint = None
        # If table carries a recognizable requirement id, surface it
        if isinstance(tid, str) and tid:
            rid_hint = f"REQ-TABLE-{tid}"
        req_text = (
            f"All constraints specified by Table {tid if tid is not None else ''} shall hold for the document. "
            f"Columns: {hdr_text}."
        ).strip()
        return {
            "from": "table",
            "text_raw": req_text,
            "text_canonical": req_text,
            "modality": "shall",
            "condition": None,
            "confidence": 0.6,
            "source": {
                "section_id": section_id,
                "page_num": page_num,
                "bbox": bbox,
                "table_id": tid,
                "section_title": section_title,
                "heading_path": heading_path,
                "section_path": section_path,
            },
            "tags": ["table"],
            "units": [],
            "req_id_hint": rid_hint,
            "table_payload": {
                "headers": headers,
                "preview_rows": preview_rows,
            },
        }
    except Exception:
        return None


def _assign_ids(cands: list[dict[str, Any]]) -> None:
    for i, c in enumerate(cands):
        if not c.get("id"):
            c["id"] = f"req_{i:06d}"


def _summarize(cands: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cands)
    by_src = {"paragraph": 0, "table_cell": 0, "bullet": 0}
    modalities: dict[str, int] = {}
    conds = 0
    for c in cands:
        by_src[c.get("from", "paragraph")] = by_src.get(c.get("from", "paragraph"), 0) + 1
        m = str(c.get("modality") or "?")
        modalities[m] = modalities.get(m, 0) + 1
        if c.get("condition"):
            conds += 1
    return {
        "total": total,
        "by_source": by_src,
        "modalities": modalities,
        "with_condition": conds,
    }


def run(
    reflowed_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
):
    out_dir = output_dir / "07_requirements_miner" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(reflowed_json.read_text())
    sections = data.get("reflowed_sections") or []
    candidates: list[dict[str, Any]] = []
    for s in sections:
        sec_id = s.get("id") or s.get("section_id") or None
        sec_title = s.get("title") or s.get("heading") or None
        hp = s.get("heading_path") or s.get("title_path") or None
        if isinstance(hp, str):
            heading_path = [hp]
        elif isinstance(hp, list):
            heading_path = [str(x) for x in hp]
        else:
            heading_path = None
        # Build a single human-readable section path
        if heading_path and len(heading_path) > 0:
            section_path = " > ".join(heading_path)
        elif sec_title:
            section_path = str(sec_title)
        else:
            section_path = None
        prev_para_text: str | None = None
        # Paragraphs/blocks
        for b in s.get("blocks") or []:
            bt = str(b.get("block_type") or b.get("type") or "").lower()
            if bt in {"text", "paragraph", "listitem"}:
                candidates.extend(_mine_from_paragraph(b, sec_id, sec_title, heading_path, section_path))
                prev_para_text = (b.get("text") or b.get("content") or "").strip()
            elif bt in {"list", "bullet_list", "ordered_list"} or b.get("items"):
                candidates.extend(_mine_from_list(b, sec_id, prev_para_text, sec_title, heading_path, section_path))
                prev_para_text = None
        # Tables
        for t in s.get("tables") or []:
            # Cell-level mining (modal cells)
            candidates.extend(_mine_from_table(t, sec_id, sec_title, heading_path, section_path))
            # Table-level requirement (always emit)
            tr = _table_level_requirement(t, sec_id, sec_title, heading_path, section_path)
            if tr:
                candidates.append(tr)

    _assign_ids(candidates)
    req_json = {"requirements": candidates}
    (out_dir / "07_requirements.json").write_text(json.dumps(req_json, indent=2))
    summary = _summarize(candidates)
    (out_dir / "07_requirements_summary.json").write_text(json.dumps(summary, indent=2))
    # Optional: render overlays for requirement provenance
    try:
        if STAGE07REQ_VISUAL_PROOF:
            # Resolve source PDF heuristically from sibling Stage 04 or env
            src_pdf: Optional[Path] = None
            try:
                s04 = (output_dir / "04_section_builder" / "json_output" / "04_sections.json")
                if s04.exists():
                    sp = (json.loads(s04.read_text()) or {}).get("source_pdf")
                    if isinstance(sp, str) and Path(sp).exists():
                        src_pdf = Path(sp)
            except Exception:
                src_pdf = None
            if not src_pdf and STAGE07REQ_SOURCE_PDF:
                p = Path(STAGE07REQ_SOURCE_PDF)
                src_pdf = p if p.exists() else None
            if src_pdf and candidates:
                from extractor.pipeline.visual.overlay import Box, draw_overlays
                vout = output_dir / "07_requirements_miner" / "visual_output"
                boxes: List[Box] = []
                for r in candidates:
                    src = r.get("source") or {}
                    bb = src.get("bbox")
                    pg = src.get("page_num")
                    if isinstance(bb, list) and len(bb) == 4 and isinstance(pg, int):
                        label = (r.get("requirement_id") or r.get("id") or "req").split()[0]
                        boxes.append(
                            Box(
                                page=int(pg),
                                x0=float(bb[0]),
                                y0=float(bb[1]),
                                x1=float(bb[2]),
                                y1=float(bb[3]),
                                label=label,
                                color=(255, 0, 0) if r.get("from") == "paragraph" else ((0, 200, 0) if r.get("from") == "table_cell" else (180, 0, 255)),
                                width=3,
                            )
                        )
                if boxes:
                    draw_overlays(src_pdf, boxes, vout)
    except Exception:
        pass
    print(json.dumps({"ok": True, "total": summary["total"], "out": str(out_dir)}, indent=2))


if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        from extractor.pipeline.steps.sanity_helper import sanity_run
        # Ensure Stage 07 reflow exists (summary_only)
        p = sanity_run("07")
        out_dir = Path("data/results/pipeline")
        run(Path(p), out_dir)
        print(str(out_dir/"07_requirements_miner/json_output/07_requirements.json"))
        sys.exit(0)
    print("Usage: python -m extractor.pipeline.steps.07_requirements_miner sanity")
STAGE07REQ_VISUAL_PROOF = os.getenv("STAGE07REQ_VISUAL_PROOF", "").lower() in ("1","true","yes","y")
STAGE07REQ_SOURCE_PDF = os.getenv("STAGE07REQ_SOURCE_PDF", "").strip() or None
