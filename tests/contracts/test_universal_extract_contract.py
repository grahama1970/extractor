"""Contract tests for the canonical one-command extraction facade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pypdf import PdfWriter
from typer.testing import CliRunner

from cli import app
from extractor.application.extract_file import extract_file
from extractor.core.schema.extraction_result import ExtractionResult


FIXTURE_ROOT = Path("data/input/twins/preset_twin")


def _assert_complete_envelope(result: ExtractionResult, source: Path) -> None:
    assert result.schema_version == "extractor.result.v1"
    assert result.status.value == "complete"
    assert result.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result.counts.blocks > 0
    assert result.artifacts
    for artifact in result.artifacts:
        path = Path(artifact.path)
        assert path.exists()
        assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        assert artifact.size_bytes == path.stat().st_size


def test_extract_file_returns_v1_for_supported_fixtures(tmp_path: Path) -> None:
    for suffix in ("pdf", "docx", "html", "md", "json"):
        source = FIXTURE_ROOT / f"preset_twin.{suffix}"
        if suffix == "json":
            source = FIXTURE_ROOT / "preset_twin_expected.json"
        result = extract_file(source, output_dir=tmp_path / suffix, offline=True)
        _assert_complete_envelope(result, source)


def test_unknown_extension_returns_blocked_envelope(tmp_path: Path) -> None:
    source = tmp_path / "unsupported.bin"
    source.write_bytes(b"\x00\x01not a supported document")
    result = extract_file(source, output_dir=tmp_path / "out", offline=True)
    assert result.schema_version == "extractor.result.v1"
    assert result.status.value == "blocked"
    assert result.needs_attention[0].code == "unsupported_format"


def test_password_protected_pdf_returns_blocked_needs_attention(tmp_path: Path) -> None:
    source = tmp_path / "locked.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    with source.open("wb") as f:
        writer.write(f)

    result = extract_file(source, output_dir=tmp_path / "locked-out", offline=True)

    assert result.schema_version == "extractor.result.v1"
    assert result.status.value == "blocked"
    assert result.needs_attention[0].code == "password_required"
    assert result.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_cli_extract_emits_json_envelope(tmp_path: Path) -> None:
    source = FIXTURE_ROOT / "preset_twin.md"
    runner = CliRunner()
    result = runner.invoke(app, ["extract", str(source), "--out", str(tmp_path), "--offline"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "extractor.result.v1"
    assert payload["status"] == "complete"
    assert payload["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_cli_help_keeps_normal_surface_zero_choice() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["extract", "--help"])

    assert result.exit_code == 0
    assert "--out" in result.output
    assert "--offline" in result.output
    assert "--format" in result.output
    for forbidden in ("--fast", "--accurate", "--preset", "--provider", "--model"):
        assert forbidden not in result.output
