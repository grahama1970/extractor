from __future__ import annotations
from typing import Optional


def sanitize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    removals = [
        "‎",
        "‏",  # LRM/RLM
        "​",
        "‌",
        "‍",  # zero-width
        "‪",
        "‫",
        "‬",
        "‭",
        "‮",  # bidi overrides
        "⁦",
        "⁧",
        "⁨",
        "⁩",  # isolates
    ]
    s2 = str(s)
    for ch in removals:
        s2 = s2.replace(ch, "")
    s2 = s2.replace(" ", " ")
    return "\n".join(" ".join(line.split()) for line in s2.splitlines()).strip()
