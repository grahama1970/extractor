from __future__ import annotations

from typing import Any


def normalize_contacts(contacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize messy contact dicts.

    Source of truth:
    - CONTRACTS.md
    - tools/gate_normalize_contacts.py (canonical sample)
    """
    raise NotImplementedError("Implement normalize_contacts")
