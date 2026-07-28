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


def expand_rect(rect: "fitz.Rect", page_rect: "fitz.Rect", scale: float) -> "fitz.Rect":
    """Expand a rectangle by scale, clipping to page bounds."""
    cx = (rect.x0 + rect.x1) / 2.0
    cy = (rect.y0 + rect.y1) / 2.0
    w = rect.width * (1.0 + scale)
    h = rect.height * (1.0 + scale)
    r = fitz.Rect(cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0) & page_rect
    return r


@app.command()
def draw(
    pdf: Path = typer.Option(..., exists=True, dir_okay=False, help="Input PDF"),
    out: Path = typer.Option(Path("scripts/artifacts/proof_expand.pdf"), help="Output PDF"),
    page: int = typer.Option(1, min=1, help="1-based page index"),
    x0: float = typer.Option(100.0),
    y0: float = typer.Option(440.0),
    x1: float = typer.Option(540.0),
    y1: float = typer.Option(640.0),
    expand: float = typer.Option(0.20, help="Relative expansion (e.g., 0.2 = +20%)"),
    r: float = typer.Option(0.10, help="box color R 0..1"),
    g: float = typer.Option(0.80, help="box color G 0..1"),
    b: float = typer.Option(0.40, help="box color B 0..1"),
):
    """Draw a specified region on a PDF page and save the output."""
    doc = fitz.open(pdf.as_posix())
    pno = max(0, min(len(doc) - 1, page - 1))
    pg = doc[pno]
    base = fitz.Rect(x0, y0, x1, y1) & pg.rect
    if base.is_empty:
        raise SystemExit("Base rect outside page bounds")
    expanded = expand_rect(base, pg.rect, expand)

    color = (float(r), float(g), float(b))
    # Draw expanded overlay + annotation
    try:
        sh = pg.new_shape()
        sh.draw_rect(expanded)
        sh.finish(
            color=color,
            fill=color,
            closePath=True,
            width=1.2,
            fill_opacity=0.06,
            stroke_opacity=1.0,
        )
        sh.commit()
    except Exception:
        pg.draw_rect(expanded, color=color, width=1.2, fill=color)
    try:
        a = pg.add_rect_annot(expanded)
        a.set_colors(stroke=color, fill=None)
        a.set_border(width=1.2)
        flag = getattr(fitz, "ANNOT_FLAG_PRINT", None) or getattr(fitz, "PDF_ANNOT_PRINT", None)
        if flag is not None:
            a.set_flags(flag)
        a.update()
    except Exception:
        pass

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out.as_posix(), garbage=4, deflate=True)
    # preview
    try:
        pm = pg.get_pixmap(dpi=144)
        Path(out.parent / (out.stem + "_page.png")).write_bytes(pm.tobytes("png"))
    except Exception:
        pass
    print(out)


if __name__ == "__main__":
    app()
