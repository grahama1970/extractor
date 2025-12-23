import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Union

import fitz
from loguru import logger

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.visuals.colors import TAB_COLORS
from extractor.pipeline.utils.visuals.geometry import coerce_page

# --- Layout Constants ---
PREVIEW_DPI = 144
MAX_TABS_PER_PAGE = 12
TAB_GUTTER_WIDTH = 48.0
TAB_HEIGHT = 34.0
TAB_GAP = 6.0
LABEL_TEXT_COLOR = (0.1, 0.1, 0.1)
STEP_NAME = "09a_pdf_annotator"


def collect_tabs(sections: List[Dict[str, Any]], overlays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a sorted list of tabs (sections and merged tables) for the gutter."""
    tabs: list[dict[str, Any]] = []
    section_index: dict[str, dict[str, Any]] = {}
    
    for s in sections:
        sid_raw = s.get("id") or s.get("section_id")
        sid = str(sid_raw) if sid_raw is not None else None
        if not sid:
            continue
        base_page = coerce_page(s.get("page_start"), s.get("page_idx"), s.get("page"))
        if base_page is None:
            continue
        metadata = s.get("metadata") or {}
        continued = metadata.get("continued_pages") or []
        pages = {int(base_page)}
        for p in continued:
            pg = coerce_page(p)
            if pg is not None:
                pages.add(int(pg))
        section = section_index.setdefault(
            sid,
            {
                "key": f"SEC::{sid}",
                "label": s.get("title") or s.get("display_title") or sid,
                "kind": "section",
                "pages": set(),
            },
        )
        section["pages"].update(pages)
    for section in section_index.values():
        section["pages"] = sorted(section["pages"])
        section["primary_page"] = section["pages"][0] if section["pages"] else 0
        section["stable_id"] = f"{section['key']}@{section['primary_page'] + 1}" if section["pages"] else section["key"]
        tabs.append(section)

    merged_groups: dict[str, dict[str, Any]] = {}
    for o in overlays:
        if o.get("kind") != "table_merged":
            continue
        key_raw = o.get("logical_table_key") or o.get("group")
        key = str(key_raw) if key_raw is not None else None
        if not key:
            continue
        group = merged_groups.setdefault(
            key,
            {
                "key": f"TBL::{key}",
                "label": o.get("_label") or f"Table {key}",
                "kind": "table",
                "pages": set(),
            },
        )
        group["pages"].add(int(o.get("page", 0)))
        extra = o.get("pages_in_group") or []
        if isinstance(extra, list):
            for p in extra:
                try:
                    pg = int(p) - 1
                except Exception as exc:
                    log_stage_error(STEP_NAME, exc, {'context': 'collect_tabs'})
                    raise
                    pg = coerce_page(p)
                if pg is not None:
                    group["pages"].add(int(pg))
    for group in merged_groups.values():
        group["pages"] = sorted(group["pages"])
        if not group["pages"]:
            continue
        group["primary_page"] = group["pages"][0]
        group["stable_id"] = f"{group['key']}@{group['primary_page'] + 1}"
        tabs.append(group)

    tabs.sort(key=lambda t: (t.get("primary_page", 0), 0 if t.get("kind") == "section" else 1, t.get("label", "")))
    for idx, tab in enumerate(tabs):
        tab["_rank"] = idx
    return tabs


def draw_vertical_tabs(
    doc: fitz.Document,
    tabs: List[Dict[str, Any]],
    *,
    side: str = "right",
    gutter_w: float = TAB_GUTTER_WIDTH,
    tab_h: float = TAB_HEIGHT,
    tab_gap: float = TAB_GAP,
    max_tabs_per_page: int = MAX_TABS_PER_PAGE,
) -> Dict[str, Any]:
    """Draw navigation tabs on the side of each page."""
    summary = {
        "mode": "none",
        "sections": 0,
        "tables": 0,
        "total": 0,
        "pages_overflow_initial": [],
        "pages_overflow": [],
        "downgraded": False,
    }
    if not tabs:
        return summary

    def _build_per_page(candidates: list[dict[str, Any]]) -> defaultdict[int, list[dict[str, Any]]]:
        mapping: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
        for tab in candidates:
            for pg in tab.get("pages", []):
                if 0 <= pg < len(doc):
                    mapping[pg].append(tab)
        return mapping

    per_page_all = _build_per_page(tabs)
    overflow_initial = sorted(pg for pg, lst in per_page_all.items() if len(lst) > max_tabs_per_page)
    use_tabs = tabs
    downgraded = False
    if overflow_initial and any(tab.get("kind") == "table" for tab in tabs):
        use_tabs = [tab for tab in tabs if tab.get("kind") == "section"]
        per_page_all = _build_per_page(use_tabs)
        downgraded = True
        if downgraded:
            logger.info(
                "09a tabs: downgraded to sections_only due to overflow on pages %s",
                overflow_initial,
            )
    per_page = per_page_all
    overflow_after = sorted(pg for pg, lst in per_page.items() if len(lst) > max_tabs_per_page)

    summary.update(
        {
            "mode": "both" if not downgraded and any(tab.get("kind") == "table" for tab in tabs) else ("sections_only" if use_tabs else "none"),
            "sections": sum(1 for tab in use_tabs if tab.get("kind") == "section"),
            "tables": sum(1 for tab in use_tabs if tab.get("kind") == "table"),
            "total": len(use_tabs),
            "pages_overflow_initial": overflow_initial,
            "pages_overflow": overflow_after,
            "downgraded": downgraded,
        }
    )

    for pno, tab_list in per_page.items():
        if not tab_list:
            continue
        page = doc[pno]
        rect = page.rect
        if side == "right":
            gutter = fitz.Rect(rect.x1 - gutter_w, rect.y0, rect.x1, rect.y1)
            offset = rect.x1 - gutter_w
            rotate = 90
        else:
            gutter = fitz.Rect(rect.x0, rect.y0, rect.x0 + gutter_w, rect.y1)
            offset = rect.x0
            rotate = 270
        page.draw_rect(gutter, fill=(0.96, 0.96, 0.96), color=None, width=0)
        ordered = sorted(
            tab_list,
            key=lambda t: (0 if t.get("kind") == "section" else 1, t.get("_rank", 0)),
        )
        display_tabs = ordered[: max_tabs_per_page]
        overflow = len(ordered) > max_tabs_per_page
        if overflow and display_tabs:
            target = ordered[max_tabs_per_page - 1].get("primary_page", pno)
            display_tabs = ordered[: max_tabs_per_page - 1] + [
                {
                    "key": f"MORE::{pno}",
                    "label": "⋯ More",
                    "kind": "more",
                    "pages": [pno],
                    "primary_page": target,
                    "_rank": 10_000,
                }
            ]
        y = 24.0
        for tab in display_tabs:
            tab_rect = fitz.Rect(0, y, gutter_w, y + tab_h)
            tab_rect = tab_rect + (offset, 0, offset, 0)
            y += tab_h + tab_gap
            color = TAB_COLORS.get(tab.get("kind"), (0.85, 0.85, 0.85))
            page.draw_rect(tab_rect, fill=color, color=None, width=0)
            label = tab.get("label") or tab.get("key")
            if pno not in (tab.get("pages") or []):
                text = label
            elif pno != tab.get("primary_page"):
                text = f"{label} (cont.)"
            else:
                text = label
            page.insert_textbox(
                tab_rect,
                text[:64],
                fontsize=9,
                fontname="helv",
                color=LABEL_TEXT_COLOR,
                rotate=rotate,
                align=1,
            )
            try:
                page.insert_link(
                    {
                        "kind": fitz.LINK_GOTO,
                        "from": tab_rect,
                        "page": int(tab.get("primary_page", pno)),
                        "zoom": 0,
                    }
                )
            except Exception as exc:
                log_stage_error(STEP_NAME, exc, {'context': 'draw_vertical_tabs'})
                raise
                continue

    return summary


def emit_overlay_map(stage_dir: Path, overlays: List[Dict[str, Any]], pages_touched: Set[int], dpi: int = PREVIEW_DPI) -> None:
    """Preview generation and JSON mapping."""
    vis_dir = stage_dir / "visual_output"
    vis_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    by_page: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for ov in overlays:
        by_page[int(ov.get("page", 0))].append(ov)
    payload = {"dpi": dpi, "pages": []}
    page_keys = sorted({int(p) for p in pages_touched} | set(by_page.keys()))
    for pg in page_keys:
        overlays_px = []
        for ov in by_page.get(pg, []):
            rb = ov.get("render_bbox") or ov.get("bbox") or [0, 0, 0, 0]
            x0, y0, x1, y1 = rb
            meta = {k: v for k, v in ov.items() if k not in {"bbox", "render_bbox", "page", "kind", "_label"}}
            meta.setdefault("_label", ov.get("_label"))
            overlays_px.append(
                {
                    "id": ov.get("stable_id") or f"ov{ov.get('overlay_id')}",
                    "kind": ov.get("kind"),
                    "label": ov.get("_label"),
                    "meta": meta,
                    "px_rect": [x0 * scale, y0 * scale, x1 * scale, y1 * scale],
                }
            )
        payload["pages"].append(
            {
                "index": pg,
                "image": f"page_{pg+1:04d}.png",
                "overlays": overlays_px,
            }
        )
    (vis_dir / "overlay_map.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    comments_path = vis_dir / "comments.jsonl"
    if not comments_path.exists():
        comments_path.touch()
