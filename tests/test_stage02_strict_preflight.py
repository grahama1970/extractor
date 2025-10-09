import io
from pathlib import Path

import fitz  # PyMuPDF
import importlib
import types
import pytest
import click


def _make_clean_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "clean.pdf"
    doc = fitz.open()
    try:
        doc.new_page(width=200, height=200)
        doc.save(p)
    finally:
        doc.close()
    return p


def test_stage02_preflight_fails_when_predictors_missing(monkeypatch, tmp_path):
    # Ensure module is freshly imported to pick up monkeypatch
    if "extractor.pipeline.steps.02_marker_extractor" in list(importlib.sys.modules.keys()):
        importlib.invalidate_caches()
        del importlib.sys.modules["extractor.pipeline.steps.02_marker_extractor"]

    # Patch extractor.core.models.create_model_dict to simulate missing predictors
    import extractor.core.models as core_models

    def fake_cmd():
        return {}  # missing all required keys

    monkeypatch.setattr(core_models, "create_model_dict", fake_cmd, raising=True)

    mod = importlib.import_module("extractor.pipeline.steps.02_marker_extractor")

    # Create a trivial clean PDF and expect run() to exit early due to preflight
    clean_pdf = _make_clean_pdf(tmp_path)

    with pytest.raises((SystemExit, click.exceptions.Exit)):
        mod.run(  # call the Typer command function directly
            pdf_path=clean_pdf,
            output_dir=tmp_path,
            timeout=5,
            debug=False,
            no_spawn=True,
            mark_all_headers_suspicious=False,
            output_suffix="",
        )
