"""Stub artifacts must not satisfy required artifact gates."""

from __future__ import annotations

import hashlib
from pathlib import Path

from extractor.application.extract_file import extract_file
from extractor.application.status import validate_required_artifacts
from extractor.core.schema.extraction_result import ArtifactRef


def test_stub_artifact_cannot_make_result_complete(tmp_path: Path) -> None:
    result = extract_file(
        "data/input/twins/preset_twin/preset_twin.md",
        output_dir=tmp_path / "real",
        offline=True,
    )
    stub = tmp_path / "stub.json"
    stub.write_text('{"stub": true, "blocks": []}', encoding="utf-8")
    artifact = ArtifactRef(
        kind="unified_document",
        path=str(stub),
        sha256=hashlib.sha256(stub.read_bytes()).hexdigest(),
        size_bytes=stub.stat().st_size,
    )

    replayed = validate_required_artifacts(result.model_copy(update={"artifacts": [artifact]}))

    assert replayed.status.value == "failed"
    assert "required_artifact_stub:unified_document" in replayed.diagnostics.messages
