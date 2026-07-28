"""Contracts for the installed extractor console entrypoint."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )


def test_console_version_and_help_are_lightweight() -> None:
    version = _run(["uv", "run", "extractor", "version"])
    assert version.returncode == 0, version.stderr + version.stdout
    assert version.stdout.strip()

    help_result = _run(["uv", "run", "extractor", "extract", "--help"])
    assert help_result.returncode == 0, help_result.stderr + help_result.stdout
    for forbidden in ["--" + "fast", "--" + "accurate", "--" + "preset"]:
        assert forbidden not in help_result.stdout


def test_console_extract_emits_result_v1(tmp_path: Path) -> None:
    fixture = ROOT / "data/input/twins/preset_twin/preset_twin.docx"
    result = _run(
        [
            "uv",
            "run",
            "extractor",
            "extract",
            str(fixture),
            "--out",
            str(tmp_path / "docx"),
            "--offline",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "extractor.result.v1"
    assert payload["status"] == "complete"
    assert payload["detected_format"] == "docx"
