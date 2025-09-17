import json
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from typer.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.slow
def test_debug_bundle_minimal_sections(tmp_path: Path, runner: CliRunner) -> None:
    from extractor.pipeline.steps import s04_section_builder as step

    # Create a minimal 1-page clean PDF
    clean_dir = tmp_path / "01_annotation_processor"
    clean_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = clean_dir / "test_clean.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)  # A4
    doc.save(str(pdf_path))
    doc.close()

    # Minimal verified blocks: one section header + one text block
    verified_blocks = {
        "blocks": [
            {
                "block_type": "SectionHeader",
                "text": "1. Introduction",
                "page_idx": 0,
                "bbox": [50, 50, 545, 100]
            },
            {
                "block_type": "Text",
                "text": "Hello world",
                "page_idx": 0,
                "bbox": [50, 120, 545, 200]
            }
        ]
    }

    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({
        "verified_blocks": verified_blocks,
        "clean_pdf": str(pdf_path),
    }))

    app = step.build_cli()
    res = runner.invoke(
        app,
        [
            "debug-bundle",
            str(bundle),
            "-o",
            str(tmp_path),
            "--fallback-heuristics",
            "--max-visual-pages",
            "0",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    out = tmp_path / "04_section_builder" / "json_output" / "04_sections.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert data.get("section_count", 0) >= 1

