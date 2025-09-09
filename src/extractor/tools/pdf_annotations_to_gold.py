#!/usr/bin/env python3
"""
Create gold JSON stubs directly from PDF annotations (Box + FreeText mini-schema).

Mini-schema expected in FreeText (JSON or key:value lines):
  id: <string>
  type: table | requirements | section | figure
  expected_json: <repo-relative path to gold json>

If expected_json is present, a stub is created or updated (with --force) at that path.

Usage:
  python -m src.extractor.tools.pdf_annotations_to_gold \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
    --repo-root . [--force]

This script reuses the annotation parsing from the Label Studio converter.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from src.extractor.tools.labelstudio.convert_pdf_annotations import (
    extract_regions_from_pdf,
)


def write_json(path: Path, obj: dict, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        print(f"[skip] Exists: {path}")
        return
    if path.exists() and force:
        backup = path.with_suffix(path.suffix + ".orig.json")
        if not backup.exists():
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[backup] {backup}")
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[write] {path}")


def main():
    ap = argparse.ArgumentParser(description="Create gold stubs from PDF annotations")
    ap.add_argument("--pdf", required=True, help="Annotated PDF path")
    ap.add_argument("--repo-root", default=".", help="Repository root for resolving expected_json")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files (writes .orig.json once)")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")

    pages_regions, _ = extract_regions_from_pdf(pdf)
    repo_root = Path(args.repo_root).resolve()

    created = 0
    for page_index, page_regions in enumerate(pages_regions, start=1):
        for reg_index, reg in enumerate(page_regions, start=1):
            meta: Dict[str, str] = reg.meta or {}
            tgt = (meta.get("expected_json") or "").strip()
            rtype = (meta.get("type") or "").strip().lower()
            rid = (meta.get("id") or "").strip()
            if not tgt:
                # Fallback: autogenerate a sensible default inside repo
                base = "tables" if rtype == "table" else ("sections" if rtype in {"requirements", "section"} else None)
                if base is None:
                    print(f"[info] No expected_json for id={rid} type={rtype}; skipping stub")
                    continue
                slug = rid or f"{pdf.stem}_page{page_index:02d}_r{reg_index:02d}"
                fname = f"{slug}.json"
                tgt = f"data/gold_standards/{base}/{fname}"
            out_path = (repo_root / tgt).resolve()
            if not str(out_path).startswith(str(repo_root)):
                print(f"[warn] Path escapes repo root, skipping: {out_path}")
                continue
            if rtype == "table":
                obj = {"type": "table", "id": rid, "columns": [], "rows": []}
            elif rtype in {"requirements", "section"}:
                title = f"INFERRED: {rid}" if rid else "INFERRED:"
                obj = {"type": "section", "id": rid, "title": title, "columns": [], "rows": []}
            else:
                print(f"[skip] Unsupported type '{rtype}' at {tgt}")
                continue
            write_json(out_path, obj, force=args.force)
            created += 1

    print(f"Done. Gold files created/updated: {created}")


if __name__ == "__main__":  # pragma: no cover
    main()
