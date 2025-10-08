#!/usr/bin/env python3
"""
Compute triage queues (ELS = error-likelihood score) for machine-first, human-selective review.

Reads Stage 05 tables and writes a ranked queue JSON for UI/API consumption.

Inputs (defaults):
  data/results/pipeline/05_table_extractor/json_output/05_tables.json

Outputs:
  data/results/pipeline/triage_queue/tables.json

ELS heuristic for tables (numeric_recall currently omitted unless present in rank_features):
  uncertainty     = 1 - |structure_prob - 0.5| * 2
  frag_norm       = min(fragmentation/8, 1)
  numeric_penalty = max(0, (0.95 - numeric_recall)/0.95) if available else 0
  foreign_penalty = clamp((foreign_numeric_ratio - 0.02)/0.08, 0, 1)
  header_penalty  = 1 if (merge_type == header_body_merge and header_jaccard < 0.5) else 0

  ELS = 0.40*uncertainty + 0.20*frag_norm + 0.20*numeric_penalty 
        + 0.10*foreign_penalty + 0.10*header_penalty
"""

from __future__ import annotations
import json, os, hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple

BASE_DIR = Path("data/results/pipeline")
TRIAGE_DIR = BASE_DIR / "triage_queue"
RUN_ID = os.environ.get("RUN_ID")
RUN_DIR = Path("data/runs") / RUN_ID / "triage" if RUN_ID else None


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def compute_doc_id(pdf_path: str) -> str | None:
    try:
        p = Path(pdf_path)
        base = p.stem.lower()
        base_norm = "".join(ch if ch.isalnum() else "_" for ch in base).strip("_")
        raw = p.read_bytes()
        h = hashlib.sha256(raw).hexdigest()[:8]
        return f"{base_norm}__{h}"
    except Exception:
        return None


