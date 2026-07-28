"""Recovery and extraction must not mutate source bytes."""

from __future__ import annotations

from pathlib import Path

from extractor.application.extract_file import extract_file
from extractor.core.recovery import sha256_file


def test_canonical_extraction_preserves_source_bytes(tmp_path: Path) -> None:
    source = Path("data/input/twins/preset_twin/preset_twin.pdf")
    before = sha256_file(source)

    result = extract_file(source, output_dir=tmp_path, offline=True)

    assert result.status.value == "complete"
    assert sha256_file(source) == before
    assert result.source_sha256 == before
