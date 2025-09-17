#!/usr/bin/env python3
"""
Create Label Studio annotations from an export JSON by copying rectangle
predictions into true annotations and adding per-region metadata
(type/id/expected_json). Useful to verify full round-trip and to generate gold
without touching the UI.

Usage:
  export LS_HOST=http://localhost:8080
  export LS_REFRESH=<your PAT refresh token>
  python -m src.extractor.tools.labelstudio.ls_create_annotations_from_export \
    --project-title "Extractor Annotations" \
    --export data/labelstudio/exports/dataset_export_full.json \
    --type section \
    --limit 4

This will create annotations for the first N tasks (limit) by:
  - Recreating rectangle results from export predictions
  - Adding Choices/TextArea results for type/id/expected_json

Expected JSON path is synthesized as:
  data/gold_standards/<sections|tables>/<doc_id>_page<page>_r<idx>.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

import requests

from src.extractor.tools.labelstudio.ls_provision import (
    norm_host,
    auth_headers,
    create_or_update_project,
)
from src.extractor.tools.labelstudio.util_env import load_ls_env
from src.extractor.tools.labelstudio.util_auth import get_access_token


def create_annotation(host: str, access: str, task_id: int, result: List[Dict]):
    # Per current API docs: POST /api/tasks/:id/annotations/
    url = f"{host}/api/tasks/{task_id}/annotations/"
    payload = {"result": result}
    r = requests.post(url, headers=auth_headers(access), json=payload, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(
            f"Create annotation failed (task {task_id}): HTTP {r.status_code} {r.text}"
        )
    return r.json()


def main():
    ap = argparse.ArgumentParser(description="Create annotations from export predictions")
    ap.add_argument("--host", default=os.environ.get("LS_HOST", "http://localhost:8080"))
    ap.add_argument("--refresh", default=os.environ.get("LS_REFRESH"))
    ap.add_argument("--access", default=None)
    ap.add_argument("--project-id", type=int, default=None)
    ap.add_argument("--project-title", default=None)
    ap.add_argument("--export", required=True, help="Path to LS export JSON (with predictions)")
    ap.add_argument(
        "--type", default="section", help="Type to assign (table|requirements|section|figure)"
    )
    ap.add_argument("--limit", type=int, default=10, help="Number of tasks to annotate (0=all)")
    args = ap.parse_args()

    load_ls_env()
    host = norm_host(args.host)
    access = args.access or get_access_token(host)

    # Ensure project exists (lookup or create)
    pid = create_or_update_project(
        host, access, project_id=args.project_id, title=args.project_title, label_config=None
    )
    print(f"Using project ID: {pid}")

    data = json.loads(Path(args.export).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Export JSON must be a list")

    count = 0
    for task in data:
        if args.limit and count >= args.limit:
            break
        task_id = task.get("id")
        if not task_id:
            continue
        tdata = task.get("data", {})
        doc_id = str(tdata.get("doc_id", "doc"))
        page = int(tdata.get("page", 1))

        preds = task.get("predictions") or []
        # Prefer full predictions with 'result' list
        full = None
        for p in preds:
            if isinstance(p, dict) and isinstance(p.get("result"), list):
                full = p
                break
        if full is None:
            # skip if predictions only contain IDs
            continue

        result: List[Dict] = []
        rect_idx = 0
        for r in full.get("result", []):
            if r.get("type") != "rectanglelabels":
                continue
            rect_idx += 1
            coords = r.get("value", {})
            # Rectangle
            result.append(
                {
                    "from_name": "label",
                    "to_name": "image",
                    "type": "rectanglelabels",
                    "value": {
                        "x": coords.get("x"),
                        "y": coords.get("y"),
                        "width": coords.get("width"),
                        "height": coords.get("height"),
                        "rotation": 0,
                        "rectanglelabels": r.get("value", {}).get("rectanglelabels") or ["Figure"],
                    },
                }
            )
            rid = f"{doc_id}_page{page:02d}_r{rect_idx:02d}"
            # Metadata: type
            result.append(
                {
                    "from_name": "type",
                    "to_name": "image",
                    "type": "choices",
                    "value": {"choices": [args.type]},
                }
            )
            # Metadata: id
            result.append(
                {
                    "from_name": "id",
                    "to_name": "image",
                    "type": "textarea",
                    "value": {"text": [rid]},
                }
            )
            # Metadata: expected_json
            base = (
                "sections"
                if args.type in {"requirements", "section"}
                else ("tables" if args.type == "table" else "figures")
            )
            epath = f"data/gold_standards/{base}/{rid}.json"
            result.append(
                {
                    "from_name": "expected_json",
                    "to_name": "image",
                    "type": "textarea",
                    "value": {"text": [epath]},
                }
            )

        if not result:
            continue
        resp = create_annotation(host, access, task_id, result)
        count += 1
        print(f"Annotated task {task_id}: {resp.get('id')}")

    print(f"Created annotations for {count} tasks")


if __name__ == "__main__":  # pragma: no cover
    main()
