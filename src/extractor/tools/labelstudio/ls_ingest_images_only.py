#!/usr/bin/env python3
"""
Ingest a single PDF into Label Studio as images-only (no pre-annotations),
via API only (no UI). Renders pages and imports tasks with only the image URL
(/data/local-files/?d=...). No annotations are merged into the pixels.

Usage:
  export LS_HOST=http://localhost:8080
  export LS_REFRESH=<your PAT refresh token>
  python -m src.extractor.tools.labelstudio.ls_ingest_images_only \
    --pdf data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf \
    --project-title "Images Only: cleaned_BHT" \
    --render-dpi 300 --use-label-config-preset
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

from src.extractor.tools.labelstudio.convert_pdf_annotations import render_pages
from src.extractor.tools.labelstudio.ls_provision import (
    norm_host,
    create_or_update_project,
    auth_headers,
    get_preset_label_config,
)
from src.extractor.tools.labelstudio.util_env import load_ls_env
from src.extractor.tools.labelstudio.util_auth import get_access_token
import requests


def build_image_only_tasks(pdf_path: Path, images: List[Path]) -> List[Dict]:
    doc_id = pdf_path.stem
    tasks: List[Dict] = []
    for idx, img_path in enumerate(images):
        page_num = idx + 1
        # Compose container-served URL: /data/local-files/?d=labelstudio/images/.../page_###.png
        try:
            rel_from_data = img_path.relative_to("data")
            # Use path relative to LS document root (mounted ./data)
            container_image = f"/data/local-files/?d={rel_from_data.as_posix()}"
        except Exception:
            p = img_path.as_posix()
            if not p.startswith("/label-studio/localdata/"):
                container_image = f"/data/local-files/?d=/label-studio/localdata/{p}"
            else:
                container_image = f"/data/local-files/?d={p}"

        task = {
            "data": {
                "image": container_image,
                "source_pdf": str(pdf_path.as_posix()),
                "page": page_num,
                "doc_id": doc_id,
            }
        }
        tasks.append(task)
    return tasks


def import_tasks(host: str, access: str, project_id: int, tasks: List[Dict]):
    url = f"{host}/api/projects/{project_id}/import"
    r = requests.post(url, headers=auth_headers(access), json=tasks, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Import failed: HTTP {r.status_code} {r.text}")
    return r.json()


def main():
    ap = argparse.ArgumentParser(
        description="Ingest a PDF as images-only into Label Studio (API-only)"
    )
    ap.add_argument("--host", default=os.environ.get("LS_HOST", "http://localhost:8080"))
    ap.add_argument("--refresh", default=os.environ.get("LS_REFRESH"))
    ap.add_argument("--access", default=None)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--project-id", type=int, default=None)
    ap.add_argument("--project-title", default=None)
    ap.add_argument("--render-dpi", type=int, default=300)
    ap.add_argument("--use-label-config-preset", action="store_true")
    args = ap.parse_args()

    load_ls_env()
    host = norm_host(args.host)
    access = args.access or get_access_token(host)

    label_config_xml = get_preset_label_config() if args.use_label_config_preset else None
    pid = create_or_update_project(
        host,
        access,
        project_id=args.project_id,
        title=args.project_title,
        label_config=label_config_xml,
    )
    print(f"Project ID: {pid}")

    pdf = Path(args.pdf)
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    images_dir = Path("data/labelstudio/images") / pdf.stem
    images = render_pages(pdf, images_dir, dpi=args.render_dpi)
    tasks = build_image_only_tasks(pdf, images)
    resp = import_tasks(host, access, pid, tasks)
    print("Imported:", json.dumps(resp))
    print(f"Open: {host}/projects/{pid}")


if __name__ == "__main__":  # pragma: no cover
    main()
