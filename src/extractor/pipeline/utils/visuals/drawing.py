try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]
from typing import Optional, List, Tuple

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.visuals import formatting as fmt

# --- Drawing Constants ---
GUTTER_PAD = 0.0
PLAQUE_PAD_X = 0.0
PLAQUE_FONT_MIN = 5.5
PLAQUE_FILL = None
PLAQUE_BORDER = None
GUTTER_BORDER = None

LABEL_MARGIN_PTS = 14.0
LABEL_MIN_FONT = 8.0
LABEL_BG = (1.0, 0.98, 0.85)
LABEL_TEXT_COLOR = (0.1, 0.1, 0.1)

TABLE_CALLOUT_BG = (0.98, 0.99, 0.92)
FIGURE_CALLOUT_BG = (0.94, 0.97, 1.0)
STEP_NAME = "09a_pdf_annotator"


def draw_page_gutter_side(page: fitz.Page, side: str = "left") -> fitz.Rect:
    """Return the gutter rect on the requested side (no fill/stroke)."""
    # Note: Logic was empty in original script; preserving signature for future implementation
    return fitz.Rect()


def draw_page_gutter(page: fitz.Page, side: str = "left") -> fitz.Rect:
    """Backward-compatible helper."""
    return draw_page_gutter_side(page, side)


def draw_gutter_tag(
    page: fitz.Page,
    lane: fitz.Rect,
    target: fitz.Rect,
    text: str,
    color: Tuple[float, float, float] = (0.12, 0.12, 0.12),
    font: float = 9.0,
) -> None:
    """Draw a gutter tag with specified text and styling on a page."""
    if not text or lane is None:
        return
    t = text.strip()
    if not t:
        return

    # Calculate text fit
    txt_w = page.get_text_length(t, fontsize=font)
    max_w = max(12.0, lane.width - 2 * GUTTER_PAD)
    font_size = font

    while txt_w > max_w and font_size > PLAQUE_FONT_MIN:
        font_size -= 0.8
        txt_w = page.get_text_length(t, fontsize=font_size)

    if txt_w > max_w:
        while txt_w > max_w and len(t) > 3:
            t = t[:-1]
            txt_w = page.get_text_length(t + "…", fontsize=font_size)
        t = (t + "…") if len(t) > 3 else t

    plaque_h = font_size * 1.7
    cy = target.y0 + target.height / 2.0
    top = max(lane.y0 + GUTTER_PAD, min(cy - plaque_h / 2.0, lane.y1 - GUTTER_PAD - plaque_h))
    left = lane.x0 + GUTTER_PAD
    plaque_w = page.get_text_length(t, fontsize=font_size) + 2 * PLAQUE_PAD_X
    plaque = fitz.Rect(left, top, left + plaque_w, top + plaque_h)

    try:
        # Prefer FreeText annotations
        annot = page.add_freetext_annot(
            plaque, t, fontsize=font_size, text_color=color, fill_color=PLAQUE_FILL
        )
        try:
            annot.set_border(width=0.6)
            annot.set_colors(stroke=PLAQUE_BORDER)
            annot.set_opacity(0.98)
            annot.update()
        except Exception:
            pass
    except Exception:
        # Fallback to direct drawing
        page.draw_rect(plaque, fill=PLAQUE_FILL, color=PLAQUE_BORDER, width=0.6, overlay=True)
        page.insert_text(
            (plaque.x0 + PLAQUE_PAD_X, plaque.y0 + font_size * 1.2 - 1),
            t,
            fontsize=font_size,
            color=color,
            overlay=True,
        )

    # Draw Connector Line
    p_from = fitz.Point(plaque.x1, plaque.y0 + plaque.height / 2.0)
    p_to = fitz.Point(target.x0, min(max(target.y0 + 4, p_from.y), target.y1 - 4))

    try:
        connector = page.add_line_annot(p_from, p_to)
        connector.set_colors(stroke=GUTTER_BORDER)
        connector.set_border(width=0.7)
        connector.update()
    except Exception:
        page.draw_line(p_from, p_to, color=GUTTER_BORDER, width=0.7)


