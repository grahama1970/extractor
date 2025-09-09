#!/usr/bin/env python3
"""
Split a Label Studio tasks JSON (array of tasks) into one JSON file per task
so it can be imported via Cloud Storage → Local files (which expects a single
task dict per file).

Usage:
  python -m src.extractor.tools.labelstudio.split_tasks_for_localfiles \
    --in data/labelstudio/tasks/BHT_CV32A65X_marked.tasks.json \
    --out data/labelstudio/tasks/BHT_CV32A65X_marked_local

Then in Label Studio:
  - Project → Settings → Cloud Storage → Add Source Storage → Local files
  - Absolute path: /label-studio/localdata/labelstudio/tasks/BHT_CV32A65X_marked_local
  - File name filter: .*\.json$
  - Leave "Treat every bucket object as a source file" OFF (import JSON tasks)
  - Save → Sync Storage
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Split tasks array into per-file JSON for LocalFiles import")
    ap.add_argument("--in", dest="in_path", required=True, help="Input tasks JSON (array of tasks)")
    ap.add_argument("--out", dest="out_dir", required=True, help="Output directory for per-task JSON files")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(in_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Input file must be a JSON array of tasks (list)")

    count = 0
    for idx, task in enumerate(data, start=1):
        if not isinstance(task, dict):
            continue
        out_file = out_dir / f"task_{idx:03d}.json"
        out_file.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        count += 1

    print(f"Wrote {count} task files to: {out_dir}")
    print("Set LS Source Storage path to the directory above and sync.")


if __name__ == "__main__":  # pragma: no cover
    main()

