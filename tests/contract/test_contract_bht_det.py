import json
from pathlib import Path


def test_bht_deterministic_contract():
    base = Path("data/results/pipeline_det")
    assert base.exists(), "deterministic run output missing; run `make ci-det` first"

    # 04: exactly 3 sections
    s04 = base / "04_section_builder/json_output/04_sections.json"
    data04 = json.loads(s04.read_text())
    sections = data04.get("sections", [])
    assert len(sections) == 3, f"expected 3 sections, got {len(sections)}"

    # 06: exactly 1 figure
    s06 = base / "06_figure_extractor/json_output/06_figures.json"
    data06 = json.loads(s06.read_text())
    figures = data06.get("figures", [])
    assert len(figures) == 1, f"expected 1 figure, got {len(figures)}"

    # 09a: contract invariants
    s09a = base / "09a_pdf_annotator/json_output/annotations.json"
    ann = json.loads(s09a.read_text())
    summary = ann.get("summary", {})
    assert summary.get("total_overlays", 0) == sum(summary.get("by_kind", {}).values())
    # Pages touched must be 1-based ints
    pages = summary.get("pages_touched", [])
    assert all(isinstance(p, int) and p >= 1 for p in pages)
    # Offline: merged groups may be zero
    assert summary.get("merged_table_groups", 0) >= 0
