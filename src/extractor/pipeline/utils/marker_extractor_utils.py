#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List


def _normalize_text(text: str) -> str:
    """Normalize text to handle PDF encoding issues.

    PDFs often have 15+ encodings for hyphens, various Unicode whitespace,
    ligatures, and other characters. Based on patterns from text_toolz.
    """
    import re
    import unicodedata

    if not text:
        return ""

    # NFKC Unicode Normalization (foundational)
    text = unicodedata.normalize("NFKC", text)

    # Remove directional formatting characters
    directional_pattern = "[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]"
    text = re.sub(directional_pattern, "", text)

    # Remove control characters (C0/C1)
    control_pattern = "[\u0000-\u001f\u007f-\u009f]"
    text = re.sub(control_pattern, "", text)

    # Whitespace variants
    text = text.replace("\u00a0", " ")  # Non-breaking space
    text = text.replace("\u2002", " ")  # En space
    text = text.replace("\u2003", " ")  # Em space
    text = text.replace("\u2009", " ")  # Thin space
    text = text.replace("\u200a", " ")  # Hair space
    text = text.replace("\u202f", " ")  # Narrow no-break space
    text = text.replace("\u205f", " ")  # Medium mathematical space
    text = text.replace("\u3000", " ")  # Ideographic space
    text = text.replace("\u200b", "")   # Zero-width space
    text = text.replace("\u200c", "")   # Zero-width non-joiner
    text = text.replace("\u200d", "")   # Zero-width joiner
    text = text.replace("\ufeff", "")   # BOM
    text = text.replace("\u2060", "")   # Word joiner

    # Hyphen/Dash variants -> ASCII hyphen
    for hc in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d":
        text = text.replace(hc, "-")
    text = text.replace("\u00ad", "")   # Soft hyphen (remove)

    # Quote variants -> ASCII quotes
    for qc in "\u2018\u2019\u201a\u201b\u2032\u2035":
        text = text.replace(qc, "'")
    for qc in "\u201c\u201d\u201e\u201f\u2033\u2036\u00ab\u00bb":
        text = text.replace(qc, '"')
    text = text.replace("\x92", "'")  # Windows right single quote
    text = text.replace("\x93", '"')  # Windows left double quote
    text = text.replace("\x94", '"')  # Windows right double quote

    # Microsoft Symbol font PUA characters (U+F000-U+F0FF)
    symbol_font_map = {
        "\uf020": " ", "\uf02d": "-", "\uf06e": "-",
        "\uf0a7": "*", "\uf0a8": "[ ]", "\uf0b7": "-",
        "\uf0d8": "-", "\uf0e0": "->", "\uf0e8": "-",
        "\uf0fc": "[x]", "\uf076": "[x]",
    }
    for old, new in symbol_font_map.items():
        text = text.replace(old, new)

    # Strip remaining PUA characters (U+E000-U+F8FF)
    text = re.sub(r"[\ue000-\uf8ff]", "", text)

    # Ligatures (expand)
    text = text.replace("\ufb00", "ff")
    text = text.replace("\ufb01", "fi")
    text = text.replace("\ufb02", "fl")
    text = text.replace("\ufb03", "ffi")
    text = text.replace("\ufb04", "ffl")

    # Fix hyphenated words at line breaks
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Collapse whitespace
    text = " ".join(text.split())
    return text.strip()


def fallback_simple_extract(pdf_path: Path, out_json: Path) -> List[Dict[str, Any]]:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        os.environ.get("PYTHON", "python"),
        "-m",
        "extractor.core.scripts.simple_marker_extract",
        str(pdf_path),
        str(out_json),
    ]
    subprocess.run(cmd, check=True)
    data = json.loads(out_json.read_text())
    blocks = data.get("blocks") or []

    # Normalize text in all blocks to handle PDF encoding issues
    for block in blocks:
        if "text" in block and block["text"]:
            block["text"] = _normalize_text(block["text"])

    return blocks
