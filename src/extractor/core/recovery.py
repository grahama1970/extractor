"""Copy-on-write recovery primitives for extraction inputs."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecoveryAttempt:
    """A recovery attempt with source and derived artifact provenance."""

    strategy: str
    source_path: str
    source_sha256: str
    derived_path: str | None
    derived_sha256: str | None
    status: str
    consumed: bool
    config_changed: bool = False


class RecoveryContractError(ValueError):
    """Raised when recovery would mutate source or claim a no-op as success."""


def copy_source_for_recovery(source: str | Path, output_dir: str | Path, *, strategy: str) -> RecoveryAttempt:
    """Copy a source file to a run-owned derived path before recovery work."""

    source_path = Path(source).resolve()
    output_path = Path(output_dir).resolve()
    derived_dir = output_path / "recovery" / strategy
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_path = derived_dir / source_path.name
    shutil.copy2(source_path, derived_path)
    return RecoveryAttempt(
        strategy=strategy,
        source_path=str(source_path),
        source_sha256=sha256_file(source_path),
        derived_path=str(derived_path),
        derived_sha256=sha256_file(derived_path),
        status="prepared",
        consumed=False,
    )


def validate_recovery_attempt(attempt: RecoveryAttempt) -> RecoveryAttempt:
    """Validate that a claimed recovery is copy-on-write and not a no-op."""

    if attempt.status != "success":
        return attempt
    if not attempt.derived_path or not attempt.derived_sha256:
        raise RecoveryContractError("successful recovery requires a derived artifact")
    source_path = Path(attempt.source_path)
    derived_path = Path(attempt.derived_path)
    if source_path.resolve() == derived_path.resolve():
        raise RecoveryContractError("successful recovery cannot use the source path as output")
    if not derived_path.exists():
        raise RecoveryContractError("successful recovery derived artifact is missing")
    if sha256_file(source_path) != attempt.source_sha256:
        raise RecoveryContractError("source hash changed during recovery")
    if sha256_file(derived_path) != attempt.derived_sha256:
        raise RecoveryContractError("derived artifact hash mismatch")
    if attempt.derived_sha256 == attempt.source_sha256 and not attempt.config_changed:
        raise RecoveryContractError(
            "successful recovery must produce a changed artifact or changed execution config"
        )
    if not attempt.consumed:
        raise RecoveryContractError("successful recovery derived artifact was not consumed")
    return attempt


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hash for a file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
