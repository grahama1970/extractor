"""Small, portable helpers for the contract loop."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


class ContractLoopError(Exception):
    """Raised when a contract check fails."""


def assert_helping(condition: bool, message: str) -> None:
    if not condition:
        raise ContractLoopError(message)


def check_json_file_valid(path: Path, key_check: Optional[Iterable[str]] = None) -> dict:
    if not path.exists():
        raise ContractLoopError(f"File not found: {path}")
    if path.stat().st_size == 0:
        raise ContractLoopError(f"File is empty: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractLoopError(f"Invalid JSON: {path} ({exc})")

    if key_check:
        for key in key_check:
            if key not in data:
                raise ContractLoopError(f"JSON missing required key '{key}': {path}")
    return data


def ensure_text(value: Any) -> str:
    return str(value or "").strip()


@dataclass
class BundleInfo:
    path: Path
    size_bytes: int
    warned: bool


BUNDLE_WARN_BYTES = 50 * 1024 * 1024
BUNDLE_FAIL_BYTES = 100 * 1024 * 1024


def _gather_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def compose_collaboration_bundle(
    out_dir: Path,
    step_name: str,
    attempt: int,
    *,
    warn_bytes: int = BUNDLE_WARN_BYTES,
    fail_bytes: int = BUNDLE_FAIL_BYTES,
) -> BundleInfo:
    sources: list[tuple[Path, Path]] = []

    def add_if_exists(path: Path) -> None:
        if path.exists():
            rel = path.relative_to(out_dir)
            sources.append((path, rel))

    manifest_path = out_dir / "manifest.json"
    add_if_exists(manifest_path)

    attempt_dir = out_dir / step_name / f"attempt_{attempt}"
    add_if_exists(attempt_dir)

    judge_output = out_dir / step_name / "judge_output.json"
    add_if_exists(judge_output)

    judge_index = out_dir / "judge_index.jsonl"
    add_if_exists(judge_index)

    clarifications = out_dir / "clarifications"
    add_if_exists(clarifications)

    if not sources:
        raise ContractLoopError("No artifacts available for collaboration bundle.")

    total_bytes = sum(_gather_size(path) for path, _ in sources)
    if total_bytes > fail_bytes:
        raise ContractLoopError(
            f"Bundle would exceed {fail_bytes / (1024 * 1024):.1f} MB "
            f"({total_bytes / (1024 * 1024):.1f} MB actual)."
        )

    warned = total_bytes > warn_bytes

    bundles_dir = out_dir / "bundles"
    bundles_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundles_dir / f"{step_name}_attempt_{attempt}.zip"
    if bundle_path.exists():
        bundle_path.unlink()

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for actual_path, rel_path in sources:
            if actual_path.is_dir():
                for file_path in actual_path.rglob("*"):
                    if file_path.is_file():
                        arcname = rel_path / file_path.relative_to(actual_path)
                        zipf.write(file_path, arcname.as_posix())
            else:
                zipf.write(actual_path, rel_path.as_posix())

    return BundleInfo(path=bundle_path, size_bytes=total_bytes, warned=warned)
