"""Contract tests for terminal extractor.result.v1 status semantics."""

from __future__ import annotations

from pathlib import Path

from extractor.application.extract_file import extract_file
from extractor.application.status import result_exit_code, validate_required_artifacts
from extractor.core.schema.extraction_result import ExtractionStatus


def test_complete_result_replays_artifact_validation(tmp_path: Path) -> None:
    result = extract_file(
        "data/input/twins/preset_twin/preset_twin.md",
        output_dir=tmp_path,
        offline=True,
    )
    replayed = validate_required_artifacts(result)

    assert replayed.status is ExtractionStatus.COMPLETE
    assert result_exit_code(replayed) == 0


def test_blocked_and_failed_statuses_are_nonzero() -> None:
    assert result_exit_code(
        extract_file("/path/that/does/not/exist.pdf", output_dir="/tmp/extractor-missing")
    ) == 1
