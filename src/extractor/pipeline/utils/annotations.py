from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast


def rect_overlap_ratio(block_bbox: List[float], annot_rect: List[float]) -> float:
    try:
        bx0, by0, bx1, by1 = block_bbox
        ax0, ay0, ax1, ay1 = annot_rect
        ix0, iy0 = max(bx0, ax0), max(by0, ay0)
        ix1, iy1 = min(bx1, ax1), min(by1, ay1)
        iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
        inter = iw * ih
        barea = max(0.0, (bx1 - bx0) * (by1 - by0))
        return (inter / barea) if barea > 0 else 0.0
    except Exception:
        return 0.0


def cue_from_annotation(a: Dict[str, Any]) -> Tuple[int, float, str]:
    """Return (polarity, strength, label) where polarity in {-1,0,1}.
    Uses interpretation.human_note/inferred_object and simple keyword rules.
    """
    note = (a.get("human_note") or "").strip()
    interp = a.get("interpretation") or {}
    inferred = interp.get("inferred_object") or {}
    inferred_type = (inferred.get("type") or "").lower() if isinstance(inferred, dict) else ""
    inferred_conf = float(inferred.get("confidence") or 0.0) if isinstance(inferred, dict) else 0.0
    labels = []
    try:
        if isinstance(interp.get("labels"), list):
            labels = [str(x).lower() for x in interp.get("labels")]
    except Exception:
        labels = []

    positive_keywords = ["section header", "sectionheader", "header"]
    negative_keywords = [
        "not a section header", "not header", "not a header", "non header",
        "paragraph", "list item", "caption", "footnote", "code block",
        "table region", "table header only"
    ]

    label = None
    polarity = 0
    strength = 0.0

    ln = note.lower()
    if any(k in ln for k in negative_keywords) or any(any(neg in lab for neg in negative_keywords) for lab in labels):
        polarity = -1
        strength = 0.95
        label = note or "NOT a section header"
    elif any(k in ln for k in positive_keywords) or any(any(pos in lab for pos in positive_keywords) for lab in labels):
        polarity = 1
        strength = 0.85
        label = note or "Section Header"
    else:
        # use inferred type
        if inferred_type == "section_header":
            polarity = 1
            strength = max(0.5, min(1.0, inferred_conf or 0.7))
            label = f"inferred:{inferred_type} ({strength:.2f})"
        elif inferred_type in ("paragraph", "list_item", "caption", "footnote", "code_block", "table_header", "table_region"):
            polarity = -1
            strength = max(0.5, min(1.0, 0.6 + 0.4 * (1 - inferred_conf)))
            label = f"inferred:{inferred_type}"
        else:
            polarity = 0
            strength = 0.0
            label = note or inferred_type or "unknown"
    return polarity, strength, label


def summarize_cues(cues: List[Tuple[int, float, str]]) -> Tuple[str, float]:
    pos = [f"{lbl} ({st:.2f})" for pol, st, lbl in cues if pol > 0]
    neg = [f"{lbl} ({st:.2f})" for pol, st, lbl in cues if pol < 0]
    signal = sum(st for pol, st, _ in cues if pol > 0) - sum(st for pol, st, _ in cues if pol < 0)
    parts = []
    if pos:
        parts.append("Positive: " + "; ".join(pos[:5]))
    if neg:
        parts.append("Negative: " + "; ".join(neg[:5]))
    return ("\n".join(parts) if parts else "None"), signal


def annotation_text_snippet(a: Dict[str, Any], max_chars: int = 140) -> str:
    def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for blk in blocks or []:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    t = (sp.get("text") or "").strip()
                    if t:
                        parts.append(t)
        s = " ".join(parts)
        s = " ".join(s.split())
        return s
    inside = _blocks_to_text(a.get("inside_blocks", []))
    if not inside:
        inside = _blocks_to_text(a.get("above_blocks", [])) or _blocks_to_text(a.get("below_blocks", []))
    return inside[:max_chars] + ("…" if len(inside) > max_chars else "")


def load_relevant_rules() -> Dict[str, Any]:
    try:
        here = Path(__file__).resolve().parents[1] / "steps" / "config" / "relevant_rules.json"
        if here.exists():
            with open(here, "r") as f:
                return cast(Dict[str, Any], json.load(f))
    except Exception:
        pass
    return {"boost_relevant_weight_for_stage": {"03": 1.25}, "auto_reject_thresholds": {"default": 0.85, "relevant_03": 0.75}}

