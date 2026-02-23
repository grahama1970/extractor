"""
Helpers for Stage 03 (suspicious_headers).
"""

from __future__ import annotations

import hashlib
from typing import Any

import fitz  # PyMuPDF


def norm_text(s: str) -> str:
    return " ".join((s or "").split())


def text_sha1(s: str) -> str:
    return hashlib.sha1(norm_text(s).encode("utf-8")).hexdigest()


def has_bullet_prefix(text: str) -> bool:
    bullets = {"•", "●", "▪", "‣", "⁃", "–", "—", "-", "*", "+", "·"}
    t = (text or "").lstrip()
    return bool(t) and t[0] in bullets


def bucket_color_hex(hex_str: str) -> str:
    try:
        h = hex_str.lstrip("#")
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        if r < 30 and g < 30 and b < 30:
            return "black"
        if r > 200 and g > 200 and b > 200:
            return "white"
        if r > g and r > b:
            return "red"
        if g > r and g > b:
            return "green"
        if b > r and b > g:
            return "blue"
        return "gray"
    except Exception:
        return "unknown"


def ensure_first_span_color(page: fitz.Page, block: dict[str, Any]) -> None:
    """Populate block.first_span_font.color_{hex,bucket,rgb} if missing, using span intersect."""
    fsf = (
        block.setdefault("first_span_font", {})
        if isinstance(block.get("first_span_font"), dict)
        else block.setdefault("first_span_font", {})
    )
    if fsf.get("color_hex") or fsf.get("color_bucket"):
        return
    bb = block.get("bbox")
    if not bb:
        return
    x0, y0, x1, y1 = bb
    td = page.get_text("dict")
    found = None
    for blk in td.get("blocks", []):
        for line in blk.get("lines", []):
            for span in line.get("spans", []):
                sb = span.get("bbox")
                if not sb:
                    continue
                sx0, sy0, sx1, sy1 = sb
                if not (sx1 < x0 or sx0 > x1 or sy1 < y0 or sy0 > y1):
                    col = span.get("color")
                    if isinstance(col, (list, tuple)) and len(col) >= 3:
                        r, g, b = col[0], col[1], col[2]
                        # Normalize if 0..1
                        if 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0:
                            r, g, b = int(r * 255), int(g * 255), int(b * 255)
                        else:
                            r, g, b = int(r), int(g), int(b)
                        found = (r, g, b)
                    elif isinstance(col, (int, float)):
                        v = int(col)
                        found = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
                    break
            if found:
                break
        if found:
            break
    if not found:
        return
    hexv = f"#{found[0]:02x}{found[1]:02x}{found[2]:02x}"
    fsf["color_rgb"] = list(found)
    fsf["color_hex"] = hexv
    fsf["color_bucket"] = bucket_color_hex(hexv)