def draw_t_endcaps(
    page: fitz.Page,
    lane: fitz.Rect,
    y0: float,
    y1: float,
    color: Tuple[float, float, float] = (0.25, 0.25, 0.25),
) -> None:
    """Draw T-shaped endcaps for the given lane."""
    if lane is None:
        return
    x = lane.x1 - 10.0
    try:
        vertical = page.add_line_annot(fitz.Point(x, y0), fitz.Point(x, y1))
        vertical.set_colors(stroke=color)
        vertical.set_border(width=1.0)
        vertical.update()

        top_bar = page.add_line_annot(fitz.Point(x - 6, y0), fitz.Point(x + 6, y0))
        top_bar.set_colors(stroke=color)
        top_bar.set_border(width=1.0)
        top_bar.update()

        bottom_bar = page.add_line_annot(fitz.Point(x - 6, y1), fitz.Point(x + 6, y1))
        bottom_bar.set_colors(stroke=color)
        bottom_bar.set_border(width=1.0)
        bottom_bar.update()
    except Exception:
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y1), color=color, width=1.0)
        page.draw_line(fitz.Point(x - 6, y0), fitz.Point(x + 6, y0), color=color, width=1.0)
        page.draw_line(fitz.Point(x - 6, y1), fitz.Point(x + 6, y1), color=color, width=1.0)


def draw_section_title_plaque(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    stroke: Tuple[float, float, float] = (0.86, 0.25, 0.2),
    font: float = 11.0,
) -> None:
    """Draw a section title plaque on the specified PDF page."""
    if not text:
        return
    t = text.strip()
    max_w = min(rect.width * 0.9, 360.0)
    while page.get_text_length(t, fontsize=font) > max_w and len(t) > 5:
        t = t[:-1]
    if t != text:
        t = t.rstrip(" .,;") + "…"

    h = font * 1.8
    top = max(page.rect.y0 + 6, rect.y0 - h - 6)
    left = rect.x0 + 6
    plaque = fitz.Rect(
        left, top, left + page.get_text_length(t, fontsize=font) + 2 * PLAQUE_PAD_X, top + h
    )

    page.draw_rect(plaque, fill=(1, 1, 1), color=stroke, width=0.9, overlay=True)
    page.insert_text(
        (plaque.x0 + PLAQUE_PAD_X, plaque.y0 + font * 1.2 - 1),
        t,
        fontsize=font,
        color=stroke,
        overlay=True,
    )


def draw_figure_watermark(page: fitz.Page, rect: fitz.Rect, text: str) -> None:
    """Draw a watermark with specified text on a PDF page."""
    text = (text or "").strip()
    if not text:
        return
    font = max(10.0, rect.height * 0.06)
    max_width = max(60.0, rect.width - 24.0)

    lines = fmt.wrap_label_lines(page, text, font, max_width, max_lines=6)
    if not lines:
        lines = [text[:80] + ("…" if len(text) > 80 else "")]

    line_height = font * 1.25
    box_height = line_height * len(lines) + 8

    longest_line_len = fitz.get_text_length(max(lines, key=len), fontsize=font) if lines else 0
    box_width = max(longest_line_len + 12, max_width)

    box = fitz.Rect(
        rect.x0 + 12,
        rect.y0 + 12,
        min(rect.x0 + 12 + box_width, rect.x1 - 12),
        min(rect.y0 + 12 + box_height, rect.y1 - 12),
    )

    page.draw_rect(box, fill=(1.0, 1.0, 1.0), color=(0.7, 0.7, 0.7), width=0.6, overlay=True)
    page.insert_textbox(
        box,
        "\n".join(lines),
        fontsize=font,
        color=(0.25, 0.25, 0.25),
        lineheight=1.2,
        align=0,
        overlay=True,
    )


