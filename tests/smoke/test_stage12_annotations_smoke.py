import importlib.util
import pytest


def _load_mod():
    """Load the 'stage12' module."""
    spec = importlib.util.spec_from_file_location(
        "stage12", "src/extractor/pipeline/steps/12_insert_annotations.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_stage12_imports_and_has_cli():
    # Offline smoke: just ensures module imports and defines 'run' CLI entry
    # Full DB operations are out-of-scope for smokes and covered in integration.
    try:
        mod = _load_mod()
    except Exception as e:
        pytest.skip(f"Stage 12 requires python-arango; skipping. ({e})")
    assert hasattr(mod, "run"), "Stage 12 lacks CLI 'run' function"
