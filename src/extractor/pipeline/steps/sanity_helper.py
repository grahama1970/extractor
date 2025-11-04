from __future__ import annotations

"""
Lightweight sanity runner for pipeline steps, designed for quick local debugging.

Usage (from a step's __main__):
    python -m extractor.pipeline.steps.04_section_builder sanity

This will run the minimal prerequisite chain against the default sample PDF and
write artifacts under data/results/pipeline. It returns the primary output path
for the requested step and raises on failure.
"""

from pathlib import Path
from typing import Tuple
import json


# Default sample PDF for sanity runs.
# Use the cleaned variant to align with gold expectations shared by the team.
DEFAULT_PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean.pdf")
RESULTS = Path("data/results/pipeline")


def _paths(base: Path) -> dict[str, Path]:
    return {
        "anno_dir": base / "01_annotation_processor",
        "blocks02": base / "02_marker_extractor" / "json_output" / "02_marker_blocks.json",
        "verified03": base / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json",
        "sections04": base / "04_section_builder" / "json_output" / "04_sections.json",
        "tables05": base / "05_table_extractor" / "json_output" / "05_tables.json",
        "figures06": base / "06_figure_extractor" / "json_output" / "06_figures.json",
        "reflow07": base / "07_reflow_section" / "json_output" / "07_reflowed.json",
    }


def _find_clean_pdf(anno_dir: Path) -> Path:
    for p in sorted(anno_dir.glob("*_clean.pdf")):
        return p
    raise FileNotFoundError(f"No '*_clean.pdf' found in {anno_dir}")


def sanity_run(step: str, pdf: Path = DEFAULT_PDF, out: Path = RESULTS) -> Path:
    """Run minimal prerequisite chain up to `step` and return that step's primary output path."""
    step = step.lower()
    out.mkdir(parents=True, exist_ok=True)
    p = _paths(out)

    # 01
    if step in {"01", "1", "01_annotation_processor", "s01_annotation_processor"}:
        from extractor.pipeline.steps import s01_annotation_processor as s01

        s01.run(pdf, out)
        return p["anno_dir"] / "json_output" / "01_annotations.json"

    # Ensure 01 exists for downstream steps
    if not p["anno_dir"].exists():
        from extractor.pipeline.steps import s01_annotation_processor as s01

        s01.run(pdf, out)
    clean_pdf = _find_clean_pdf(p["anno_dir"])

    # 02
    if step in {"02", "2", "02_marker_extractor", "s02_marker_extractor"}:
        from extractor.pipeline.steps import s02_marker_extractor as s02

        s02.run(clean_pdf, out)
        return p["blocks02"]
    if not p["blocks02"].exists():
        from extractor.pipeline.steps import s02_marker_extractor as s02

        s02.run(clean_pdf, out)

    # 03
    if step in {"03", "3", "03_suspicious_headers", "s03_suspicious_headers"}:
        from extractor.pipeline.steps import s03_suspicious_headers as s03

        s03.run(p["blocks02"], p["anno_dir"], out)
        return p["verified03"]
    if not p["verified03"].exists():
        from extractor.pipeline.steps import s03_suspicious_headers as s03

        s03.run(p["blocks02"], p["anno_dir"], out)

    # 04
    if step in {"04", "4", "04_section_builder", "s04_section_builder"}:
        from extractor.pipeline.steps import s04_section_builder as s04

        return s04.run(p["verified03"], p["anno_dir"], out)
    if not p["sections04"].exists():
        from extractor.pipeline.steps import s04_section_builder as s04

        s04.run(p["verified03"], p["anno_dir"], out)

    # 05
    if step in {"05", "5", "05_table_extractor", "s05_table_extractor"}:
        from extractor.pipeline.steps import s05_table_extractor as s05

        out_path = s05.run(p["sections04"], pdf_dir=p["anno_dir"], output_dir=out)
        # Basic sanity: file readable + has a tables array. Leave exact counts to invariants.
        try:
            data = json.loads(Path(out_path).read_text())
            tables = data.get("tables") or []
            print(f"[sanity 05] tables={len(tables)} → {out_path}")
        except Exception:
            print(f"[sanity 05] Failed to read tables JSON → {out_path}")
            raise SystemExit(1)
        return out_path
    if not p["tables05"].exists():
        from extractor.pipeline.steps import s05_table_extractor as s05

        s05.run(p["sections04"], pdf_dir=p["anno_dir"], output_dir=out)

    # 06
    if step in {"06", "6", "06_figure_extractor", "s06_figure_extractor"}:
        from extractor.pipeline.steps import s06_figure_extractor as s06

        out_path = s06.run(
            stage_02_json=p["blocks02"],
            stage_04_json=p["sections04"],
            pdf_dir=p["anno_dir"],
            output_dir=out,
            skip_descriptions=True,
        )
        # Deterministic invariant for reference PDF: exactly 1 figure
        try:
            data = json.loads(Path(out_path).read_text())
            figures = data.get("figures") or []
            # Clean PDF expectation: exactly one figure
            expected = 1
            if len(figures) != expected:
                print(f"[sanity 06] Expected {expected} figure, found {len(figures)} → {out_path}")
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception:
            print(f"[sanity 06] Failed to read figures JSON → {out_path}")
            raise SystemExit(1)
        return out_path
    if not p["figures06"].exists():
        from extractor.pipeline.steps import s06_figure_extractor as s06

        s06.run(
            stage_02_json=p["blocks02"],
            stage_04_json=p["sections04"],
            pdf_dir=p["anno_dir"],
            output_dir=out,
            skip_descriptions=True,
        )

    # 07
    if step in {"07", "7", "07_reflow_section", "s07_reflow_section"}:
        from extractor.pipeline.steps import s07_reflow_section as s07

        return s07.run(
            sections_json=p["sections04"],
            tables_json=p["tables05"],
            figures_json=p["figures06"],
            annotations_json=(p["anno_dir"] / "json_output" / "01_annotations.json"),
            output_dir=out,
            summary_only=True,
        )
    if not p["reflow07"].exists():
        from extractor.pipeline.steps import s07_reflow_section as s07

        s07.run(
            sections_json=p["sections04"],
            tables_json=p["tables05"],
            figures_json=p["figures06"],
            annotations_json=(p["anno_dir"] / "json_output" / "01_annotations.json"),
            output_dir=out,
            summary_only=True,
        )

    # 09a
    if step in {"09a", "09a_pdf_annotator", "s09a_pdf_annotator"}:
        from extractor.pipeline.steps import s09a_pdf_annotator as s09a

        return s09a.run(
            pdf_path=_find_clean_pdf(p["anno_dir"]),
            sections_json=p["sections04"],
            tables_json=p["tables05"],
            figures_json=p["figures06"],
            reflowed_json=p["reflow07"],
            output_dir=out,
            labels=True,
            render_previews=False,
        )

    raise ValueError(f"Unsupported step for sanity: {step}")
