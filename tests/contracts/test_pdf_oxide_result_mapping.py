"""Contract tests for mapping pdf_oxide output into extractor.result.v1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from extractor.application.extract_file import extract_file


PDF_FIXTURE = Path("data/input/twins/preset_twin/preset_twin.pdf")


def test_pdf_oxide_raw_artifact_and_normalized_counts_are_hashed(tmp_path: Path) -> None:
    result = extract_file(PDF_FIXTURE, output_dir=tmp_path, offline=True)

    raw_artifacts = [artifact for artifact in result.artifacts if artifact.kind == "pdf_oxide_result"]
    assert len(raw_artifacts) == 1
    raw_path = Path(raw_artifacts[0].path)
    assert raw_path.exists()
    assert raw_artifacts[0].sha256 == hashlib.sha256(raw_path.read_bytes()).hexdigest()

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw["page_count"] == result.counts.pages
    assert len(raw["blocks"]) > 0
    assert result.counts.tables == len(raw["tables"])
    assert result.counts.figures == len(raw["figures"])


def test_pdf_oxide_core_extraction_does_not_enable_plugins(tmp_path: Path) -> None:
    result = extract_file(PDF_FIXTURE, output_dir=tmp_path, offline=True)

    raw_path = next(artifact for artifact in result.artifacts if artifact.kind == "pdf_oxide_result").path
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))

    assert "plugin_report" not in raw.get("metadata", {})
    assert result.diagnostics.extra["offline"] is True
    assert result.diagnostics.extra["pdf_oxide_output_sha256"]
