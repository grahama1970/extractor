import importlib.util
import importlib
import pytest
from pathlib import Path


def _load_stage01_module() -> object:
    """Dynamically load stage 01 module since filename starts with digits."""
    file_path = Path("src/extractor/pipeline/steps/s01_annotation_processor.py").resolve()
    assert file_path.exists(), f"Missing Stage 01 script at {file_path}"
    spec = importlib.util.spec_from_file_location("stage01_module", str(file_path))
    assert spec and spec.loader, "Failed to load spec for Stage 01"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


_has_tenacity = True
_has_pymupdf = True
try:
    import tenacity  # type: ignore  # noqa: F401
except Exception:
    _has_tenacity = False
try:
    import fitz  # type: ignore  # noqa: F401
except Exception:
    _has_pymupdf = False


@pytest.mark.skipif(not _has_tenacity, reason="tenacity not installed")
@pytest.mark.skipif(not _has_pymupdf, reason="PyMuPDF not installed")
def test_stage01_saves_images_and_clean_pdf(tmp_path):
    """Test image saving and PDF cleaning functionality in stage one."""
    mod = _load_stage01_module()

    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_marked.pdf").resolve()
    assert pdf_path.exists(), f"Fixture PDF missing: {pdf_path}"

    # Stage output under temp dir (does not run full pipeline to avoid LLM)
    stage_dir = tmp_path / "pipeline" / "01_annotation_processor"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # Build minimal config for helpers
    Config = getattr(mod, "Config")
    cfg = Config(
        input_pdf=pdf_path,
        output_dir=stage_dir,
        include_freetext=True,  # include FreeText notes for richer coverage
        use_images=False,
        render_dpi=120,
        llm_model="dummy/model",  # unused in this smoke path
        llm_concurrency=1,
        limit_annotations=0,
        max_runtime_seconds=0,
        debug=False,
        cache=False,
    )

    # Call the extraction helper directly (no LLM calls)
    extract_annotations_data = getattr(mod, "extract_annotations_data")
    annotations = extract_annotations_data(pdf_path, cfg)

    # Expect at least one annotation and saved images
    assert isinstance(annotations, list)
    assert len(annotations) > 0, "Expected at least one annotation from fixture PDF"
    img_dir = stage_dir / "visual_output"
    assert img_dir.exists(), "visual_output directory not created"
    assert any(img_dir.iterdir()), "No images saved for annotations"

    # Create the clean PDF and verify it exists
    create_clean_pdf = getattr(mod, "create_clean_pdf")
    clean_pdf = Path(create_clean_pdf(pdf_path, stage_dir))
    assert clean_pdf.exists(), "Clean PDF not created"

    # Spot-check a couple of computed fields to ensure context processing ran
    a0 = annotations[0]
    assert "computed_features" in a0
    assert "relevant_to" in a0
