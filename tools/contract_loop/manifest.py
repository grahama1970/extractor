import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class StepRecord:
    step: str
    attempt: int
    status: str  # "success", "failed", "skipped"
    duration_sec: float
    output_hash: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)


@dataclass
class ManifestData:
    run_id: str
    start_time: str
    command_line: List[str]
    git_sha: str
    environment: dict
    fixture_info: dict
    steps: List[StepRecord] = field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None
    clarifications: List[Dict[str, Any]] = field(default_factory=list)


class Manifest:
    def __init__(
        self,
        out_dir: Path,
        cmd_args: List[str],
        fixture_path: Optional[Path],
        debug_info: Optional[Dict[str, Any]] = None,
    ):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out_dir / "manifest.json"
        
        # Capture environment info
        try:
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            ).decode().strip()
        except subprocess.CalledProcessError:
            git_sha = "unknown"

        fixture_info = {}
        if fixture_path and fixture_path.exists():
            fixture_info = {
                "path": str(fixture_path),
                "sha256": self._hash_file(fixture_path)
            }

        self.data = ManifestData(
            run_id=str(uuid.uuid4()),
            start_time=datetime.now(timezone.utc).isoformat(),
            command_line=cmd_args,
            git_sha=git_sha,
            environment={
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                "cwd": str(Path.cwd()),
            },
            fixture_info=fixture_info,
            debug=debug_info,
        )
        self._save()

    def add_step_attempt(
        self,
        step_name: str,
        attempt: int,
        status: str,
        duration_sec: float,
        artifact_paths: Optional[List[str]] = None,
    ):
        output_hash = None
        artifacts: List[str] = []
        hashes: List[str] = []

        if artifact_paths:
            for path_str in artifact_paths:
                full_path = self.out_dir / path_str
                if not full_path.exists():
                    continue
                artifacts.append(path_str)
                if status == "success":
                    if full_path.is_file():
                        hashes.append(self._hash_file(full_path))
                    elif full_path.is_dir():
                        hashes.append(self._hash_dir(full_path))

        if hashes:
            output_hash = hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()

        record = StepRecord(
            step=step_name,
            attempt=attempt,
            status=status,
            duration_sec=duration_sec,
            output_hash=output_hash,
            artifacts=artifacts,
        )
        self.data.steps.append(record)
        self._save()

    def record_clarification(self, step_name: str, attempt: int, rel_path: str) -> None:
        self.data.clarifications.append(
            {"step": step_name, "attempt": attempt, "path": rel_path}
        )
        self._save()

    def _save(self):
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.data), f, indent=2)

    def _hash_file(self, path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)
        return sha.hexdigest()

    def _hash_dir(self, path: Path) -> str:
        """Deterministically hash a directory by hashing file contents in sorted order."""
        sha = hashlib.sha256()
        for p in sorted(path.rglob("*")):
            if p.is_file():
                # Add relative path to distinguish same content in diff files
                rel_path = p.relative_to(path).as_posix()
                sha.update(rel_path.encode())
                with open(p, "rb") as f:
                    while chunk := f.read(8192):
                        sha.update(chunk)
        return sha.hexdigest()
