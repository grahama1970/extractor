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
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer


app = typer.Typer(add_completion=False, help="Identify requirement candidates after Stage 07.")


MODALITY_RE = re.compile(r"\b(shall|must|should|will)\b", re.IGNORECASE)
REQID_RE = re.compile(r"\bREQ[-_][A-Z0-9]+[-_]?\d+\b")
COND_RE = re.compile(r"\b(if|when|unless)\b.*?\b(shall|must|will|should)\b", re.IGNORECASE | re.DOTALL)


@dataclass
class SourceRef:
    section_id: Optional[str]
    page_num: Optional[int]
    bbox: Optional[List[float]]
    block_ids: List[str]


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


def _sentences(text: str) -> List[str]:
    # Simple, robust splitter; avoids over-splitting decimals/IDs
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _mine_from_paragraph(block: Dict[str, Any], section_id: Optional[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    raw = str(block.get("text") or block.get("content") or "").strip()
    if not raw:
        return out
    for sent in _sentences(raw):
        if not MODALITY_RE.search(sent):
            continue
        rid = REQID_RE.search(sent)
        cond = COND_RE.search(sent)
        src = SourceRef(
            section_id=section_id,
            page_num=int(block.get("page", block.get("page_idx", 0))) if block.get("page") is not None or block.get("page_idx") is not None else None,
            bbox=(block.get("bbox") if isinstance(block.get("bbox"), list) else None),
            block_ids=[str(block.get("id") or "")],
        )
        out.append(
            {
                "from": "paragraph",
                "text_raw": sent,
                "text_canonical": sent,  # editable later in UX
                "modality": MODALITY_RE.search(sent).group(1).lower(),  # type: ignore[arg-type]
                "condition": cond.group(0) if cond else None,
                "confidence": _confidence(sent, bool(rid), "paragraph"),
                "source": {
                    "section_id": src.section_id,
                    "page_num": src.page_num,
                    "bbox": src.bbox,
                    "block_ids": src.block_ids,
                },
                "tags": [],
                "units": [],
                "req_id_hint": rid.group(0) if rid else None,
            }
        )
    return out


def _mine_from_table(table: Dict[str, Any], section_id: Optional[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
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
            if not MODALITY_RE.search(text):
                continue
            rid = REQID_RE.search(text)
            cond = COND_RE.search(text)
            out.append(
                {
                    "from": "table_cell",
                    "text_raw": text,
                    "text_canonical": text,
                    "modality": MODALITY_RE.search(text).group(1).lower(),  # type: ignore[arg-type]
                    "condition": cond.group(0) if cond else None,
                    "confidence": _confidence(text, bool(rid), "table_cell"),
                    "source": {
                        "section_id": section_id,
                        "page_num": page_num,
                        "bbox": bbox,
                        "block_ids": [f"table[r{r_idx},c{c_key}]"],
                    },
                    "tags": ["table"],
                    "units": [],
                    "req_id_hint": rid.group(0) if rid else None,
                }
            )
    return out


def _assign_ids(cands: List[Dict[str, Any]]) -> None:
    for i, c in enumerate(cands):
        if not c.get("id"):
            c["id"] = f"req_{i:06d}"


def _summarize(cands: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(cands)
    by_src = {"paragraph": 0, "table_cell": 0, "bullet": 0}
    modalities: Dict[str, int] = {}
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


@app.command()
def run(
    reflowed_json: Path = typer.Argument(..., exists=True, readable=True, help="Path to 07_reflowed.json"),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o", help="Results root directory"),
):
    out_dir = output_dir / "07_requirements_miner" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(reflowed_json.read_text())
    sections = data.get("reflowed_sections") or []
    candidates: List[Dict[str, Any]] = []
    for s in sections:
        sec_id = s.get("id") or s.get("section_id") or None
        # Paragraphs/blocks
        for b in s.get("blocks") or []:
            if str(b.get("block_type") or b.get("type") or "").lower() in {"text", "paragraph", "listitem"}:
                candidates.extend(_mine_from_paragraph(b, sec_id))
        # Tables
        for t in s.get("tables") or []:
            candidates.extend(_mine_from_table(t, sec_id))

    _assign_ids(candidates)
    req_json = {"requirements": candidates}
    (out_dir / "07_requirements.json").write_text(json.dumps(req_json, indent=2))
    summary = _summarize(candidates)
    (out_dir / "07_requirements_summary.json").write_text(json.dumps(summary, indent=2))
    typer.echo(json.dumps({"ok": True, "total": summary["total"], "out": str(out_dir)}, indent=2))


if __name__ == "__main__":
    app()

