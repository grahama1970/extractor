#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
# ]
# ///

"""
Compute extraction accuracy against Stage‑01 annotations for a set of pipeline outputs.

Method (pseudo‑gold):
- Use Stage‑01 annotations as the reference (when present). Extract type from
  annotation["interpretation"]["inferred_object"]["type"] or annotation["type"].
- Compare with Stage‑02 blocks (02_marker_blocks.json) by page and IoU of bboxes.
- Per type, compute precision/recall/F1; provide macro and micro averages.

Outputs:
- Per‑document JSON: <base>/metrics/accuracy.json
- Summary Markdown: data/results/metrics/accuracy_report.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer


app = typer.Typer(help="Compute accuracy metrics by comparing Stage‑02 blocks to Stage‑01 annotations")


def _iou(a: List[float], b: List[float]) -> float:
    try:
        ax0, ay0, ax1, ay1 = [float(x) for x in a]
        bx0, by0, bx1, by1 = [float(x) for x in b]
    except Exception:
        return 0.0
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    iw = max(0.0, ix1 - ix0)
    ih = max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def _ann_type(a: Dict[str, Any]) -> str:
    t = (((a.get("interpretation") or {}).get("inferred_object") or {}).get("type"))
    t = t or a.get("type") or "region"
    return str(t)


def _blk_type(b: Dict[str, Any]) -> str:
    return str(b.get("block_type") or b.get("type") or "Text")


def _page(obj: Dict[str, Any]) -> Optional[int]:
    if obj.get("page") is not None:
        try:
            return int(obj["page"])  # 0-based
        except Exception:
            pass
    if obj.get("page_idx") is not None:
        try:
            return int(obj["page_idx"])  # 0-based
        except Exception:
            pass
    if obj.get("page_num") is not None:
        try:
            return max(0, int(obj["page_num"]) - 1)
        except Exception:
            pass
    return None


def _bbox(obj: Dict[str, Any]) -> Optional[List[float]]:
    bb = obj.get("bbox") or obj.get("original_rect") or obj.get("expanded_rect")
    if isinstance(bb, (list, tuple)) and len(bb) == 4:
        try:
            return [float(v) for v in bb]
        except Exception:
            return None
    return None


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def precision(self) -> float:
        d = self.tp + self.fp
        return (self.tp / d) if d else 0.0

    def recall(self) -> float:
        d = self.tp + self.fn
        return (self.tp / d) if d else 0.0

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        return (2 * p * r / (p + r)) if (p + r) else 0.0


def _match_precision_recall(
    refs: List[Dict[str, Any]],
    cands: List[Dict[str, Any]],
    iou_thresh: float = 0.5,
) -> PRF:
    prf = PRF()
    used = set()
    for r in refs:
        rp = _page(r)
        rb = _bbox(r)
        if rp is None or rb is None:
            continue
        best = None
        best_iou = 0.0
        for idx, c in enumerate(cands):
            if idx in used:
                continue
            if _page(c) != rp:
                continue
            cb = _bbox(c)
            if cb is None:
                continue
            iou = _iou(rb, cb)
            if iou > best_iou:
                best_iou = iou
                best = idx
        if best is not None and best_iou >= iou_thresh:
            prf.tp += 1
            used.add(best)
        else:
            prf.fn += 1
    # remaining candidates are false positives
    prf.fp = max(0, len(cands) - len(used))
    return prf


def _load_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


@app.command()
def report(
    root: Path = typer.Argument(
        Path("data/results/pipeline_multi"), exists=True, file_okay=False, dir_okay=True
    ),
    iou: float = typer.Option(0.5, help="IoU threshold for a match"),
    out_dir: Path = typer.Option(Path("data/results/metrics"), help="Output directory for summary"),
):
    """Compute accuracy metrics for all documents under <root>.

    Outputs per-doc JSON and a summary markdown.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    md_lines = ["# Extraction Accuracy Report", ""]
    totals: Dict[str, PRF] = {}
    doc_rows: List[str] = []
    for doc_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        s01 = doc_dir / "01_annotation_processor" / "json_output" / "01_annotations.json"
        s02 = doc_dir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
        if not s01.exists() or not s02.exists():
            continue
        ann = _load_json(s01) or {}
        blks = _load_json(s02) or {}
        ann_list = ann.get("annotations") or []
        blk_list = blks.get("blocks") or []

        # group by type
        type_set = set()
        for a in ann_list:
            type_set.add(_ann_type(a))
        for b in blk_list:
            type_set.add(_blk_type(b))
        # normalize a small subset we care about
        interest = {"SectionHeader": "SectionHeader", "Table": "Table", "Figure": "Figure", "ListItem": "ListItem"}

        per_type: Dict[str, PRF] = {}
        for friendly, tname in interest.items():
            refs = [a for a in ann_list if _ann_type(a).lower() == friendly.lower()]
            cands = [b for b in blk_list if _blk_type(b).lower() == friendly.lower()]
            prf = _match_precision_recall(refs, cands, iou_thresh=iou)
            per_type[friendly] = prf
            # accumulate micro totals
            agg = totals.setdefault(friendly, PRF())
            agg.tp += prf.tp
            agg.fp += prf.fp
            agg.fn += prf.fn

        # macro F1 across available types
        macro_f1 = 0.0
        macro_n = 0
        for friendly, prf in per_type.items():
            macro_f1 += prf.f1()
            macro_n += 1
        macro_f1 = (macro_f1 / macro_n) if macro_n else 0.0

        metrics_path = doc_dir / "metrics"
        metrics_path.mkdir(exist_ok=True)
        doc_json = {
            "doc": doc_dir.name,
            "iou_thresh": iou,
            "per_type": {k: {"tp": v.tp, "fp": v.fp, "fn": v.fn, "precision": v.precision(), "recall": v.recall(), "f1": v.f1()} for k, v in per_type.items()},
            "macro_f1": macro_f1,
        }
        (metrics_path / "accuracy.json").write_text(json.dumps(doc_json, indent=2))
        doc_rows.append(f"- {doc_dir.name}: macro_F1={macro_f1:.3f}")

    # summary
    md_lines.extend(doc_rows)
    md_lines.append("")
    md_lines.append("## Totals (micro)")
    for friendly, agg in totals.items():
        md_lines.append(
            f"- {friendly}: P={agg.precision():.3f} R={agg.recall():.3f} F1={agg.f1():.3f} (tp={agg.tp}, fp={agg.fp}, fn={agg.fn})"
        )
    (out_dir / "accuracy_report.md").write_text("\n".join(md_lines))
    typer.secho(f"Wrote summary: {out_dir/'accuracy_report.md'}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()

