#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Quick smoke for 06a nearest-above/below logic (no network).

Usage:
  PYTHONPATH=src python scripts/smokes/06a_nearby_blocks_smoke.py

Prints the chosen 'above' and 'below' blocks for a synthetic page and bbox.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List
import importlib

# Import the module (numeric module name requires importlib)
s06a = importlib.import_module("extractor.pipeline.steps.06a_title_caption_enricher")


def main() -> None:
    # Create a small synthetic page with a few text-like blocks
    page_idx = 0
    blocks: List[Dict[str, Any]] = [
        {
            "block_type": "Text",
            "text": "Figure 1: Overall pipeline architecture",
            "bbox": [80, 300, 520, 330],
        },
        {
            "block_type": "Text",
            "text": "This figure shows the relationship between stages.",
            "bbox": [82, 560, 520, 590],
        },
        {
            "block_type": "SectionHeader",
            "text": "4.1.5.4. BHT (Branch History Table) submodule",
            "bbox": [70, 260, 540, 290],
        },
        {
            "block_type": "ListItem",
            "text": "• Additional notes about the figure.",
            "bbox": [84, 610, 480, 635],
        },
    ]
    page_blocks = {page_idx: blocks}

    # Target bbox roughly between the above and below blocks
    target_bbox = [90, 400, 500, 520]

    above, below = s06a._nearest_above_below(page_blocks, page_idx, target_bbox, min_h_overlap=0.2)

    out = {
        "target_bbox": target_bbox,
        "above_text": (above.get("text") if isinstance(above, dict) else None),
        "below_text": (below.get("text") if isinstance(below, dict) else None),
        "above_bbox": (above.get("bbox") if isinstance(above, dict) else None),
        "below_bbox": (below.get("bbox") if isinstance(below, dict) else None),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
