#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Optional


_DASHES = re.compile(r"[‐‑–—−]")


def normalize_table_label(text: str) -> Optional[str]:
    if not text:
        return None
    t = _DASHES.sub("-", text.strip())
    m = re.search(r"(?i)\btable\s+(\d+(?:[-\.]\d+)*[a-z]?)", t)
    if not m:
        return None
    num = m.group(1)
    num_norm = re.sub(r"[.\-]+", "-", num.lower())
    return f"table/{num_norm}"


def normalize_figure_label(text: str) -> Optional[str]:
    if not text:
        return None
    t = _DASHES.sub("-", text.strip())
    m = re.search(r"(?i)\bfig(?:ure)?\s+(\d+(?:[-\.]\d+)*[a-z]?)", t)
    if not m:
        return None
    num = m.group(1)
    num_norm = re.sub(r"[.\-]+", "-", num.lower())
    return f"figure/{num_norm}"

