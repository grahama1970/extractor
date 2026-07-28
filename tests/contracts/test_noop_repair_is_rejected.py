"""No-op recovery attempts must not be accepted as successful repairs."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from extractor.core.recovery import (
    RecoveryContractError,
    RecoveryAttempt,
    copy_source_for_recovery,
    sha256_file,
    validate_recovery_attempt,
)


def test_success_without_changed_artifact_or_config_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    attempt = copy_source_for_recovery(source, tmp_path / "out", strategy="noop")

    claimed = replace(attempt, status="success", consumed=True)

    with pytest.raises(RecoveryContractError, match="changed artifact"):
        validate_recovery_attempt(claimed)


def test_success_on_source_path_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    digest = sha256_file(source)
    claimed = RecoveryAttempt(
        strategy="bad",
        source_path=str(source),
        source_sha256=digest,
        derived_path=str(source),
        derived_sha256=digest,
        status="success",
        consumed=True,
        config_changed=True,
    )

    with pytest.raises(RecoveryContractError, match="source path"):
        validate_recovery_attempt(claimed)
