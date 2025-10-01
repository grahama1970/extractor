#!/usr/bin/env python3
"""
Generate gold JSON stubs directly from Label Studio exports.

For each region that includes an `expected_json` path, create (or update with --force)
the referenced JSON file with a minimal schema aligned to our evals.

Supported region types → gold schema stubs:
- table → { type, id, columns: [], rows: [] }
- requirements/section → { type: "section", id, title: "INFERRED: <id>", columns: [], rows: [] }

Usage:
  python -m src.extractor.tools.labelstudio.ls_export_to_gold \
    --export data/labelstudio/exports/my_project-annotations.json \
    --repo-root .

Optional flags:
  --force              Overwrite existing gold files (writes .orig.json backup once)
  --dry-run            Print actions without writing files

Notes:
- Paths are resolved relative to --repo-root (default: project root). For safety,
  only paths under the repo root are allowed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def _pick_results(task: Dict) -> List[Dict]:
    anns = task.get("annotations") or []
    if isinstance(anns, list) and anns:
        anns_sorted = sorted(anns, key=lambda a: a.get("updated_at") or a.get("id") or 0)
        return anns_sorted[-1].get("result", [])
    preds = task.get("predictions") or []
    if isinstance(preds, list) and preds:
        return preds[0].get("result", [])
    return []


def _group_regions(results: List[Dict]) -> Dict[str, Dict]:
    regions: Dict[str, Dict] = {}
    last_rect_key = None
    for r in results:
        if r.get("type") == "rectanglelabels" and r.get("from_name") == "label":
            rid = r.get("id") or r.get("origin_id") or f"rect_{len(regions)}"
            regions[rid] = {"id": None, "type": None, "expected_json": None, "gold_json": None}
            last_rect_key = rid
    for r in results:
        if r.get("type") == "rectanglelabels":
            continue
        rid = r.get("region_id") or last_rect_key
        if not rid or rid not in regions:
            continue
        fn = r.get("from_name")
        val = r.get("value", {})
        if fn == "type":
            choices = val.get("choices") or []
            if choices:
                regions[rid]["type"] = str(choices[0]).strip()
        elif fn == "id":
            txt = val.get("text") or []
            if txt:
                regions[rid]["id"] = str(txt[0]).strip()
        elif fn == "expected_json":
            txt = val.get("text") or []
            if txt:
                regions[rid]["expected_json"] = str(txt[0]).strip()
        elif fn == "gold_json":
            txt = val.get("text") or []
            if txt:
                regions[rid]["gold_json"] = str(txt[0]).strip()
    return regions


def _safe_path(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    root_resolved = root.resolve()
    if not str(p).startswith(str(root_resolved)):
        raise ValueError(f"Target path escapes repo root: {p}")
    return p


def _write_json(path: Path, obj: dict, force: bool, dry_run: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        print(f"[skip] Exists: {path}")
        return
    if path.exists() and force:
        backup = path.with_suffix(path.suffix + ".orig.json")
        if not backup.exists():
            if dry_run:
                print(f"[dry-run] Would write backup: {backup}")
            else:
                backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"[backup] {backup}")
    payload = json.dumps(obj, indent=2, ensure_ascii=False)
    if dry_run:
        print(f"[dry-run] Would write: {path}\n{payload}\n")
    else:
        path.write_text(payload + "\n", encoding="utf-8")
        print(f"[write] {path}")


def main():
    ap = argparse.ArgumentParser(description="Create gold JSON stubs from LS export")
    ap.add_argument("--export", required=True, help="Label Studio export JSON path")
    ap.add_argument(
        "--repo-root", default=".", help="Repository root for resolving expected_json paths"
    )
    ap.add_argument(
        "--force", action="store_true", help="Overwrite existing files (backup .orig.json)"
    )
    ap.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    args = ap.parse_args()

    export_path = Path(args.export)
    repo_root = Path(args.repo_root)
    tasks = json.loads(export_path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise SystemExit("Export JSON does not look like a list of tasks.")

    created = 0
    written_paths = set()
    for t in tasks:
        results = _pick_results(t)
        regions = _group_regions(results)
        for r in regions.values():
            tgt = r.get("expected_json")
            rtype = (r.get("type") or "").strip().lower()
            rid = r.get("id") or ""
            if not tgt:
                continue
            try:
                out_path = _safe_path(repo_root, tgt)
            except ValueError as e:
                print(f"[warn] {e}")
                continue
            if str(out_path) in written_paths:
                # Avoid overwriting same expected_json multiple times in one export
                continue

            # Build stub payloads
            if rtype == "table":
                if r.get("gold_json"):
                    try:
                        obj = json.loads(r["gold_json"])
                    except Exception:
                        obj = {"type": "table", "id": rid, "columns": [], "rows": []}
                else:
                    obj = {"type": "table", "id": rid, "columns": [], "rows": []}
            elif rtype in {"requirements", "section"}:
                title = f"INFERRED: {rid}" if rid else "INFERRED:"
                if r.get("gold_json"):
                    try:
                        obj = json.loads(r["gold_json"])
                    except Exception:
                        obj = {
                            "type": "section",
                            "id": rid,
                            "title": title,
                            "columns": [],
                            "rows": [],
                        }
                else:
                    obj = {"type": "section", "id": rid, "title": title, "columns": [], "rows": []}
            else:
                # Optional: ignore other types like figure
                print(f"[skip] Unhandled type '{rtype}' at {tgt}")
                continue

            _write_json(out_path, obj, force=args.force, dry_run=args.dry_run)
            created += 1
            written_paths.add(str(out_path))

    print(f"Done. Processed tasks. Files created/updated: {created}")


if __name__ == "__main__":  # pragma: no cover
    main()
