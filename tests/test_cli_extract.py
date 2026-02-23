import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import src.cli as cli
from extractor.core.schema.unified_document import (
    BaseBlock,
    BlockMetadata,
    BlockType,
    DocumentMetadata,
    HierarchyNode,
    UnifiedDocument,
)


runner = CliRunner()


def test_fast_pdf_creates_json(tmp_path: Path):
    fitz = pytest.importorskip("fitz", reason="PyMuPDF required for fast path")

    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "1. Heading\nhello")
    doc.save(pdf_path)
    doc.close()

    out_dir = tmp_path / "out"
    result = runner.invoke(
        cli.app, [str(pdf_path), str(out_dir), "--mode", "fast", "--fast-section"]
    )

    assert result.exit_code == 0, result.output
    out_file = out_dir / "sample_fast.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["pages"], "fast extractor should emit pages"
    assert data.get("fast_sections"), "fast sections should be present when enabled"


def test_structured_runs_with_stub_provider(tmp_path: Path, monkeypatch):
    # Dummy provider that returns a minimal UnifiedDocument
    class DummyProvider:
        def __init__(self, *_args, **_kwargs):
            pass

        def extract_document(self, path: str):
            block = BaseBlock(
                id="b1",
                parent_id=None,
                type=BlockType.PARAGRAPH,
                content="hello",
                metadata=BlockMetadata(),
            )
            return UnifiedDocument(
                id="doc1",
                source_type="html",
                source_path=path,
                blocks=[block],
                hierarchy=HierarchyNode(id="h1", block_id="b1", title="root", level=1, children=[]),
                metadata=DocumentMetadata(),
            )

    # Stub provider detection to avoid heavy dependencies
    monkeypatch.setattr(cli, "provider_from_filepath", lambda _p: DummyProvider)

    src = tmp_path / "page.html"
    src.write_text("<html><body>hello</body></html>")
    out_dir = tmp_path / "out"

    result = runner.invoke(cli.app, [str(src), str(out_dir)])

    assert result.exit_code == 0, result.output

    base = out_dir / src.stem
    reflow = base / "07_reflow_section" / "json_output" / "07_reflowed.json"
    flat = base / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    assert reflow.exists(), "reflow output missing"
    assert flat.exists(), "flattened output missing"
    # Check flattened data structure (block_id instead of id)
    flat_data = json.loads(flat.read_text())
    assert len(flat_data) >= 1, "should have at least one flattened entry"
    assert flat_data[0].get("block_id") == "b1" or "_key" in flat_data[0]
