import importlib.util
import pytest


_has_deps = True
try:
    import fitz  # type: ignore  # noqa: F401
    import camelot  # type: ignore  # noqa: F401
except Exception:
    _has_deps = False


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        "stage05", "src/extractor/pipeline/steps/05_table_extractor.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@pytest.mark.skipif(not _has_deps, reason="Stage 05 deps (PyMuPDF, camelot) not installed")
def test_camelot_strategy_callable():
    mod = _load_mod()
    assert hasattr(mod, "try_camelot_strategy")
    # We only assert the function exists and returns a list when invoked with a dummy strategy
    # Actual PDF work is covered in integration runs; this keeps the smoke tiny and fast.
    fn = getattr(mod, "try_camelot_strategy")
    # Use an obviously invalid page to exercise error handling quickly
    out = fn(pdf_path=__file__, page_num=0, strategy={"flavor": "lattice", "params": {}}, diagnostics=[])
    assert isinstance(out, list)

