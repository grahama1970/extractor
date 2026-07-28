"""Recovery preparation writes derived artifacts outside the source path."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from extractor.core.recovery import copy_source_for_recovery, sha256_file, validate_recovery_attempt


def test_recovery_copy_is_run_owned_and_hash_recorded(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    before = sha256_file(source)

    attempt = copy_source_for_recovery(source, tmp_path / "out", strategy="sanitize")

    assert Path(attempt.derived_path or "").exists()
    assert Path(attempt.derived_path or "").resolve() != source.resolve()
    assert attempt.source_sha256 == before
    assert attempt.derived_sha256 == before
    assert sha256_file(source) == before


def test_changed_derived_artifact_can_be_consumed(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    attempt = copy_source_for_recovery(source, tmp_path / "out", strategy="sanitize")
    derived = Path(attempt.derived_path or "")
    derived.write_text("hello repaired", encoding="utf-8")

    success = replace(
        attempt,
        status="success",
        derived_sha256=sha256_file(derived),
        consumed=True,
    )

    assert validate_recovery_attempt(success) == success
