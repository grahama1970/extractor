#!/usr/bin/env python3
"""
Provision a Label Studio project and import pre-annotated tasks via API only
(no UI clicks).

Flow:
 1) Exchange a Personal Access Token (refresh) for a short-lived access token
    and use Authorization: Bearer <access>.
 2) Get or create a project by --project-id or --project-title.
 3) Ensure the labeling interface is set.
 4) Import tasks from a JSON array file on disk (with predictions prefilled).
 5) (Optional) Create a Local export storage to write exports into the repo.

Requirements:
  - LABEL_STUDIO is running at --host (default: $LS_HOST or http://localhost:8080)
  - You have a Personal Access Token (refresh) in --refresh or $LS_REFRESH
  - Tasks JSON exists (array of tasks) at --tasks

Example:
  export LS_HOST=http://localhost:8080
  export LS_REFRESH=<your PAT refresh token>
  python -m src.extractor.tools.labelstudio.ls_provision \
    --project-title "Extractor Annotations" \
    --tasks data/labelstudio/tasks/BHT_CV32A65X_marked.tasks.json \
    --use-label-config-preset \
    --create-local-export

This will print the project URL and status codes for each step.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional
import time

import requests
from .util_env import load_ls_env
from .util_auth import get_access_token


def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def norm_host(host: str) -> str:
    host = host.rstrip("/")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "http://" + host
    return host


def refresh_access(host: str, refresh_token: str) -> str:
    url = f"{host}/api/token/refresh"
    headers = {"Authorization": f"Token {refresh_token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"refresh": refresh_token}, timeout=30)
    if resp.status_code != 200:
        die(f"Failed to refresh access token: HTTP {resp.status_code} {resp.text}")
    access = resp.json().get("access")
    if not access:
        die("No 'access' in refresh response")
    return access


def auth_headers(access: str) -> dict:
    return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}


def get_project_by_title(host: str, access: str, title: str) -> Optional[dict]:
    url = f"{host}/api/projects"
    resp = requests.get(url, headers=auth_headers(access), timeout=30)
    if resp.status_code != 200:
        die(f"List projects failed: HTTP {resp.status_code} {resp.text}")
    items = resp.json().get("results") if isinstance(resp.json(), dict) else resp.json()
    if not isinstance(items, list):
        return None
    for p in items:
        if str(p.get("title", "")) == title:
            return p
    return None


def create_or_update_project(
    host: str,
    access: str,
    *,
    project_id: Optional[int],
    title: Optional[str],
    label_config: Optional[str],
) -> int:
    if project_id:
        # Optionally patch label_config
        if label_config:
            url = f"{host}/api/projects/{project_id}"
            r = requests.patch(
                url, headers=auth_headers(access), json={"label_config": label_config}, timeout=30
            )
            if r.status_code not in (200, 202):
                die(f"Failed to patch label_config: HTTP {r.status_code} {r.text}")
        return int(project_id)

    if not title:
        die("Provide --project-id or --project-title")
    # Reuse existing if any
    prj = get_project_by_title(host, access, title)
    if prj:
        pid = int(prj.get("id"))
        if label_config:
            url = f"{host}/api/projects/{pid}"
            r = requests.patch(
                url, headers=auth_headers(access), json={"label_config": label_config}, timeout=30
            )
            if r.status_code not in (200, 202):
                die(f"Failed to patch label_config: HTTP {r.status_code} {r.text}")
        return pid

    # Create new
    payload = {"title": title}
    if label_config:
        payload["label_config"] = label_config
    url = f"{host}/api/projects"
    r = requests.post(url, headers=auth_headers(access), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        die(f"Create project failed: HTTP {r.status_code} {r.text}")
    pid = int(r.json().get("id"))
    return pid


def import_tasks(host: str, access: str, project_id: int, tasks_file: Path):
    url = f"{host}/api/projects/{project_id}/import"
    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    r = requests.post(url, headers=auth_headers(access), json=data, timeout=60)
    if r.status_code not in (200, 201):
        die(f"Import failed: HTTP {r.status_code} {r.text}")
    print(f"Imported: {r.json()}")


def create_local_export_storage(host: str, access: str, project_id: int, path: str) -> int:
    url = f"{host}/api/storages/export/localfiles"
    payload = {"project": project_id, "path": path}
    r = requests.post(url, headers=auth_headers(access), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        die(f"Create export storage failed: HTTP {r.status_code} {r.text}")
    print("Created export storage:", r.json())
    return int(r.json().get("id"))


def export_project_sync(
    host: str, access: str, project_id: int, out_path: Path, download_all_tasks: bool = True
):
    """Download export synchronously via /api/projects/:id/export?exportType=JSON.

    This avoids snapshot polling and writes the JSON directly to disk.
    """
    params = {"exportType": "JSON"}
    if download_all_tasks:
        params["download_all_tasks"] = "true"
    url = f"{host}/api/projects/{project_id}/export"
    r = requests.get(url, headers=auth_headers(access), params=params, timeout=120)
    if r.status_code != 200:
        die(f"Export (sync) failed: HTTP {r.status_code} {r.text}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(r.text, encoding="utf-8")
    print(f"Export written: {out_path}")


def create_export_snapshot(
    host: str, access: str, project_id: int, serialization_options: Optional[dict] = None
) -> int:
    """Create an export snapshot with optional serialization options (e.g., include predictions full)."""
    url = f"{host}/api/projects/{project_id}/exports"
    payload = {}
    if serialization_options:
        payload["serialization_options"] = serialization_options
    r = requests.post(url, headers=auth_headers(access), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        die(f"Create export snapshot failed: HTTP {r.status_code} {r.text}")
    data = r.json()
    export_id = data.get("id") or data.get("pk") or data.get("export_pk")
    if export_id is None:
        die(f"Snapshot create response missing id: {data}")
    return int(export_id)


def wait_export_completed(
    host: str, access: str, project_id: int, export_id: int, timeout_s: int = 120
) -> None:
    url = f"{host}/api/projects/{project_id}/exports/{export_id}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(url, headers=auth_headers(access), timeout=15)
        if r.status_code != 200:
            die(f"Polling export failed: HTTP {r.status_code} {r.text}")
        status = r.json().get("status")
        if status == "completed":
            return
        if status == "failed":
            die(f"Export failed: {r.text}")
        time.sleep(2)
    die("Export polling timeout")


def download_export_snapshot(
    host: str,
    access: str,
    project_id: int,
    export_id: int,
    out_path: Path,
    export_type: str = "JSON",
) -> None:
    url = f"{host}/api/projects/{project_id}/exports/{export_id}/download"
    params = {"exportType": export_type}
    r = requests.get(url, headers=auth_headers(access), params=params, timeout=120)
    if r.status_code != 200:
        die(f"Download snapshot failed: HTTP {r.status_code} {r.text}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(r.text, encoding="utf-8")
    print(f"Snapshot export written: {out_path}")


def get_preset_label_config() -> str:
    return (
        "<View>\n"
        '  <Image name="image" value="$image"/>\n'
        '  <RectangleLabels name="label" toName="image">\n'
        '    <Label value="Table" hotkey="1"/>\n'
        '    <Label value="Requirements" hotkey="2"/>\n'
        '    <Label value="Figure" hotkey="3"/>\n'
        "  </RectangleLabels>\n"
        '  <Choices name="type" toName="image" perRegion="true" required="true">\n'
        '    <Choice value="table"/>\n'
        '    <Choice value="requirements"/>\n'
        '    <Choice value="figure"/>\n'
        "  </Choices>\n"
        '  <TextArea name="id" toName="image" perRegion="true" required="true" displayMode="region-list"/>\n'
        '  <TextArea name="expected_json" toName="image" perRegion="true" displayMode="region-list"/>\n'
        "</View>"
    )


def main():
    ap = argparse.ArgumentParser(description="Provision LS project + import tasks (API only)")
    ap.add_argument("--host", default=os.environ.get("LS_HOST", "http://localhost:8080"))
    ap.add_argument(
        "--refresh",
        default=os.environ.get("LS_REFRESH"),
        help="(optional) Personal access token (refresh)",
    )
    ap.add_argument(
        "--access",
        default=None,
        help="(optional) Use an access token directly (skips refresh) — otherwise auto-load from cache/.env",
    )
    ap.add_argument("--project-id", type=int, default=None)
    ap.add_argument("--project-title", default=None)
    ap.add_argument("--tasks", required=True, help="Path to tasks JSON array file")
    ap.add_argument("--label-config", default=None, help="Path to label config XML")
    ap.add_argument("--use-label-config-preset", action="store_true")
    ap.add_argument("--create-local-export", action="store_true")
    ap.add_argument("--export-path", default="/label-studio/localdata/labelstudio/exports")
    ap.add_argument(
        "--download-export-sync",
        default=None,
        help="If set, downloads JSON export to this file after import.",
    )
    ap.add_argument(
        "--snapshot-export",
        default=None,
        help="If set, create export snapshot (predictions full) and download to this file.",
    )
    args = ap.parse_args()

    load_ls_env()
    host = norm_host(args.host)
    access = args.access or get_access_token(host)
    print("Access token ready.")

    label_config_xml = None
    if args.use_label_config_preset:
        label_config_xml = get_preset_label_config()
    elif args.label_config:
        label_config_xml = Path(args.label_config).read_text(encoding="utf-8")

    pid = create_or_update_project(
        host,
        access,
        project_id=args.project_id,
        title=args.project_title,
        label_config=label_config_xml,
    )
    print(f"Project ID: {pid}")

    tasks_file = Path(args.tasks)
    if not tasks_file.exists():
        die(f"Tasks file not found: {tasks_file}")
    import_tasks(host, access, pid, tasks_file)

    if args.create_local_export:
        create_local_export_storage(host, access, pid, args.export_path)

    if args.download_export_sync:
        export_project_sync(host, access, pid, Path(args.download_export_sync))

    if args.snapshot_export:
        # Ensure predictions are exported fully (not only IDs)
        export_id = create_export_snapshot(
            host,
            access,
            pid,
            serialization_options={
                "predictions": {"only_id": False},
                "drafts": {"only_id": True},
                "include_annotation_history": False,
            },
        )
        wait_export_completed(host, access, pid, export_id)
        download_export_snapshot(host, access, pid, export_id, Path(args.snapshot_export))

    print(f"Done. Open: {host}/projects/{pid}")


if __name__ == "__main__":  # pragma: no cover
    main()