def draw_table_metrics(
    page: fitz.Page,
    rect: fitz.Rect,
    headers_preview: Optional[str],
    camelot_acc: Optional[float],
    pandas_acc: Optional[float],
    color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """Draw table metrics on a PDF page within a specified rectangle."""
    y = rect.y1 - 6
    x = rect.x0 + 8
    font1 = 9.5
    font2 = 9.0

    if headers_preview:
        page.insert_text(
            (x, y - font1), f"Data: {headers_preview}", fontsize=font1, color=color, overlay=True
        )
        y -= font1 + 2

    metrics: List[str] = []
    if camelot_acc is not None:
        try:
            metrics.append(f"camelot={float(camelot_acc):.2f}")
        except Exception:
            pass

    if pandas_acc is not None:
        try:
            metrics.append(f"pandas={float(pandas_acc):.2f}")
        except Exception:
            pass

    page.insert_text(
        (x, y - font2),
        f"Metrics: {', '.join(metrics) if metrics else '—'}",
        fontsize=font2,
        color=color,
        overlay=True,
    )


def draw_table_preview_box(
    page: fitz.Page,
    rect: fitz.Rect,
    lines: List[str],
    color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """Draw a preview box for a table on the specified PDF page."""
    if not lines:
        return
    max_lines = min(len(lines), 6)
    panel_lines = ["Table preview:"] + [ln for ln in lines[:max_lines]]
    font = 8.4
    line_height = font * 1.25
    padding = 6.0

    box_height = line_height * len(panel_lines) + padding * 2
    panel_width = min(320.0, rect.width - 16.0)

    top = rect.y0 - box_height - 6
    if top < page.rect.y0 + 4:
        top = rect.y1 + 6
    if top + box_height > page.rect.y1 - 4:
        top = max(page.rect.y0 + 4, rect.y0 + 6)

    box = fitz.Rect(rect.x0 + 6, top, rect.x0 + 6 + panel_width, top + box_height)

    page.draw_rect(box, fill=TABLE_CALLOUT_BG, color=(0.65, 0.65, 0.65), width=0.6, overlay=True)
    preview_text = "\n".join(panel_lines)
    page.insert_textbox(
        box, preview_text, fontsize=font, color=color, lineheight=1.2, align=0, overlay=True
    )


def draw_figure_caption_box(page: fitz.Page, rect: fitz.Rect, text: str) -> None:
    """Draw a caption box on a page with formatted text."""
    caption = (text or "").strip()
    if not caption:
        return
    font = 9.2
    line_height = font * 1.3
    max_width = min(340.0, rect.width - 12.0)

    lines = fmt.wrap_label_lines(page, caption, font, max_width, max_lines=8)
    if not lines:
        lines = [caption[:120] + ("…" if len(caption) > 120 else "")]

    height = line_height * len(lines) + 10

    # Try placing below figure, flip to above if no room
    box = fitz.Rect(rect.x0 + 6, rect.y1 + 8, rect.x0 + 6 + max_width, rect.y1 + 8 + height)
    if box.y1 > page.rect.y1 - 4:
        box = fitz.Rect(
            rect.x0 + 6,
            max(rect.y0 - height - 8, page.rect.y0 + 6),
            rect.x0 + 6 + max_width,
            max(rect.y0 - 8, page.rect.y0 + 6) + height,
        )

    page.draw_rect(box, fill=FIGURE_CALLOUT_BG, color=(0.5, 0.6, 0.8), width=0.6, overlay=True)
    panel = ["Figure description:"] + lines
    page.insert_textbox(
        box,
        "\n".join(panel),
        fontsize=font,
        color=(0.1, 0.14, 0.2),
        lineheight=1.2,
        align=0,
        overlay=True,
    )


def draw_label(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    color: Tuple[float, float, float],
    font_size: float,
) -> None:
    """Draw a label with specified text and styling on a page."""
    try:
        if not text or not text.strip():
            return

        font = max(float(font_size), LABEL_MIN_FONT)
        line_height = font * 1.2
        y_center = rect.y0 + rect.height / 2.0
        left_space = rect.x0 - page.rect.x0
        right_space = page.rect.x1 - rect.x1

        def _draw_lines(x: float, top: float, width: float, lines: List[str]) -> fitz.Point:
            """Draw multiple lines of text as a freetext annotation."""
            height = line_height * len(lines)
            bg = fitz.Rect(x - 2, top - 2, x + width + 2, top + height + 2)
            text_block = "\n".join(lines)
            try:
                annot = page.add_freetext_annot(
                    bg, text_block, fontsize=font, text_color=LABEL_TEXT_COLOR, fill_color=LABEL_BG
                )
                annot.set_border(width=0.4)
                annot.set_colors(stroke=color)
                annot.set_opacity(0.95)
                annot.update()
            except Exception:
                # Fallback
                page.draw_rect(bg, color=color, width=0.4, fill=LABEL_BG, overlay=False)
                y = top + font
                for ln in lines:
                    page.insert_text(
                        (x, y), ln, fontsize=font, color=LABEL_TEXT_COLOR, overlay=False
                    )
                    y += line_height
            return fitz.Point(bg.x0 + width / 2.0, bg.y0 + height / 2.0)

        # 1. Try left margin
        avail_left = left_space - LABEL_MARGIN_PTS * 2
        if avail_left > font * 3:
            lines = fmt.wrap_label_lines(page, text, font, avail_left)
            if lines:
                width = max(fitz.get_text_length(ln, fontsize=font) for ln in lines)
                if left_space >= width + LABEL_MARGIN_PTS * 2:
                    text_height = line_height * len(lines)
                    top = y_center - text_height / 2.0
                    top = max(page.rect.y0 + 2, min(page.rect.y1 - text_height - 2, top))
                    x = rect.x0 - LABEL_MARGIN_PTS - width
                    center = _draw_lines(x, top, width, lines)
                    end = fitz.Point(rect.x0, max(rect.y0, min(rect.y1, center.y)))
                    page.draw_line(center, end, color=color, width=0.4)
                    return

        # 2. Try right margin
        avail_right = right_space - LABEL_MARGIN_PTS * 2
        if avail_right > font * 3:
            lines = fmt.wrap_label_lines(page, text, font, avail_right)
            if lines:
                width = max(fitz.get_text_length(ln, fontsize=font) for ln in lines)
                if right_space >= width + LABEL_MARGIN_PTS * 2:
                    text_height = line_height * len(lines)
                    top = y_center - text_height / 2.0
                    top = max(page.rect.y0 + 2, min(page.rect.y1 - text_height - 2, top))
                    x = rect.x1 + LABEL_MARGIN_PTS
                    center = _draw_lines(x, top, width, lines)
                    end = fitz.Point(rect.x1, max(rect.y0, min(rect.y1, center.y)))
                    page.draw_line(end, center, color=color, width=0.4)
                    return

        # 3. Fallback: Above or Below
        max_available = min(page.rect.width - LABEL_MARGIN_PTS * 2, max(rect.width, font * 6))
        lines = fmt.wrap_label_lines(page, text, font, max_available)
        if not lines:
            return

        width = max(fitz.get_text_length(ln, fontsize=font) for ln in lines)
        text_height = line_height * len(lines)

        # Try above
        top = rect.y0 - LABEL_MARGIN_PTS - text_height
        if top >= page.rect.y0 + 2:
            x = max(
                page.rect.x0 + LABEL_MARGIN_PTS,
                min(rect.x0, page.rect.x1 - width - LABEL_MARGIN_PTS),
            )
            center = _draw_lines(x, top, width, lines)
            end = fitz.Point(rect.x0 + rect.width / 2.0, rect.y0)
            page.draw_line(center, end, color=color, width=0.4)
            return

        # Try below
        top = rect.y1 + LABEL_MARGIN_PTS
        if top + text_height > page.rect.y1 - 2:
            top = page.rect.y1 - text_height - 2
        x = max(
            page.rect.x0 + LABEL_MARGIN_PTS, min(rect.x0, page.rect.x1 - width - LABEL_MARGIN_PTS)
        )
        center = _draw_lines(x, top, width, lines)
        end = fitz.Point(rect.x0 + rect.width / 2.0, rect.y1)
        page.draw_line(end, center, color=color, width=0.4)

    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {"context": "draw_label"})
