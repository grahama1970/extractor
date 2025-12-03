"""
Helpers for Stage 04 (section_builder).
Split out to keep the step file focused on orchestration.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from extractor.pipeline.utils.section_builder_utils import (
    _bucket_color,
    _roman_to_int,
    pdf_analyze_section_numbering as _pdf_analyze_numbering,
)


def normalize_section_number(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().rstrip(".")


def coerce_depth(depth: Any) -> List[int]:
    if isinstance(depth, list):
        normalized: List[int] = []
        for item in depth:
            try:
                normalized.append(int(item))
            except Exception:
                continue
        if normalized:
            return normalized
    return []


def derive_parent_number(sec_num: str) -> Optional[str]:
    trimmed = normalize_section_number(sec_num)
    if not trimmed:
        return None
    parts = [p for p in trimmed.split(".") if p]
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1])


def normalize_breadcrumbs(value: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    nodes: List[Dict[str, Any]] = []
    titles: List[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("label") or "").strip()
                node = {
                    "id": item.get("id"),
                    "title": title,
                    "section_number": normalize_section_number(item.get("section_number")),
                    "level": item.get("level"),
                    "section_hash": item.get("section_hash"),
                }
                nodes.append({k: v for k, v in node.items() if v not in (None, "")})
                if title:
                    titles.append(title)
            else:
                title = str(item).strip()
                if title:
                    nodes.append({"title": title})
                    titles.append(title)
    elif isinstance(value, str):
        parts = [p.strip() for p in value.split(">")]
        for part in parts:
            if part:
                nodes.append({"title": part})
                titles.append(part)
    return nodes, titles


def breadcrumb_label(section: Dict[str, Any], sec_num: str) -> str:
    meta = section.get("metadata") or {}
    display = section.get("display_title") or meta.get("title_display") or ""
    fallback = section.get("title") or ""
    label = str(display or fallback or sec_num or "").strip()
    if sec_num:
        normalized = normalize_section_number(sec_num)
        if label and not label.lower().startswith(normalized.lower()):
            return f"{normalized} {label}".strip()
        return label or normalized
    return label


def analyze_section_numbering(text: str) -> Dict[str, Any]:
    """Analyze section numbering patterns with depth detection."""
    t = (text or "").strip()
    if not t:
        return {
            "has_numbering": False,
            "numbering_type": "none",
            "depth_level": 0,
            "number_confidence": 0.0,
            "number_text": "",
            "title_text": "",
        }
    analysis = _pdf_analyze_numbering(t)
    num_text = analysis.get("number_text") or ""
    if analysis.get("numbering_type") == "roman" and num_text.islower():
        analysis.update(
            has_numbering=False,
            numbering_type="none",
            number_confidence=0.0,
            number_text="",
            depth_level=0,
        )
    analysis.setdefault("title_text", t)
    analysis.setdefault("number_text", "")
    analysis.setdefault("depth_level", 0)
    analysis.setdefault("numbering_type", "none")
    analysis.setdefault("number_confidence", 0.0)
    analysis.setdefault("has_numbering", False)
    return analysis


def derive_section_depth(numbering_analysis: Dict[str, Any]) -> List[int]:
    depth: List[int] = []
    if not numbering_analysis or not numbering_analysis.get("has_numbering"):
        return depth
    ntype = numbering_analysis.get("numbering_type")
    ntext = (numbering_analysis.get("number_text") or "").strip()
    if not ntext:
        return depth
    try:
        if ntype == "decimal":
            ntext = ntext.rstrip(".")
            parts = [p for p in ntext.split(".") if p]
            depth = [int(p) for p in parts]
        elif ntype == "decimal_paren":
            num = re.sub(r"[^0-9]", "", ntext)
            if num:
                depth = [int(num)]
        elif ntype == "alpha_upper":
            ch = re.sub(r"[^A-Za-z]", "", ntext).upper()[:1]
            if ch:
                depth = [ord(ch) - ord("A") + 1]
        elif ntype == "alpha_lower":
            ch = re.sub(r"[^A-Za-z]", "", ntext).lower()[:1]
            if ch:
                depth = [ord(ch) - ord("a") + 1]
        elif ntype == "roman":
            roman = re.sub(r"[^IVXLCDMivxlcdm]", "", ntext)
            if roman:
                depth = [_roman_to_int(roman)]
    except Exception:
        depth = []
    return depth


def extract_section_title(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    na = analyze_section_numbering(text)
    if na.get("has_numbering"):
        title = na.get("title_text") or ""
        return title.strip().lstrip(". ").strip()
    m = re.match(r"^\s*\d+(?:\.\d+)*\.?\s+(.*)$", text)
    if m:
        return m.group(1).strip()
    return text


def clean_section_title(text: str) -> str:
    text_lines = text.split("\n")
    if len(text_lines) > 1 and "<!-- SECTION_BREADCRUMB" in text_lines[-1]:
        return text_lines[0].strip()
    return text.strip()


def detect_header_level(text: str) -> int:
    text = text.strip()
    if text.startswith("# "):
        return 1
    elif text.startswith("## "):
        return 2
    elif text.startswith("### "):
        return 3
    elif text.startswith("#### "):
        return 4
    elif text.startswith("##### "):
        return 5
    elif text.startswith("###### "):
        return 6

    numbering_analysis = analyze_section_numbering(text)
    if numbering_analysis["has_numbering"]:
        return numbering_analysis["depth_level"]

    lower_text = text.lower()
    if any(k in lower_text for k in ["introduction", "abstract", "conclusion", "references", "appendix"]):
        return 1
    if any(k in lower_text for k in ["methodology", "implementation", "results", "discussion"]):
        return 2
    if any(k in lower_text for k in ["interface", "protocol", "algorithm", "structure"]):
        return 3
    return 2


def looks_like_header_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.match(r"^\d+(?:\.\d+){1,}\s+.+", t):
        return True
    if t.endswith("(Simulated)") or t.endswith("(SIMULATED)"):
        return True
    # All-caps multi-word titles (common unnumbered headings)
    alpha = re.sub(r"[^A-Za-z]", "", t)
    if alpha and t.upper() == t and len(alpha) >= 6 and len(t.split()) >= 2:
        return True
    return False


def prepare_section_hierarchy(sections: List[Dict[str, Any]]) -> None:
    """Normalize numbering, derive parents, and attach breadcrumb metadata in-place."""
    id_map = {s.get("id"): s for s in sections if s.get("id")}
    order_map = {s.get("id"): idx for idx, s in enumerate(sections) if s.get("id")}
    number_map: Dict[str, Dict[str, Any]] = {}

    for section in sections:
        meta = section.setdefault("metadata", {})
        sec_num = normalize_section_number(meta.get("section_number") or section.get("section_number"))
        if sec_num:
            meta["section_number"] = sec_num
            section["section_number"] = sec_num
            number_map[sec_num] = section
        depth = coerce_depth(meta.get("section_depth") or section.get("section_depth"))
        if not depth and sec_num and all(part.isdigit() for part in sec_num.split(".")):
            try:
                depth = [int(part) for part in sec_num.split(".") if part]
            except Exception:
                depth = []
        if depth:
            meta["section_depth"] = depth
            section["section_depth"] = depth

    for section in sections:
        sec_num = section.get("section_number") or section.get("metadata", {}).get("section_number")
        parent_candidate = derive_parent_number(sec_num or "") if sec_num else None
        parent_section = number_map.get(parent_candidate) if parent_candidate else None
        if parent_section and parent_section.get("id") != section.get("id"):
            parent_idx = order_map.get(parent_section.get("id"))
            current_idx = order_map.get(section.get("id"))
            if parent_idx is not None and current_idx is not None and parent_idx < current_idx:
                section["parent_id"] = parent_section.get("id")

    for section in sections:
        meta = section.setdefault("metadata", {})
        breadcrumbs_existing = meta.get("breadcrumbs")
        breadcrumb_titles_existing = meta.get("breadcrumb_titles")
        if breadcrumbs_existing and breadcrumb_titles_existing:
            continue
        path: List[Dict[str, Any]] = []
        titles: List[str] = []
        current = section
        visited: set[str] = set()
        while current and current.get("id") not in visited:
            visited.add(current.get("id"))
            cur_meta = current.get("metadata") or {}
            cur_num = cur_meta.get("section_number") or current.get("section_number")
            label = breadcrumb_label(current, cur_num or "")
            entry = {
                "id": current.get("id"),
                "title": label,
                "section_number": cur_num,
                "level": current.get("level"),
                "section_hash": cur_meta.get("section_hash"),
            }
            path.append({k: v for k, v in entry.items() if v not in (None, "")})
            if label:
                titles.append(label)
            parent_id = current.get("parent_id")
            current = id_map.get(parent_id)
        path.reverse()
        titles.reverse()
        if path and not breadcrumbs_existing:
            meta["breadcrumbs"] = path
        if titles and not breadcrumb_titles_existing:
            meta["breadcrumb_titles"] = titles
        if titles:
            for block in section.get("blocks", []):
                if isinstance(block, dict) and not block.get("section_breadcrumbs"):
                    block["section_breadcrumbs"] = titles


def enrich_header_colors(pdf_path: Path, sections: List[Dict[str, Any]]) -> None:
    """Populate first_span_font color for section headers if missing, and mirror to metadata."""
    try:
        import fitz  # type: ignore
    except Exception:
        return
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return
    for s in sections:
        if not s.get("blocks"):
            continue
        hdr = s["blocks"][0]
        fsf_existing = hdr.get("first_span_font") or {}
        if fsf_existing.get("color_hex") or fsf_existing.get("color_bucket"):
            continue
        page_idx = int(hdr.get("page", hdr.get("page_idx", s.get("page_start", 0))))
        if page_idx < 0 or page_idx >= len(doc):
            continue
        bbox = hdr.get("bbox") or s.get("bbox")
        if not bbox:
            continue
        try:
            page = doc[page_idx]
            td = page.get_text("dict")
            hx0, hy0, hx1, hy1 = bbox
            found_rgb = None
            for blk in td.get("blocks", []):
                for line in blk.get("lines", []):
                    for span in line.get("spans", []):
                        sb = span.get("bbox")
                        if not sb:
                            continue
                        sx0, sy0, sx1, sy1 = sb
                        if not (sx1 < hx0 or sx0 > hx1 or sy1 < hy0 or sy0 > hy1):
                            col = span.get("color")
                            if isinstance(col, (list, tuple)) and len(col) >= 3:
                                found_rgb = (float(col[0]), float(col[1]), float(col[2]))
                            elif isinstance(col, (int, float)):
                                v = int(col)
                                found_rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
                            break
                    if found_rgb:
                        break
                if found_rgb:
                    break
            if found_rgb is None:
                continue
            if all(0.0 <= c <= 1.0 for c in found_rgb):
                rgb255 = (int(found_rgb[0] * 255), int(found_rgb[1] * 255), int(found_rgb[2] * 255))
            else:
                rgb255 = tuple(int(c) for c in found_rgb)
            hexv = f"#{rgb255[0]:02x}{rgb255[1]:02x}{rgb255[2]:02x}"
            bucket = _bucket_color(hexv)
            fsf = hdr.setdefault("first_span_font", {})
            fsf["color_rgb"] = list(rgb255)
            fsf["color_hex"] = hexv
            fsf["color_bucket"] = bucket
            s.setdefault("metadata", {})["header_color_hex"] = hexv
            s["metadata"]["header_color_bucket"] = bucket
        except Exception:
            continue
    try:
        doc.close()
    except Exception:
        pass
