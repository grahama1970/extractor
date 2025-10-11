#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf>=1.24.9",
#   "typer>=0.12",
# ]
# ///

import typer
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(f"PyMuPDF required: {e}")

app = typer.Typer(add_completion=False)


@app.command()
def draw(
    pdf: Path = typer.Option(..., exists=True, dir_okay=False, help="Input PDF"),
    out: Path = typer.Option(Path("scripts/artifacts/proof_box.pdf"), help="Output PDF"),
    page: int = typer.Option(1, min=1, help="1-based page index"),
    x0: float = typer.Option(72.0, help="Left (pt)"),
    y0: float = typer.Option(72.0, help="Top (pt)"),
    x1: float = typer.Option(300.0, help="Right (pt)"),
    y1: float = typer.Option(220.0, help="Bottom (pt)"),
    color_r: float = typer.Option(0.10, help="R 0..1"),
    color_g: float = typer.Option(0.60, help="G 0..1"),
    color_b: float = typer.Option(0.95, help="B 0..1"),
):
    """Draw a visible rectangle (vector overlay + annotation) on the PDF."""
    doc = fitz.open(pdf.as_posix())
    pno = max(0, min(len(doc) - 1, page - 1))
    pg = doc[pno]
    rect = fitz.Rect(x0, y0, x1, y1) & pg.rect
    if rect.is_empty:
        raise SystemExit("Rect outside page bounds")

    color = (float(color_r), float(color_g), float(color_b))

    # Vector overlay (flattened), with light fill so it's obvious
    try:
        sh = pg.new_shape()
        sh.draw_rect(rect)
        sh.finish(color=color, fill=color, closePath=True, width=1.2, fill_opacity=0.08, stroke_opacity=1.0)
        sh.commit()
    except Exception:
        pg.draw_rect(rect, color=color, width=1.2, fill=color)

    # Real annotation object as well (so Comments pane shows something)
    try:
        a = pg.add_rect_annot(rect)
        a.set_colors(stroke=color, fill=None)
        a.set_border(width=1.2)
        flag_val = getattr(fitz, "ANNOT_FLAG_PRINT", None) or getattr(fitz, "PDF_ANNOT_PRINT", None)
        if flag_val is not None:
            a.set_flags(flag_val)
        a.update()
        # Label note near the box
        pt = fitz.Point(rect.x1 - 8, max(rect.y0 + 8, 8))
        n = pg.add_text_annot(pt, "demo-box")
        if flag_val is not None:
            n.set_flags(flag_val)
        n.update()
    except Exception:
        pass

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out.as_posix(), garbage=4, deflate=True)
    # Export a PNG preview of the page with the box
    try:
        pm = pg.get_pixmap(dpi=144)
        Path(out.parent / "proof_box_page.png").write_bytes(pm.tobytes("png"))
    except Exception:
        pass
    print(out)


if __name__ == "__main__":
    app()

