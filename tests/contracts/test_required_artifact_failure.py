"""Negative controls for required artifact validation."""

from __future__ import annotations

from pathlib import Path

from extractor.application.extract_file import extract_file
from extractor.application.status import validate_required_artifacts
from extractor.core.schema.extraction_result import ArtifactRef


def test_required_artifact_missing_downgrades_complete_to_failed(tmp_path: Path) -> None:
    result = extract_file(
        "data/input/twins/preset_twin/preset_twin.md",
        output_dir=tmp_path,
        offline=True,
    )
    bad = result.model_copy(
        update={
            "artifacts": [
                ArtifactRef(
                    kind="unified_document",
                    path=str(tmp_path / "missing.json"),
                    sha256="0" * 64,
                    size_bytes=1,
                )
            ]
        }
    )

    replayed = validate_required_artifacts(bad)

    assert replayed.status.value == "failed"
    assert "required_artifact_missing:unified_document" in replayed.diagnostics.messages


def test_required_artifact_hash_mismatch_downgrades_to_failed(tmp_path: Path) -> None:
    result = extract_file(
        "data/input/twins/preset_twin/preset_twin.md",
        output_dir=tmp_path,
        offline=True,
    )
    artifact = result.artifacts[0].model_copy(update={"sha256": "0" * 64})
    replayed = validate_required_artifacts(result.model_copy(update={"artifacts": [artifact]}))

    assert replayed.status.value == "failed"
    assert "required_artifact_hash_mismatch:unified_document" in replayed.diagnostics.messages
