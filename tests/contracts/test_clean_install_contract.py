"""Contracts for the clean-install CI entrypoint."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ci_core_script_is_blocking_and_artifact_backed() -> None:
    script = ROOT / "scripts/ci_core.sh"
    text = script.read_text(encoding="utf-8")

    assert "set -euo pipefail" in text
    assert "uv sync --frozen --group dev" in text
    assert "uv run pytest --collect-only -q" in text
    assert "uv build --wheel" in text
    assert "python -m venv" in text
    assert "pip install dist/extractor-*.whl" in text
    assert "EXTRACTOR_COMMAND=" in text
    assert "extractor.result.v1" in text
    assert "|| true" not in text


def test_ci_workflows_do_not_mask_core_correctness_failures() -> None:
    for relative in [".github/workflows/python.yml", ".github/workflows/extractor-lint.yml"]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "|| true" not in text, relative
        assert "scripts/ci_core.sh" in text, relative
