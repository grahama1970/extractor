import json
from pathlib import Path

import pytest

from extractor.pipeline.steps import s03_suspicious_headers as stage03


@pytest.fixture()
def tmp_pdf_dir(tmp_path: Path) -> Path:
    # Stage 03.skip_llm still resolves a *_clean.pdf; create a tiny placeholder.
    pdf_dir = tmp_path
    (pdf_dir / "dummy_clean.pdf").write_text("%PDF-1.4\n%EOF\n", encoding="utf-8")
    return pdf_dir


def _run_stage(tmp_path: Path, blocks: list[dict]) -> dict:
    input_json = tmp_path / "02_marker_blocks.json"
    input_json.write_text(json.dumps({"blocks": blocks}, indent=2))
    out_dir = tmp_path / "out"
    out = stage03.run(
        input_json=input_json,
        pdf_dir=tmp_path,
        output_dir=out_dir,
        skip_llm=True,
    )
    return json.loads(out.read_text())


def test_bullet_header_demoted_offline(tmp_path: Path, tmp_pdf_dir: Path):
    blocks = [
        {
            "block_type": "SectionHeader",
            "text": "• flush_bp_i input is tied to 0",
            "bbox": [0, 0, 10, 10],
            "suspicious_header": True,
        }
    ]
    data = _run_stage(tmp_path, blocks)
    b = data["blocks"][0]
    assert b["block_type"] == "Text"
    assert b.get("is_suspicious") is True
    assert any("bullet" in str(r) for r in b.get("suspicious_reasons", []))


def test_numbered_header_kept_offline(tmp_path: Path, tmp_pdf_dir: Path):
    blocks = [
        {
            "block_type": "SectionHeader",
            "text": "4.1.5. Title Line",
            "bbox": [0, 0, 10, 10],
            "suspicious_header": True,
        }
    ]
    data = _run_stage(tmp_path, blocks)
    b = data["blocks"][0]
    assert b["block_type"] == "SectionHeader"
    assert b.get("is_suspicious") is False or b.get("is_suspicious") is None
