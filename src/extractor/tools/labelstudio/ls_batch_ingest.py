#!/usr/bin/env python3
"""
Batch ingest a directory of PDFs into a single Label Studio project
using API-only automation (no UI).

Steps per PDF:
  - Render pages and build pre-annotated tasks (predictions) with
    /data/local-files/?d= URLs
  - Import tasks into the given project via API

Prereqs:
  - LABEL_STUDIO running at --host (or $LS_HOST)
  - Personal Access Token (refresh) in --refresh or $LS_REFRESH, or
    pass --access to skip refresh

Example:
  export LS_HOST=http://localhost:8080
  export LS_REFRESH=<your PAT refresh token>
  python -m src.extractor.tools.labelstudio.ls_batch_ingest \
    --pdf-dir data/input/pipeline \
    --project-title "Extractor Annotations" \
    --render-dpi 150 --use-label-config-preset

To also download an export after import, run ls_provision with
--download-export-sync.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from src.extractor.tools.labelstudio.convert_pdf_annotations import (
    render_pages,
    extract_regions_from_pdf,
    build_ls_tasks,
)
from src.extractor.tools.labelstudio.ls_provision import (
    norm_host,
    create_or_update_project,
    auth_headers,
    get_preset_label_config,
)
from src.extractor.tools.labelstudio.util_env import load_ls_env
from src.extractor.tools.labelstudio.util_auth import get_access_token
import json
import os
import requests


def import_tasks_json(host: str, access: str, project_id: int, tasks: List[dict]):
    url = f"{host}/api/projects/{project_id}/import"
    r = requests.post(url, headers=auth_headers(access), json=tasks, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Import failed: HTTP {r.status_code} {r.text}")
    return r.json()


def main():
    ap = argparse.ArgumentParser(description="Batch ingest PDFs into a Label Studio project (API-only)")
    ap.add_argument("--host", default=os.environ.get("LS_HOST", "http://localhost:8080"))
    ap.add_argument("--refresh", default=os.environ.get("LS_REFRESH"))
    ap.add_argument("--access", default=None)
    ap.add_argument("--project-id", type=int, default=None)
    ap.add_argument("--project-title", default=None)
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--render-dpi", type=int, default=150)
    ap.add_argument("--use-label-config-preset", action="store_true")
    args = ap.parse_args()

    load_ls_env()
    host = norm_host(args.host)
    access = args.access or get_access_token(host)

    label_config_xml = get_preset_label_config() if args.use_label_config_preset else None
    pid = create_or_update_project(host, access, project_id=args.project_id, title=args.project_title, label_config=label_config_xml)
    print(f"Project ID: {pid}")

    pdf_dir = Path(args.pdf_dir)
    pdfs = sorted(p for p in pdf_dir.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found.")
        return

    for pdf in pdfs:
        doc_id = pdf.stem
        images_dir = Path("data/labelstudio/images") / doc_id
        print(f"Processing {pdf} → {images_dir}")
        images = render_pages(pdf, images_dir, dpi=args.render_dpi)
        pages_regions, pages_sizes = extract_regions_from_pdf(pdf)
        tasks = build_ls_tasks(pdf, images, pages_regions, pages_sizes)
        # Import directly via API
        resp = import_tasks_json(host, access, pid, tasks)
        print(f"Imported {doc_id}: {json.dumps(resp)}")

    print(f"Done. Open: {host}/projects/{pid}")


if __name__ == "__main__":  # pragma: no cover
    main()
