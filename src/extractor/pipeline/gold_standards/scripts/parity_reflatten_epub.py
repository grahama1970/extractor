#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ebooklib>=0.18",
#   "beautifulsoup4>=4.12",
# ]
# ///
"""Re-flatten EPUB into a simple block list (one paragraph/table per block).

This avoids provider variability and aligns with the PDF canonical block shape.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict

from ebooklib import epub
from bs4 import BeautifulSoup


def reflatten_epub(path: Path) -> List[Dict[str, str]]:
    book = epub.read_epub(str(path))
    blocks: List[Dict[str, str]] = []

    # Spine order
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if not item or item.media_type != "application/xhtml+xml":
            continue
        soup = BeautifulSoup(item.get_content(), "lxml")
        for el in soup.find_all(["p", "table"]):
            if el.name == "p":
                txt = el.get_text(" ", strip=True)
                if txt:
                    blocks.append({"type": "text", "text": txt})
            elif el.name == "table":
                blocks.append({"type": "table", "text": "table"})
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    blocks = reflatten_epub(args.epub)
    args.out.write_text(json.dumps(blocks, indent=2), encoding="utf-8")
    print(f"Reflattened {len(blocks)} blocks → {args.out}")


if __name__ == "__main__":
    main()
