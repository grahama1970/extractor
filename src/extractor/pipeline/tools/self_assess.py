#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
# ]
# ///

"""
Lightweight agent self-assessment for a single PDF’s pipeline artifacts.

Inputs (convention over configuration):
- Base dir (data/results/pipeline_multi/<slug> or data/results/pipeline).
  - 01_annotation_processor/json_output/01_annotations.json
  - 02_marker_extractor/json_output/02_marker_blocks.json
  - 05_table_extractor/verify/index.html (+ per-table subdirs with view.html)

Outputs:
- suspects.json in base dir with structured reasons and helpful links.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer


app = typer.Typer(help="Generate suspects.json by comparing Stage 01/02/05 artifacts")


@dataclass
class Suspect:
    kind: str
    reason: str
    page: Optional[int] = None
    block_id: Optional[int] = None
    table_view: Optional[str] = None
    related: Dict[str, Any] = None  # type: ignore


def _load_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _collect_table_views(verify_dir: Path) -> List[str]:
    if not verify_dir.exists():
        return []
    views = []
    for sub in sorted(verify_dir.glob("table_*")):
        vf = sub / "view.html"
        if vf.exists():
            views.append(str(vf))
    return views


@app.command()
def generate(
    base_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Base results dir for a single PDF (e.g., data/results/pipeline_multi/<slug>)",
    ),
    out: Optional[Path] = typer.Option(None, "--out", help="Explicit output path for suspects.json"),
    verify_dir: Optional[Path] = typer.Option(None, "--verify-dir", help="Optional table verification root (link view.html)"),
):
    s01 = base_dir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    s02 = base_dir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    v05 = base_dir / "05_table_extractor" / "verify"

    ann = _load_json(s01)
    blks = _load_json(s02)
    views = _collect_table_views(v05)

    suspects: List[Suspect] = []
    meta: Dict[str, Any] = {
        "base_dir": str(base_dir),
        "stage01_json": str(s01),
        "stage02_json": str(s02),
        "table_verify_dir": str(v05),
        "table_views": views,
    }

    ann_count = len((ann or {}).get("annotations", [])) if isinstance(ann, dict) else 0
    blocks = (blks or {}).get("blocks", []) if isinstance(blks, dict) else []
    blk_count = len(blocks)
    susp_blocks = [b for b in blocks if isinstance(b, dict) and b.get("is_suspicious")]
    coverage_ratio = round((blk_count / ann_count), 4) if ann_count else 0.0
    suspicious_preview = [
        {
            "page": b.get("page_idx"),
            "block_type": b.get("block_type"),
            "id": b.get("block_id") or b.get("id"),
            "text_snip": (b.get("text") or "")[:120],
        }
        for b in susp_blocks[:12]
    ]

    # High-level counters and simple mismatches
    if blk_count == 0:
        suspects.append(Suspect(kind="stage02_empty", reason="No blocks produced by Stage 02"))
    if ann_count and blk_count and abs(ann_count - blk_count) / max(1, ann_count) > 0.6:
        suspects.append(
            Suspect(
                kind="coverage_gap",
                reason=f"Stage 01 annotations ({ann_count}) differ greatly from Stage 02 blocks ({blk_count})",
                related={"stage01_count": ann_count, "stage02_count": blk_count},
            )
        )

    # Flag suspicious blocks and missing table verification views
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("is_suspicious"):
            suspects.append(
                Suspect(
                    kind="block_suspicious",
                    reason="Block flagged suspicious by Marker",
                    page=b.get("page_idx"),
                    block_id=b.get("block_id"),
                    related={
                        "suspicion_confidence": b.get("suspicion_confidence"),
                        "reasons": b.get("suspicious_reasons"),
                        "block_type": b.get("block_type"),
                    },
                )
            )
        if str(b.get("block_type", "")).lower() == "table" and not views:
            suspects.append(
                Suspect(
                    kind="table_missing_verify",
                    reason="No table verification views are present",
                    page=b.get("page_idx"),
                    block_id=b.get("block_id"),
                )
            )
    # Build table preview pointers
    tables_preview: List[Dict[str, Any]] = []
    try:
        tables_json = (base_dir / "05_table_extractor" / "json_output" / "05_tables.json")
        tdata = _load_json(tables_json) or {}
        for t in (tdata.get("tables") or [])[:12]:
            entry: Dict[str, Any] = {
                "raw_table_id": t.get("raw_table_id"),
                "page": t.get("page_index"),
                "shape": (t.get("pandas_metrics") or {}).get("shape"),
            }
            tid = t.get("raw_table_id")
            vroot = verify_dir or v05
            if tid and vroot and vroot.exists():
                candidate = vroot / str(tid).replace("rawtbl_", "table_") / "view.html"
                if candidate.exists():
                    entry["view_html"] = str(candidate)
            tables_preview.append(entry)
    except Exception:
        pass

    # Write suspects.json
    payload = {
        "meta": meta,
        "counters": {
            "stage01_annotations": ann_count,
            "stage02_blocks": blk_count,
            "stage02_suspicious_blocks": len(susp_blocks),
            "table_views": len(views),
        },
        "coverage_ratio": coverage_ratio,
        "suspicious_preview": suspicious_preview,
        "tables_preview": tables_preview,
        "stage02_empty": blk_count == 0,
        "suspects": [asdict(s) for s in suspects],
    }
    out_path = out or (base_dir / "suspects.json")
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    typer.secho(f"Wrote suspects: {out_path}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()
