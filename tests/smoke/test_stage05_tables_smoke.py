import importlib.util
import pytest


_has_deps = True
try:
    import fitz  # type: ignore  # noqa: F401
    import camelot  # type: ignore  # noqa: F401
except Exception:
    _has_deps = False


def _load_mod():
    """Load module from specified file path."""
    spec = importlib.util.spec_from_file_location(
        "stage05", "src/extractor/pipeline/steps/s05_table_extractor.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@pytest.mark.skipif(not _has_deps, reason="Stage 05 deps (PyMuPDF, camelot) not installed")
def test_camelot_strategy_callable():
    """Check for the existence of a callable strategy in the module."""
    mod = _load_mod()
    assert hasattr(mod, "try_camelot_strategy")
    # We only assert the function exists and returns a list when invoked with a dummy strategy
    # Actual PDF work is covered in integration runs; this keeps the smoke tiny and fast.
    fn = getattr(mod, "try_camelot_strategy")
    # Use an obviously invalid page to exercise error handling quickly
    out = fn(
        pdf_path=__file__, page_num=0, strategy={"flavor": "lattice", "params": {}}, diagnostics=[]
    )
    assert isinstance(out, list)


@pytest.mark.skipif(not _has_deps, reason="Stage 05 deps (PyMuPDF, camelot) not installed")
def test_quality_fallback_retries_fragmented_table(monkeypatch, tmp_path):
    """Ensure fragmentation triggers a fallback strategy that replaces the baseline result."""

    import pandas as pd

    mod = _load_mod()

    # Force low threshold so any fragmentation >0 retries
    monkeypatch.setattr(mod, "FRAGMENTATION_RETRY_THRESHOLD", 0)
    monkeypatch.setattr(mod, "FRAGMENTATION_IMPROVEMENT_MIN", 1)

    class FakeTable:
        def __init__(self, df, bbox):
            self.df = df
            self._bbox = bbox
            self.accuracy = 95.0
            self.whitespace = 0.1
            self.order = 1

    df_fragmented = pd.DataFrame([{"0": "Subsyste m", "1": "Value"}])
    df_clean = pd.DataFrame([{"0": "Subsystem", "1": "Value"}])

    call_log = []

    def fake_try(pdf_path, page_num, strategy, diagnostics):  # noqa: ANN001
        name = strategy.get("name")
        call_log.append(name)
        if name == "lattice_default":
            return [FakeTable(df_fragmented, (0.0, 0.0, 100.0, 100.0))]
        if name == "lattice_strong":
            return [FakeTable(df_clean, (0.0, 0.0, 100.0, 100.0))]
        return []

    monkeypatch.setattr(mod, "try_camelot_strategy", fake_try)
    monkeypatch.setattr(
        mod, "extract_table_image", lambda *args, **kwargs: str(tmp_path / "mock.png")
    )

    tables, best_strategy, durations, page_metrics = mod.extract_tables_from_page(
        pdf_path=tmp_path / "dummy.pdf",
        page_num=0,
        pdf_doc=None,
        output_dir=tmp_path,
        last_good_strategy=None,
        diagnostics=[],
    )

    # Baseline should run first, fallback second
    # Baseline should run first; fallback list should include lattice_strong eventually
    assert call_log[0] == "lattice_default"
    assert "lattice_strong" in call_log
    assert page_metrics["fallback_applied"] is True
    assert page_metrics["fallback_tables"] == 1
    assert best_strategy == "lattice_strong"

    assert len(tables) == 1
    table_payload = tables[0]
    assert table_payload["strategy"] == "lattice_strong"
    assert table_payload["quality_fallback"] is True
    history = table_payload.get("strategy_history", [])
    assert len(history) == 2
    assert history[0]["strategy"] == "lattice_default"
    assert history[1]["strategy"] == "lattice_strong"
