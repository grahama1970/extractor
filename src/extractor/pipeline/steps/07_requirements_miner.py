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
from loguru import logger


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
    debug: bool = typer.Option(False, "--debug", help="Enable verbose logging to a stage log file."),
):
    """Mine requirement candidates from Stage 07 output with robust debug logging.

    Failure points are logged with rich context (section index/id, block summaries, counts)
    to make debugging straightforward when a document deviates from expected schema.
    """
    stage_dir = output_dir / "07_requirements_miner"
    out_dir = stage_dir / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Configure a dedicated log sink
    try:
        logger.remove()
        logger.add(
            str(stage_dir / "stage_07_requirements_miner.log"),
            level="DEBUG" if debug or os.getenv("STAGE07R_DEBUG", "0").lower() in {"1","true","yes","y"} else "INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception:
        pass

    logger.info("07r:start reflowed_json={} output_dir={} debug={}", reflowed_json, output_dir, debug)

    # Load JSON with error capture
    try:
        raw_text = reflowed_json.read_text()
        data = json.loads(raw_text)
    except Exception as e:
        err = {
            "ok": False,
            "error": "read_or_parse_failed",
            "exception": str(e),
            "path": str(reflowed_json),
            "size": reflowed_json.stat().st_size if reflowed_json.exists() else None,
            "head": raw_text[:500] if 'raw_text' in locals() else None,
        }
        (out_dir / "07_requirements_error.json").write_text(json.dumps(err, indent=2))
        logger.exception("07r:failed to read/parse reflowed_json")
        raise typer.Exit(2)

    # Validate top-level structure
    if not isinstance(data, dict):
        (out_dir / "07_requirements_error.json").write_text(json.dumps({"ok": False, "error": "bad_schema", "type": str(type(data))}, indent=2))
        logger.error("07r:bad_schema type={} keys_absent", type(data))
        raise typer.Exit(2)

    sections = data.get("reflowed_sections") or []
    if not isinstance(sections, list):
        (out_dir / "07_requirements_error.json").write_text(json.dumps({"ok": False, "error": "missing_sections", "keys": list(data.keys())}, indent=2))
        logger.error("07r:missing_sections keys={}", list(data.keys()))
        raise typer.Exit(2)

    logger.info("07r:sections count={} keys={}", len(sections), list(data.keys()))
    candidates: List[Dict[str, Any]] = []
    errors = 0
    debug_snap: List[Dict[str, Any]] = []
    for i, s in enumerate(sections):
        try:
            sec_id = s.get("id") or s.get("section_id") or None
            bcount = len(s.get("blocks") or [])
            tcount = len(s.get("tables") or [])
            if (i % 25) == 0:
                logger.debug("07r:section idx={} id={} blocks={} tables={}", i, sec_id, bcount, tcount)
            # Paragraphs/blocks
            for b in s.get("blocks") or []:
                try:
                    btype = str(b.get("block_type") or b.get("type") or "").lower()
                    if btype in {"text", "paragraph", "listitem"}:
                        c = _mine_from_paragraph(b, sec_id)
                        if c:
                            candidates.extend(c)
                except Exception as be:
                    errors += 1
                    logger.warning("07r:block_error idx={} sec_id={} exc={}", i, sec_id, be)
            # Tables
            for t in s.get("tables") or []:
                try:
                    c = _mine_from_table(t, sec_id)
                    if c:
                        candidates.extend(c)
                except Exception as te:
                    errors += 1
                    logger.warning("07r:table_error idx={} sec_id={} exc={}", i, sec_id, te)
            if (i % 50) == 0:
                debug_snap.append({"section_idx": i, "section_id": sec_id, "blocks": bcount, "tables": tcount, "cand_so_far": len(candidates)})
        except Exception as se:
            errors += 1
            logger.exception("07r:section_iter_error idx={} exc={}", i, se)

    _assign_ids(candidates)
    req_json = {"requirements": candidates, "errors_count": errors}
    (out_dir / "07_requirements.json").write_text(json.dumps(req_json, indent=2))
    summary = _summarize(candidates)
    (out_dir / "07_requirements_summary.json").write_text(json.dumps({**summary, "errors_count": errors, "sections": len(sections)}, indent=2))
    if debug_snap:
        (out_dir / "07_requirements_debug.json").write_text(json.dumps({"snap": debug_snap[-10:]}, indent=2))
    typer.echo(json.dumps({"ok": True, "total": summary["total"], "errors": errors, "out": str(out_dir)}, indent=2))


if __name__ == "__main__":
    app()
