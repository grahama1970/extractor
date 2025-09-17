#!/usr/bin/env python3
"""
Ingest a PDF into Label Studio by UPLOADING rendered images (no local-files).
This avoids any local-files serving issues by storing images inside LS and
referencing them as /data/upload/<filename> automatically.

Usage:
  export LS_HOST=http://localhost:8080
  export LS_REFRESH=<your PAT refresh token>
  python -m src.extractor.tools.labelstudio.ls_ingest_images_upload \
    --pdf data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf \
    --project-title "Images Only (upload): cleaned_BHT" \
    --render-dpi 300 --use-label-config-preset
"""

from __future__ import annotations

import argparse
from pathlib import Path
import os
import requests

from src.extractor.tools.labelstudio.convert_pdf_annotations import render_pages
from src.extractor.tools.labelstudio.ls_provision import (
    norm_host,
    create_or_update_project,
    get_preset_label_config,
)
from src.extractor.tools.labelstudio.util_env import load_ls_env
from src.extractor.tools.labelstudio.util_auth import get_access_token


def import_image_file(host: str, access: str, project_id: int, img_path: Path):
    url = f"{host}/api/projects/{project_id}/import"
    headers = {"Authorization": f"Bearer {access}"}
    with img_path.open("rb") as f:
        files = {"file": (img_path.name, f, "image/png")}
        r = requests.post(url, headers=headers, files=files, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Import file failed: {img_path} HTTP {r.status_code} {r.text}")
    return r.json()


def main():
    ap = argparse.ArgumentParser(description="Ingest PDF pages by uploading images to Label Studio")
    ap.add_argument("--host", default=os.environ.get("LS_HOST", "http://localhost:8080"))
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--project-id", type=int, default=None)
    ap.add_argument("--project-title", default=None)
    ap.add_argument("--render-dpi", type=int, default=300)
    ap.add_argument("--use-label-config-preset", action="store_true")
    args = ap.parse_args()

    load_ls_env()
    host = norm_host(args.host)
    access = get_access_token(host)

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

    total = 0
    for img in images:
        resp = import_image_file(host, access, pid, img)
        total += resp.get("task_count", 0)
    print(f"Imported files as tasks: {total}")
    print(f"Open: {host}/projects/{pid}")


if __name__ == "__main__":  # pragma: no cover
    main()
