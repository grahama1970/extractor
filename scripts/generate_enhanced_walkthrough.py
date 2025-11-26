
import fitz
import json
import sys
import html
from pathlib import Path
from datetime import date


def _table_rect(table, page_height):
    """Return a fitz.Rect for a Camelot-style bbox (x0,y0,x1,y1 with origin bottom-left)."""
    bbox = table.get("bbox")
    if not bbox:
        return None
    x0, y0, x1, y1 = bbox
    return fitz.Rect(x0, page_height - y1, x1, page_height - y0)


def _figure_rect(fig, page_height):
    """Figures are emitted by stage 06 using PDF coords (bottom-left)."""
    bbox = fig.get("bbox") or fig.get("bbox_pdf")
    if not bbox:
        return None
    x0, y0, x1, y1 = bbox
    return fitz.Rect(x0, page_height - y1, x1, page_height - y0)


def _header_blocks(section, page_idx):
    """Yield header blocks for the given page."""
    for b in section.get("blocks", []):
        if b.get("block_type") == "SectionHeader" and int(b.get("page_idx", -1)) == page_idx:
            yield b


def _find_label_targets(page, labels):
    """Map label -> y_center by scanning existing text blocks on the page."""
    targets = {}
    blocks = page.get_text("blocks")  # list of tuples (x0,y0,x1,y1,text,...)
    for x0, y0, x1, y1, text, *_ in blocks:
        t = text.strip().lstrip("• ")
        for lbl in labels:
            if t.startswith(f"[{lbl}]"):
                targets[lbl] = (y0 + y1) / 2
    return targets



