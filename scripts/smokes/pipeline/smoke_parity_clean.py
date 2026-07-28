#!/usr/bin/env python3
"""Parity smoke against clean artifacts (no provider reparse).

It compares canonical flattened PDF blocks with re-flattened clean artifacts
(HTML/MD) and enforces a 95%+ textual match. Tables are compared by type only
because the clean emitters purposely collapse tables to a single block.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List


def load(flat: Path) -> List[Dict[str, Any]]:
    """Load JSON data from a file path into a list of dictionaries."""
    return json.loads(flat.read_text())


def block_kind(block: Dict[str, Any]) -> str:
    """Determine the kind of a block, returning "table" or "text"."""
    data = block.get("data") or {}
    if (data.get("type") or "").lower() == "table":
        return "table"
    if (block.get("object_type") or "").lower() == "table":
        return "table"
    if (block.get("type") or "").lower() == "table":
        return "table"
    return "text"


def block_text(block: Dict[str, Any]) -> str:
    """Extract text content from a block dictionary with fallback values."""
    return block.get("text_content") or block.get("text") or block.get("content") or ""


def normalize(s: str) -> str:
    """Clean string by removing 'TEXT:', unescaping, and normalizing whitespace."""
    s = s.replace("TEXT:", "", 1).strip()
    s = s.replace("\\_", "_")
    return " ".join(s.split())


def compare(
    pdf_blocks: List[Dict[str, Any]], clean_blocks: List[Dict[str, Any]], threshold: float
) -> bool:
    """Validate PDF blocks against clean blocks by threshold."""
    if len(pdf_blocks) != len(clean_blocks):
        print(f"FAIL: block count mismatch pdf={len(pdf_blocks)} clean={len(clean_blocks)}")
        return False

    total = len(pdf_blocks)
    mismatches = 0
    sampled = 0

    for idx, (p, c) in enumerate(zip(pdf_blocks, clean_blocks)):
        pk, ck = block_kind(p), block_kind(c)
        if pk != ck:
            mismatches += 1
            if sampled < 5:
                print(f"  kind mismatch @ {idx}: pdf={pk} clean={ck}")
                sampled += 1
            continue
        if pk == "text":
            if normalize(block_text(p)) != normalize(block_text(c)):
                mismatches += 1
                if sampled < 5:
                    print(
                        f"  text mismatch @ {idx}:\n    pdf: {normalize(block_text(p))[:120]}\n    clean:{normalize(block_text(c))[:120]}"
                    )
                    sampled += 1

    match_rate = (total - mismatches) / max(total, 1)
    print(f"Match rate: {match_rate:.3f} (threshold {threshold:.2f})")
    return match_rate >= threshold


def main():
    """Validate a flattened PDF against provided clean artifacts."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-flat", type=Path, required=True)
    ap.add_argument(
        "--clean-flat",
        type=Path,
        required=True,
        nargs="+",
        help="One or more re-flattened clean artifacts (html/md/docx/pptx/xlsx/rst)",
    )
    ap.add_argument(
        "--ignore-ext",
        type=str,
        default="pptx,xlsx,epub",
        help="Comma-separated list of extensions to skip enforcement (still reported)",
    )
    ap.add_argument("--threshold", type=float, default=0.95)
    args = ap.parse_args()

    ignore_exts = {e.strip().lstrip(".") for e in args.ignore_ext.split(",") if e.strip()}

    pdf_blocks = load(args.pdf_flat)
    if len(pdf_blocks) != 53:
        print(f"FAIL: pdf blocks {len(pdf_blocks)} != 53")
        return 1

    all_ok = True
    for clean in args.clean_flat:
        ext = clean.suffix.lower().lstrip(".")
        if not clean.exists():
            print(f"SKIP parity for {clean} (missing file)")
            continue
        if ext in ignore_exts:
            n = len(load(clean))
            print(f"SKIP parity for {clean} (ext {ext} in ignore list); count={n}")
            continue

        clean_blocks = load(clean)
        ok = compare(pdf_blocks, clean_blocks, args.threshold)
        if not ok:
            print(f"FAIL parity for {clean}")
            all_ok = False
        else:
            print(f"PASS parity for {clean}")

    if not all_ok:
        return 1
    print("PASS: canonical vs all clean artifacts >= threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
