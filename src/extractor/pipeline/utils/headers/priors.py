#!/usr/bin/env python3
"""Prior decisions retrieval for Stage 03 (Suspicious Header Verification).

Stub module for database-backed prior header decisions.
Replace with actual ArangoDB queries when ready.
"""

from __future__ import annotations

from typing import Any, List


def retrieve_prior_decisions(
    header_text_norm: str,
    font_sig: str,
    limit: int = 5,
) -> List[dict[str, Any]]:
    """Retrieve prior header decisions from database.
    
    Currently stubbed to prevent NameError when --use-prior is enabled.
    Replace with DB-backed retrieval in future.
    
    Args:
        header_text_norm: Normalized header text
        font_sig: Font signature string
        limit: Maximum number of prior decisions to return
        
    Returns:
        List of prior decision records (currently empty)
    """
    # TODO: Implement ArangoDB query when database is connected
    return []


__all__ = [
    "retrieve_prior_decisions",
]