def generate_enhanced_walkthrough(pdf_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    
    # Load Artifacts
    tables_path = Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json")
    figures_path = Path("data/results/pipeline/06_figure_extractor/json_output/06_figures.json")
    sections_path = Path("data/results/pipeline/04_section_builder/json_output/04_sections.json")
    reflowed_path = Path("data/results/pipeline/07_reflow_section/json_output/07_reflowed.json")
    requirements_path = Path("data/results/pipeline/07_requirements_miner/json_output/07_requirements.json")
    
    # Enriched paths (preferred if available)
    tables_enriched = Path("data/results/pipeline/06a_title_caption_enricher/json_output/05_tables.enriched.json")
    figures_enriched = Path("data/results/pipeline/06a_title_caption_enricher/json_output/06_figures.enriched.json")
    layout06b_path = Path("data/results/pipeline/06b_layout_sketcher/json_output/06b_layout_sketch.json")
    
    if tables_enriched.exists():
        tables = json.loads(tables_enriched.read_text()).get("tables", [])
    elif tables_path.exists():
        tables = json.loads(tables_path.read_text()).get("tables", [])
    else:
        tables = []
        
    if figures_enriched.exists():
        figures = json.loads(figures_enriched.read_text()).get("figures", [])
    elif figures_path.exists():
        figures = json.loads(figures_path.read_text()).get("figures", [])
    else:
        figures = []
        
    sections = json.loads(sections_path.read_text()).get("sections", []) if sections_path.exists() else []
    section_ranges = []
    for s in sections:
        ps = s.get("page_start")
        pe = s.get("page_end") if s.get("page_end") is not None else s.get("page_stop")
        if ps is None:
            continue
        section_ranges.append({
            "title": s.get("title") or "(untitled)",
            "page_start": int(ps),
            "page_end": int(pe) if pe is not None else int(ps),
            "level": int(s.get("level", 1)),
        })
    if reflowed_path.exists():
        reflow_sections = json.loads(reflowed_path.read_text()).get("reflowed_sections") or json.loads(reflowed_path.read_text()).get("sections", [])
    else:
        reflow_sections = []
    requirements = json.loads(requirements_path.read_text()).get("requirements", []) if requirements_path.exists() else []

    # Organize by page
    page_map = {} 
    for t in tables:
        pidx = int(t.get("page_index", 0))
        page_map.setdefault(pidx, {}).setdefault("tables", []).append(t)
    table_metrics_by_page = {}
    for t in tables:
        p = int(t.get("page_index", 0))
        pm = t.get("pandas_metrics") or {}
        cm = t.get("camelot_metrics") or {}
        shape = pm.get("shape", [0, 0])
        density = pm.get("data_density")
        acc = cm.get("accuracy") or cm.get("accuracy_score")
        table_metrics_by_page.setdefault(p, []).append(
            {
                "title": t.get("title") or t.get("title_hint") or "(table)",
                "shape": shape,
                "density": density,
                "acc": acc,
            }
        )
    for f in figures:
        pidx = int(f.get("page_index") if f.get("page_index") is not None else f.get("page", 0))
        page_map.setdefault(pidx, {}).setdefault("figures", []).append(f)
    for s in sections:
        # Heuristic: Associate section with its start page for visualization
        pidx = int(s.get("page_start", 0))
        page_map.setdefault(pidx, {}).setdefault("sections", []).append(s)
    for r in requirements:
        # Get page number from source
        src = r.get("source") or {}
        pidx = src.get("page_num")
        if pidx is not None:
            page_map.setdefault(int(pidx), {}).setdefault("requirements", []).append(r)

    md_lines = [
        "# Enhanced Pipeline Walkthrough",
        "",
        f"**Date:** {date.today()}",
        "**Format:** Side-by-side visualization of extracted artifacts.",
        "",
    ]

    layout_sketches = []
    layout06b_pages = {}
    layout06b_groups = {}
    layout06b_table_areas = {}
    if layout06b_path.exists():
        try:
            layout06b = json.loads(layout06b_path.read_text())
            for sec in layout06b.get("sections", {}).values():
                for el in sec.get("elements", []):
                    page_idx = int(el.get("page", 0))
                    kind = el.get("kind", "?")
                    y0 = el.get("grid_bbox", {}).get("y0", 0)
                    col = el.get("column_id")
                    char_count = el.get("char_count")
                    area = el.get("area")
                    summary = el.get("summary") or kind
                    layout06b_pages.setdefault(page_idx, []).append(
                        {"kind": kind, "y0": y0, "summary": summary, "col": col, "char_count": char_count, "area": area}
                    )
                    if kind == "table":
                        layout06b_table_areas.setdefault(page_idx, []).append(area)
            for page_idx, items in layout06b_pages.items():
                items.sort(key=lambda x: x.get("y0", 0))
                # group text by column and proximity (same col, y-gap <=1 grid unit)
                groups = []
                cur = None
                for it in items:
                    if it["kind"] != "text":
                        continue
                    col = it.get("col")
                    y0 = it.get("y0", 0)
                    if cur is None or col != cur.get("col") or abs(y0 - cur.get("last_y0", y0)) > 1:
                        cur = {
                            "col": col,
                            "items": [it],
                            "first": it,
                            "last": it,
                            "last_y0": y0,
                            "char_sum": (it.get("char_count") or 0),
                            "area_sum": (it.get("area") or 0),
                        }
                        groups.append(cur)
                    else:
                        cur["items"].append(it)
                        cur["last"] = it
                        cur["last_y0"] = y0
                        cur["char_sum"] += it.get("char_count") or 0
                        cur["area_sum"] += it.get("area") or 0
                layout06b_groups[page_idx] = groups
        except Exception:
            layout06b_pages = {}
            layout06b_groups = {}
            layout06b_table_areas = {}

    # Process each page
    for pidx in sorted(page_map.keys()):
        if pidx >= len(doc): continue
        page = doc[pidx]
        items = page_map[pidx]
        H = page.rect.height
        
        # -- Draw Annotations on Image --
        t_list = items.get("tables", [])
        f_list = items.get("figures", [])
        s_list = items.get("sections", [])

        ordered_items = []  # (y_top, kind, obj)

        # Tables (Red)
        for i, t in enumerate(t_list):
            rect = _table_rect(t, H)
            if rect:
                label = f"T{i+1}"
                page.draw_rect(rect, color=(1, 0, 0), width=2.5)
                page.insert_text((rect.x0, rect.y0 - 5), label, color=(1, 0, 0), fontsize=12)
                t["_label"] = label
                t["_rect"] = rect
                ordered_items.append((rect.y0, "table", t))

        # Figures (Blue)
        for i, f in enumerate(f_list):
            rect = _figure_rect(f, H)
            if rect:
                label = f"F{i+1}"
                page.draw_rect(rect, color=(0, 0, 1), width=2.5)
                page.insert_text((rect.x0, rect.y0 - 5), label, color=(0, 0, 1), fontsize=12)
                f["_label"] = label
                f["_rect"] = rect
                ordered_items.append((rect.y0, "figure", f))

        # Section Headers (Green)
        header_count = 0
        for s in s_list:
            for b in _header_blocks(s, pidx):
                bbox = b.get("bbox")
                if not bbox:
                    continue
                rect = fitz.Rect(bbox)
                label = f"S{header_count + 1}"
                header_count += 1
                page.draw_rect(rect, color=(0, 0.6, 0), width=2.5)
                page.insert_text((rect.x0, rect.y0 - 5), label, color=(0, 0.6, 0), fontsize=12)
                s.setdefault("_labels", []).append(label)
                s.setdefault("_rects", []).append(rect)
                ordered_items.append((rect.y0, "section", {"label": label, "title": s.get("title"), "rect": rect}))

        ordered_items.sort(key=lambda t: t[0])

        layout_entry = {"page": pidx + 1, "items": []}
        for y_top, kind, obj in ordered_items:
            rect = obj.get("_rect") or obj.get("rect")
            layout_entry["items"].append(
                {
                    "label": obj.get("_label") or obj.get("label") or "?",
                    "kind": kind,
                    "top": round(float(y_top), 1),
                    "height": round(float(rect.height), 1) if rect else None,
                }
            )
        if layout_entry["items"]:
            layout_sketches.append(layout_entry)

        # Save Image
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) # Higher res
        img_filename = f"annotated_p{pidx+1}_enhanced.png"
        img_path = output_dir / img_filename
        pix.save(str(img_path))
        
        # -- Build Data Pane (HTML) --
        data_html = []

        color_map = {"section": "#198754", "figure": "#0d6efd", "table": "#dc3545"}

        if ordered_items:
            order_str = " \u2192 ".join(
                (obj.get("_label") or obj.get("label") or "?") for _, _, obj in ordered_items
            )
            data_html.append(
                f"<div style='font-size:0.9em; color:#666; margin-bottom:8px;'>Order on page: {order_str} (top to bottom)</div>"
            )

            for y_top, kind, obj in ordered_items:
                color = color_map.get(kind, "#555")
                swatch = f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:6px;'></span>"
                if kind == "section":
                    lbl = obj.get("label", "?")
                    title = html.escape(obj.get("title") or "(Untitled section)")
                    data_html.append(f"<div>{swatch}<strong>[{lbl}] {title}</strong></div>")
                    data_html.append("<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>")

                if kind == "figure":
                    lbl = obj.get("_label", "?")
                    caption = html.escape(obj.get("caption") or obj.get("ai_description") or "(No Caption)")
                    bbox = obj.get("bbox") or obj.get("bbox_pdf")
                    data_html.append(f"<div>{swatch}<strong>[{lbl}] Figure</strong></div>")
                    if bbox:
                        data_html.append(
                            f"<div style='font-size:0.85em;color:#555;'>page {pidx+1} • bbox {bbox}</div>"
                        )
                    data_html.append(
                        f"<div style='font-size: 0.9em; font-style: italic; margin-bottom: 8px;'>{caption}</div>"
                    )
                    data_html.append("<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>")

                if kind == "table":
                    lbl = obj.get("_label", "?")
                    title = html.escape(obj.get("title") or obj.get("title_hint") or "(No Title)")
                    pm = obj.get("pandas_metrics") or {}
                    cm = obj.get("camelot_metrics") or {}
                    shape = pm.get("shape", [0, 0])
                    density = pm.get("data_density")
                    cols = pm.get("columns", [])
                    conf = obj.get("confidence")
                    bbox = obj.get("bbox")
                    data_html.append(f"<div>{swatch}<strong>[{lbl}] {title}</strong></div>")
                    if bbox:
                        data_html.append(
                            f"<div style='font-size:0.85em;color:#555;'>page {pidx+1} • bbox {bbox}</div>"
                        )
                    density_val = density if density is not None else 0.0
                    data_html.append(
                        f"<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: {shape[0]}x{shape[1]} | Density: {density_val:.2f}</div>"
                    )
                    if cm:
                        acc = cm.get("accuracy") or cm.get("accuracy_score")
                        if acc is not None:
                            data_html.append(
                                f"<div style='font-size:0.8em;color:#666;'>Camelot acc: {float(acc):.2f}</div>"
                            )
                    if cols:
                        col_str = ", ".join(html.escape(str(c)) for c in cols[:5])
                        if len(cols) > 5:
                            col_str += "..."
                        data_html.append(
                            f"<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: {col_str}</div>"
                        )
                    # Preview row
                    rows = obj.get("pandas_df", [])
                    if rows:
                        first = rows[0]
                        vals = list(first.values()) if isinstance(first, dict) else list(first)
                        val_str = " | ".join(html.escape(str(v)[:20]) for v in vals[:4])
                        data_html.append(
                            f"<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>{val_str}</div>"
                        )
                    if conf is not None and not isinstance(conf, dict):
                        data_html.append(
                            f"<div style='font-size:0.75em;color:#666;'>Confidence: {float(conf):.2f}</div>"
                        )
                    data_html.append("<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>")

        # Requirements on this page (not ordered because bbox absent)
        r_list = items.get("requirements", [])
        if r_list:
            data_html.append("<h4>Requirements</h4>")
            for i, r in enumerate(r_list):
                req_id = r.get("requirement_id") or r.get("id") or f"R{i+1}"
                text = r.get("text_canonical") or r.get("text_raw") or r.get("text") or "(No text)"
                display_text = html.escape(text[:150] + "..." if len(text) > 150 else text)
                modality = r.get("modality") or ""
                confidence = r.get("confidence", 0)
                conf_val = confidence if confidence is not None else 0.0
                bg_color = "#fff9e6" if conf_val > 0.7 else "#f5f5f5"
                data_html.append(
                    f"<div style='background-color: {bg_color}; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>"
                )
                data_html.append(
                    f"<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>{html.escape(req_id)}</div>"
                )
                data_html.append(f"<div style='font-size: 0.85em;'>{display_text}</div>")
                data_html.append(
                    f"<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: {html.escape(modality)} • Confidence: {conf_val:.2f}</div>"
                )
                data_html.append("</div>")

        if not data_html:
            data_html.append("<em>No structured artifacts detected on this page.</em>")

        # -- Assemble HTML Table Row --
        md_lines.append(f"### Page {pidx+1}")
        md_lines.append("<table>")
        md_lines.append("<tr>")
        # Left Column: Image
        md_lines.append(f'<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">')
        md_lines.append(f'<img src="{output_dir}/{img_filename}" width="100%" />')
        md_lines.append("</td>")
        # Right Column: Data
        md_lines.append(f'<td width="40%" style="vertical-align: top; padding: 15px; background-color: #fff;">')
        md_lines.append("\n".join(data_html))
        md_lines.append("</td>")
        md_lines.append("</tr>")
        md_lines.append("</table>")
        md_lines.append("")

    # ---------- Global Sections ----------
    md_lines.append("## Section Hierarchy")
    section_source = reflow_sections or sections
    numbered_sections = []
    if section_source:
        sorted_secs = sorted(section_source, key=lambda s: (s.get("page_start", 0), s.get("level", 1), s.get("title", "")))
        stack = []  # counters per level
        for s in sorted_secs:
            lvl = max(1, int(s.get("level", 1)))
            # adjust stack to current level
            while len(stack) >= lvl:
                stack.pop()
            while len(stack) < lvl:
                stack.append(0)
            stack[-1] += 1
            num = ".".join(str(n) for n in stack)
            pstart = s.get("page_start")
            pend = s.get("page_end") or s.get("page_stop")
            numbered_sections.append({
                "level": lvl,
                "num": num,
                "title": s.get("title") or "(untitled)",
                "page_start": pstart,
                "page_end": pend if pend is not None else pstart,
            })
        for sec in numbered_sections:
            indent = "  " * (sec["level"] - 1)
            page_span = f"pages {sec['page_start']+1}-{sec['page_end']+1}" if sec["page_end"] is not None and sec["page_end"] != sec["page_start"] else f"page {sec['page_start']+1}"
            md_lines.append(f"{indent}- {sec['num']} {sec['title']} ({page_span})")
    else:
        md_lines.append("- No sections available")
    md_lines.append("")

    md_lines.append("## Table Data (full)")
    if tables:
        sorted_tables = sorted(tables, key=lambda t: (int(t.get("page_index", 0)), t.get("bbox", [0,0,0,0])[1]))
        for idx, t in enumerate(sorted_tables, start=1):
            title = t.get("title") or t.get("title_hint") or f"Table {idx}"
            page_idx = int(t.get("page_index", 0)) + 1
            pm = t.get("pandas_metrics") or {}
            cm = t.get("camelot_metrics") or {}
            shape = pm.get("shape", [0, 0])
            density = pm.get("data_density")
            acc = cm.get("accuracy") or cm.get("accuracy_score")
            density_val = density if density is not None else 0.0
            acc_str = f"{float(acc):.2f}" if acc is not None else "n/a"
            md_lines.append(
                f"- (p{page_idx}) {title}: {shape[0]}x{shape[1]}, density={density_val:.2f}, camelot_acc={acc_str}"
            )
    else:
        md_lines.append("- No tables extracted")
    md_lines.append("")

    md_lines.append("## Layout Sketcher (text)")
    if layout06b_pages:
        ranges = numbered_sections if numbered_sections else [{
            "title": "(no section)",
            "page_start": min(layout06b_pages.keys()),
            "page_end": max(layout06b_pages.keys()),
            "num": "1",
            "level": 1,
        }]

        for sec in ranges:
            pages_in_sec = [p for p in sorted(layout06b_pages.keys()) if sec["page_start"] <= p <= sec["page_end"]]
            if not pages_in_sec:
                continue
            span = f"pages {sec['page_start']+1}-{sec['page_end']+1}" if sec["page_end"] is not None and sec["page_end"] != sec["page_start"] else f"page {sec['page_start']+1}"
            indent = "  " * (sec["level"] - 1)
            md_lines.append(f"{indent}- Section {sec['num']}: {sec['title']} ({span})")
            for page_idx in pages_in_sec:
                items = layout06b_pages[page_idx]
                counts = {}
                for it in items:
                    counts[it["kind"]] = counts.get(it["kind"], 0) + 1
                md_lines.append(
                    f"{indent}  - Page {page_idx+1}: text_blocks={counts.get('text',0)}, tables={counts.get('table',0)}, figures={counts.get('figure',0)}"
                )
                # quick table metrics on this page
                for idx, t in enumerate(table_metrics_by_page.get(page_idx, [])[:3]):
                    shape = t.get("shape", [0, 0])
                    density = t.get("density")
                    acc = t.get("acc")
                    areas = layout06b_table_areas.get(page_idx, [])
                    area_val = areas[idx] if idx < len(areas) else None
                    md_lines.append(
                        f"{indent}    - Table: {shape[0]}x{shape[1]}, density={density if density is not None else 0:.2f}, acc={acc if acc is not None else 'n/a'}, area={area_val if area_val is not None else 'n/a'}, title={t.get('title')}"
                    )
            groups = layout06b_groups.get(page_idx, [])
            for g in groups[:3]:
                first = g["first"].get("summary", "")
                last = g["last"].get("summary", "")
                head = first[:60]
                tail = last[-60:] if last else ""
                if head and tail and head != tail:
                    snippet = f"{head} … {tail}"
                else:
                    snippet = head or tail
                md_lines.append(
                    f"{indent}    - Text col {g['col']}: blocks={len(g['items'])}, chars={g['char_sum']}, snippet=\"{snippet}\""
                )
    elif layout_sketches:
        for entry in layout_sketches:
            md_lines.append(f"- Page {entry['page']}")
            for item in entry["items"]:
                md_lines.append(
                    f"  - {item['label']} ({item['kind']}): top={item['top']} h={item['height']}"
                )
    else:
        md_lines.append("- No layout info recorded")

    # Write MD (root-relative) and a self-contained copy inside the output dir
    output_md = output_dir / "walkthrough_fragment.md"
    md_text = "\n".join(md_lines)
    output_md.write_text(md_text)

    local_md = output_dir / "walkthrough_local.md"
    local_md_text = md_text.replace(f"{output_dir}/", "")
    local_md.write_text(local_md_text)
    
    print(f"Enhanced walkthrough fragment generated: {output_md}")
    print(f"Self-contained walkthrough (relative assets): {local_md}")

if __name__ == "__main__":
    pdf = "data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"
    out = "scripts/artifacts/visuals_pipeline"
    generate_enhanced_walkthrough(pdf, out)
