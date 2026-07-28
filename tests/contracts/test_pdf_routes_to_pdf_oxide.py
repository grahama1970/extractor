"""Contract tests proving canonical PDFs route through pdf_oxide."""

from __future__ import annotations

import tomllib
from pathlib import Path

from extractor.application.extract_file import PDF_OXIDE_PIN, extract_file


PDF_FIXTURE = Path("data/input/twins/preset_twin/preset_twin.pdf")


def test_pdf_route_records_pdf_oxide_engine_and_pin(tmp_path: Path) -> None:
    result = extract_file(PDF_FIXTURE, output_dir=tmp_path, offline=True)

    assert result.status.value == "complete"
    assert result.detected_format == "pdf"
    assert result.diagnostics.engine == "pdf_oxide"
    assert result.diagnostics.provider == "PdfProvider"
    assert result.diagnostics.extra["pdf_oxide_dependency_pin"] == PDF_OXIDE_PIN
    assert result.diagnostics.extra["pdf_oxide_version"]
    assert result.counts.blocks > 0


def test_pdf_oxide_dependency_is_pinned_to_immutable_commit() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    deps = project["project"]["dependencies"]
    matches = [dep for dep in deps if dep.startswith("pdf_oxide @ ")]

    assert matches == [
        f"pdf_oxide @ git+https://github.com/grahama1970/pdf_oxide.git@{PDF_OXIDE_PIN}"
    ]