def compute_table_els(t: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    c = t.get("confidence", {}) or {}
    fusion_feats = (t.get("fusion") or {}).get("rank_features", {}) or {}
    structure_prob = c.get("structure_prob")
    if structure_prob is None:
        structure_prob = 0.5
    uncertainty = 1 - abs(float(structure_prob) - 0.5) * 2
    fragmentation = min(float(c.get("fragmentation", 0) or 0) / 8.0, 1.0)
    numeric_recall = fusion_feats.get("numeric_recall")
    if numeric_recall is None:
        numeric_penalty = 0.0
    else:
        numeric_penalty = max(0.0, (0.95 - float(numeric_recall)) / 0.95)
    foreign_ratio = float(fusion_feats.get("foreign_numeric_ratio", 0.0) or 0.0)
    foreign_penalty = _clamp((foreign_ratio - 0.02) / 0.08, 0.0, 1.0)
    header_jaccard = float(c.get("header_jaccard", 1.0) or 1.0)
    merge_type = (c.get("merge_type") or "").strip()
    header_penalty = 1.0 if (merge_type == "header_body_merge" and header_jaccard < 0.5) else 0.0

    els = (
        0.40 * uncertainty
        + 0.20 * fragmentation
        + 0.20 * numeric_penalty
        + 0.10 * foreign_penalty
        + 0.10 * header_penalty
    )
    els = round(_clamp(els, 0.0, 1.0), 4)
    reasons = {
        "uncertainty": round(uncertainty, 3),
        "fragmentation": round(fragmentation, 3),
        "numeric_penalty": round(numeric_penalty, 3),
        "foreign_penalty": round(foreign_penalty, 3),
        "header_penalty": header_penalty,
    }
    return els, reasons


def _band(els: float) -> str:
    if els >= 0.65:
        return "high"
    if els >= 0.40:
        return "medium"
    if els >= 0.20:
        return "low"
    return "very_low"


def build_tables_queue() -> Dict[str, Any]:
    tables_path = BASE_DIR / "05_table_extractor" / "json_output" / "05_tables.json"
    if not tables_path.exists():
        return {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": []}
    data = json.loads(tables_path.read_text())
    src_pdf = data.get("source_pdf") or ""
    doc_id = os.environ.get("DOC_ID") or (compute_doc_id(src_pdf) if src_pdf else None)
    run_id = os.environ.get("RUN_ID")
    out_items: List[Dict[str, Any]] = []
    for t in data.get("tables", []):
        page_index = int(t.get("page_index", 0) or 0)
        index = int(t.get("table_index", 1) or 1)
        object_id = f"table:p{page_index:03d}:t{index:02d}"
        els, reasons = compute_table_els(t)
        out_items.append(
            {
                "object_id": object_id,
                "els": els,
                "band": _band(els),
                "reasons": reasons,
                "page_index": page_index,
                "doc_source": src_pdf,
                "doc_id": doc_id,
                "run_id": run_id,
            }
        )
    out_items.sort(key=lambda x: (x["els"], x.get("page_index", 0)), reverse=True)
    return {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": out_items}


def compute_section_els(s: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    meta = s.get("metadata") or {}
    conf = meta.get("confidence") or {}
    comps = conf.get("components") or {}
    heading_factor = comps.get("heading_factor")
    heading_penalty = 0.0 if heading_factor is None else 1 - float(heading_factor)
    nrec = comps.get("numeric_recall")
    numeric_penalty = 0.0 if nrec is None else max(0.0, (0.95 - float(nrec)) / 0.95)
    naudit = meta.get("numeric_audit") or {}
    f_ratio = float(naudit.get("foreign_numeric_ratio") or 0.0)
    halluc_penalty = _clamp((f_ratio - 0.02) / 0.08, 0.0, 1.0)
    anomalies = (meta.get("heading_analysis") or {}).get("anomalies") or []
    anomaly_penalty = min(len(anomalies) / 3.0, 1.0)
    els = 0.45 * heading_penalty + 0.25 * numeric_penalty + 0.20 * anomaly_penalty + 0.10 * halluc_penalty
    els = round(_clamp(els, 0.0, 1.0), 4)
    reasons = {
        "heading_penalty": round(heading_penalty, 3),
        "numeric_penalty": round(numeric_penalty, 3),
        "anomaly_penalty": round(anomaly_penalty, 3),
        "hallucination_penalty": round(halluc_penalty, 3),
    }
    return els, reasons


def build_sections_queue() -> Dict[str, Any]:
    sections_path = BASE_DIR / "04_section_builder" / "json_output" / "04_sections.json"
    if not sections_path.exists():
        return {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": []}
    data = json.loads(sections_path.read_text())
    src_pdf = data.get("source_pdf") or ""
    doc_id = os.environ.get("DOC_ID") or (compute_doc_id(src_pdf) if src_pdf else None)
    run_id = os.environ.get("RUN_ID")
    items: List[Dict[str, Any]] = []
    for s in data.get("sections", []):
        els, reasons = compute_section_els(s)
        items.append({
            "object_id": f"section:{s.get('id')}",
            "els": els,
            "band": _band(els),
            "reasons": reasons,
            "level": s.get("level"),
            "doc_source": src_pdf,
            "doc_id": doc_id,
            "run_id": run_id,
        })
    items.sort(key=lambda x: (x["els"], x.get("level", 0)), reverse=True)
    return {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": items}


def compute_figure_els(fig: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    caption = (fig.get("caption") or fig.get("ai_description") or "").strip()
    caption_missing = 1.0 if not caption else 0.0
    els = min(1.0, 0.7 * caption_missing)
    return round(els, 4), {"caption_missing": caption_missing}


def build_figures_queue() -> Dict[str, Any]:
    figures_path = BASE_DIR / "06_figure_extractor" / "json_output" / "06_figures.json"
    if not figures_path.exists():
        return {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": []}
    data = json.loads(figures_path.read_text())
    src_pdf = data.get("source_pdf") or ""
    doc_id = os.environ.get("DOC_ID") or (compute_doc_id(src_pdf) if src_pdf else None)
    run_id = os.environ.get("RUN_ID")
    items: List[Dict[str, Any]] = []
    for f in data.get("figures", []):
        els, reasons = compute_figure_els(f)
        items.append({
            "object_id": f"figure:{f.get('figure_id', f.get('image_path',''))}",
            "els": els,
            "band": _band(els),
            "reasons": reasons,
            "page_index": f.get("page"),
            "doc_source": src_pdf,
            "doc_id": doc_id,
            "run_id": run_id,
        })
    items.sort(key=lambda x: (x["els"], x.get("page_index", 0)), reverse=True)
    return {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": items}


def main() -> int:
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    tables_queue = build_tables_queue()
    sections_queue = build_sections_queue()
    figures_queue = build_figures_queue()
    (TRIAGE_DIR / "tables.json").write_text(json.dumps(tables_queue, indent=2), encoding="utf-8")
    (TRIAGE_DIR / "sections.json").write_text(json.dumps(sections_queue, indent=2), encoding="utf-8")
    (TRIAGE_DIR / "figures.json").write_text(json.dumps(figures_queue, indent=2), encoding="utf-8")
    # Also write run-scoped triage if RUN_ID present
    if RUN_DIR:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        (RUN_DIR / "tables.json").write_text(json.dumps(tables_queue, indent=2), encoding="utf-8")
        (RUN_DIR / "sections.json").write_text(json.dumps(sections_queue, indent=2), encoding="utf-8")
        (RUN_DIR / "figures.json").write_text(json.dumps(figures_queue, indent=2), encoding="utf-8")
    print("Wrote triage queues: tables, sections, figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
