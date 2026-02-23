#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Create canonical markdown from a flattened JSON (one block per line)."""
from __future__ import annotations
import json
from pathlib import Path
import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    blocks = json.loads(args.flat.read_text())
    lines = []
    for blk in blocks:
        if blk.get("type") == "table" and blk.get("cells"):
            for row in blk["cells"]:
                vals = list(row.values()) if isinstance(row, dict) else row
                lines.append(" | ".join(str(v) for v in vals))
        else:
            lines.append(blk.get("text") or blk.get("content") or "")
    args.out.write_text("\n\n".join(lines), encoding="utf-8")
    print(f"Wrote markdown with {len(blocks)} blocks → {args.out}")


if __name__ == "__main__":
    main()
