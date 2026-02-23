from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_latest_status(log_root: Path) -> dict:
    status: dict = {
        "generated_at_utc": None,
        "tasks": {},
    }

    if not log_root.exists():
        status["generated_at_utc"] = _timestamp()
        status["error"] = f"log root not found: {log_root}"
        return status

    latest_run_stamp = None
    for task_dir in sorted(p for p in log_root.iterdir() if p.is_dir()):
        runs = sorted((p for p in task_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
        if not runs:
            continue
        latest = runs[-1]
        artifacts = sorted(str(path) for path in latest.rglob("*") if path.is_file())
        status["tasks"][task_dir.name] = {
            "latest_run_dir": str(latest),
            "artifacts": artifacts,
        }
        if latest_run_stamp is None or latest.name > latest_run_stamp:
            latest_run_stamp = latest.name

    status["generated_at_utc"] = latest_run_stamp or _timestamp()
    return status


def write_latest_status(*, log_root: Path, output_path: Path) -> Path:
    payload = build_latest_status(log_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write latest contract loop status.")
    parser.add_argument(
        "--log-root",
        type=Path,
        default=Path("logs/contract_loop"),
        help="Directory containing contract loop logs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/contract_loop/latest_status.json"),
        help="Output JSON path.",
    )
    args = parser.parse_args()

    write_latest_status(log_root=args.log_root, output_path=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
