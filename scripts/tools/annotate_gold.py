#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf>=1.24.9",
# ]
# ///

import json
from pathlib import Path
import typer

try:
    import fitz  # type: ignore
except Exception as e:
    raise SystemExit(f"PyMuPDF required: {e}")

app = typer.Typer(add_completion=False)


def camelot_to_fitz(bbox, page_rect: "fitz.Rect"):
    """Transform Camelot bbox to Fitz.Rect, intersecting with page."""
    try:
        x0, y0, x1, y1 = [float(v) for v in bbox]
        H = float(page_rect.height)
        r = fitz.Rect(x0, H - y1, x1, H - y0) & page_rect
        return None if r.is_empty else r
    except Exception:
        return None


@app.command()
def run(
    pdf: Path = typer.Option(..., exists=True),
    run_dir: Path = typer.Option(..., exists=True),
    out: Path = typer.Option(Path("scripts/artifacts/annotated_gold.pdf")),
):
    """Generate an annotated PDF from processing pipeline outputs."""
    p02 = run_dir / "02_marker_extractor/json_output/02_marker_blocks.json"
    p04 = run_dir / "04_section_builder/json_output/04_sections.json"
    p05 = run_dir / "05_table_extractor/json_output/05_tables.json"
    p06 = run_dir / "06_figure_extractor/json_output/06_figures.json"

    def load(p: Path):
        try:
            return json.loads(p.read_text()) if p.exists() else {}
        except Exception:
            return {}

    j02, j04, j05, j06 = map(load, (p02, p04, p05, p06))

    doc = fitz.open(pdf.as_posix())

    COL = {
        "section": (0.95, 0.45, 0.10),
        "table": (0.10, 0.60, 0.95),
        "figure": (0.10, 0.80, 0.40),
        "text": (0.45, 0.45, 0.45),
    }

    def add(pg: "fitz.Page", rect: "fitz.Rect", label: str, key: str):
        # Stroke-only square + sticky note for maximum compatibility
        sq = pg.add_rect_annot(rect)
        try:
            sq.set_colors(stroke=COL.get(key, (0.2, 0.2, 0.2)))
            sq.set_border(width=1.0)
            sq.update()
        except Exception:
            pass
        try:
            pt = fitz.Point(rect.x1 - 8, max(rect.y0 + 8, 8))
            na = pg.add_text_annot(pt, label)
            na.set_icon("Comment")
            na.set_border(width=0.0)
            na.update()
        except Exception:
            pass

    # Sections
    for s in j04.get("sections", []):
        a = s.get("anchor") or {}
        bb = a.get("bbox")
        pno = a.get("page_idx")
        if bb and isinstance(pno, int) and 0 <= pno < len(doc):
            add(doc[pno], fitz.Rect(*bb), "section", "section")

    # Tables (Camelot → fitz), with sanity filtering
    for t in j05.get("tables", []):
        bb = t.get("bbox")
        try:
            pno = int(t.get("page_number", 1)) - 1
        except Exception:
            pno = 0
        if not (bb and 0 <= pno < len(doc)):
            continue
        rect = camelot_to_fitz(bb, doc[pno].rect)
        if rect is None:
            continue
        # Skip absurdly large or tiny boxes
        page_rect = doc[pno].rect
        pa = page_rect.width * page_rect.height
        ra = rect.width * rect.height
        if (pa and (ra / pa > 0.9)) or rect.width < 12 or rect.height < 12:
            continue
        add(doc[pno], rect, "table", "table")

    # Figures
    for f in j06.get("figures", []):
        bb = f.get("bbox")
        try:
            pno = int(f.get("page_number", 1)) - 1
        except Exception:
            pno = 0
        if not (bb and 0 <= pno < len(doc)):
            continue
        add(doc[pno], fitz.Rect(*bb), "figure", "figure")

    # Text Groups (Stage 02)
    for b in j02.get("blocks", []):
        bt = str(b.get("block_type") or b.get("type") or "").lower()
        if not (("textgroup" in bt) or ("text group" in bt) or bt == "text"):
            continue
        pno = b.get("page") if "page" in b else b.get("page_idx")
        try:
            pno = int(pno)
        except Exception:
            continue
        bb = b.get("bbox") or b.get("rect")
        if not (bb and isinstance(pno, int) and 0 <= pno < len(doc)):
            continue
        rect = fitz.Rect(*bb) & doc[pno].rect
        if rect.is_empty:
            continue
        if rect.get_area() / doc[pno].rect.get_area() > 0.85:
            continue
        add(doc[pno], rect, "text", "text")

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out.as_posix(), garbage=4, deflate=True)
    print(out)


if __name__ == "__main__":
    app()
