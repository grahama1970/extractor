"""Contract tests for the companion extractor agent skill wrapper."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from extractor.core.recovery import sha256_file


ROOT = Path(__file__).resolve().parents[2]


def _skill_dir() -> Path:
    return Path(os.environ.get("EXTRACTOR_SKILL_DIR", ROOT / ".skills" / "skills" / "extractor"))


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["EXTRACTOR_ROOT"] = str(ROOT)
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


def _load_stdout_json(
    result: subprocess.CompletedProcess[str],
    *,
    expected_codes: set[int] | None = None,
) -> dict[str, Any]:
    expected_codes = {0} if expected_codes is None else expected_codes
    assert result.returncode in expected_codes, result.stderr + result.stdout
    return json.loads(result.stdout)


def _summarize(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload["schema_version"],
        "status": payload["status"],
        "source_sha256": payload["source_sha256"],
        "detected_format": payload["detected_format"],
        "counts": payload["counts"],
        "artifact_kinds": sorted(artifact["kind"] for artifact in payload["artifacts"]),
        "needs_attention": payload["needs_attention"],
        "route": payload["diagnostics"]["route"],
        "engine": payload["diagnostics"].get("engine"),
    }


def test_wrapper_matches_direct_cli_for_pdf_and_docx(tmp_path: Path) -> None:
    skill = _skill_dir()
    assert (skill / "run.sh").is_file(), skill

    for fixture in [
        ROOT / "data/input/twins/preset_twin/preset_twin.pdf",
        ROOT / "data/input/twins/preset_twin/preset_twin.docx",
    ]:
        direct = _load_stdout_json(
            _run(
                [
                    "uv",
                    "run",
                    "extractor",
                    "extract",
                    str(fixture),
                    "--out",
                    str(tmp_path / f"direct-{fixture.suffix[1:]}"),
                    "--offline",
                    "--format",
                    "json",
                ]
            )
        )
        wrapped = _load_stdout_json(
            _run(
                [
                    "bash",
                    str(skill / "run.sh"),
                    str(fixture),
                    "--out",
                    str(tmp_path / f"wrapped-{fixture.suffix[1:]}"),
                    "--offline",
                    "--format",
                    "json",
                ]
            )
        )

        assert _summarize(wrapped) == _summarize(direct)


def test_wrapper_negative_offline_and_source_preservation(tmp_path: Path) -> None:
    skill = _skill_dir()
    fixture = ROOT / "data/input/twins/preset_twin/preset_twin.pdf"
    before = sha256_file(fixture)

    result = _load_stdout_json(
        _run(
            [
                "bash",
                str(skill / "run.sh"),
                str(fixture),
                "--out",
                str(tmp_path / "pdf"),
                "--offline",
            ]
        )
    )

    assert result["schema_version"] == "extractor.result.v1"
    assert result["status"] == "complete"
    assert result["diagnostics"]["extra"]["offline"] is True
    assert sha256_file(fixture) == before

    unsupported = tmp_path / "unsupported.bin"
    unsupported.write_bytes(b"not a supported document")
    blocked = _load_stdout_json(
        _run(
            [
                "bash",
                str(skill / "run.sh"),
                str(unsupported),
                "--out",
                str(tmp_path / "blocked"),
                "--offline",
            ]
        ),
        expected_codes={1},
    )

    assert blocked["status"] == "blocked"
    assert blocked["needs_attention"][0]["code"] == "unsupported_format"


def test_wrapper_surface_is_thin() -> None:
    skill = _skill_dir()
    help_result = _run(["bash", str(skill / "run.sh"), "--help"])
    assert help_result.returncode == 0, help_result.stderr + help_result.stdout
    combined = "\n".join(
        [
            help_result.stdout,
            (skill / "SKILL.md").read_text(encoding="utf-8"),
            (skill / "run.sh").read_text(encoding="utf-8"),
            (skill / "extract.py").read_text(encoding="utf-8"),
        ]
    )
    for forbidden in [
        "--" + "fast",
        "--" + "accurate",
        "--" + "preset",
        "CHUTES" + "_",
        "pdf_" + "oxide",
        "extract_pdf_" + "with",
        ".venv/bin/python",
    ]:
        assert forbidden not in combined
