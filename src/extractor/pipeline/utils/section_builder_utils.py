#!/usr/bin/env python3
"""Pure helpers for Stage 04 (Section Builder)."""
from __future__ import annotations

from typing import Tuple


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    try:
        r, g, b = rgb
        r = int(max(0, min(255, round(r * (255 if r <= 1 else 1)))))
        g = int(max(0, min(255, round(g * (255 if g <= 1 else 1)))))
        b = int(max(0, min(255, round(b * (255 if b <= 1 else 1)))))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#000000"


def _bucket_color(hex_str: str) -> str:
    try:
        h = hex_str.lstrip('#')
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


def _roman_to_int(roman: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    roman = roman.upper()
    total = 0
    prev = 0
    for ch in reversed(roman):
        val = values.get(ch, 0)
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total
