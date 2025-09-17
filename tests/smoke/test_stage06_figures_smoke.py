import os
import importlib.util
from pathlib import Path
import pytest

_has_pymupdf = True
try:
    import fitz  # type: ignore  # noqa: F401
except Exception:
    _has_pymupdf = False


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        "stage06", "src/extractor/pipeline/steps/06_figure_extractor.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@pytest.mark.skipif(not _has_pymupdf, reason="PyMuPDF not installed")
@pytest.mark.asyncio
async def test_extract_and_describe_figure_offline(tmp_path):
    mod = _load_mod()
    fn = getattr(mod, "extract_and_describe_figure")

    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_marked.pdf").resolve()
    assert pdf_path.exists(), "Fixture PDF missing"
    # Minimal figure-like block
    block = {"page_idx": 0, "bbox": [50, 100, 200, 200]}
    out_dir = tmp_path / "figs"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = await fn(pdf_path, block, "fig-smoke", out_dir, skip_descriptions=True)
    assert result is not None
    assert (out_dir / "fig-smoke.png").exists(), "Image not saved"

