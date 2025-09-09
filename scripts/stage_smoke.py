#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


# Repo root and results base
ROOT = Path(__file__).resolve().parents[2]
RESULTS_BASE = ROOT / "src" / "extractor" / "pipeline" / "poc_simplified" / "results"


def run(cmd: List[str]) -> None:
    print(">>", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def stage01(pdf: Path):
    """Run Stage 01: 01_annotation_processor.py"""
    outdir = RESULTS_BASE
    run(
        [
            sys.executable,
            str(
                ROOT
                / "src"
                / "extractor"
                / "pipeline"
                / "poc_simplified"
                / "pipeline"
                / "01_annotation_processor.py"
            ),
            "run",
            str(pdf),
            "-o",
            str(outdir),
        ]
    )
    artifact = outdir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    assert artifact.exists(), "Stage 01 artifact missing"


def stage02():
    """Run Stage 02: 02_marker_extractor.py"""
    outdir = RESULTS_BASE
    clean_pdfs = list((outdir / "01_annotation_processor").glob("*_clean.pdf"))
    assert clean_pdfs, "No '*_clean.pdf' found from Stage 01"
    clean_pdf = clean_pdfs[0]
    run(
        [
            sys.executable,
            str(
                ROOT
                / "src"
                / "extractor"
                / "pipeline"
                / "poc_simplified"
                / "pipeline"
                / "02_marker_extractor.py"
            ),
            "run",
            str(clean_pdf),
            "-o",
            str(outdir),
        ]
    )
    artifact = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    assert artifact.exists(), "Stage 02 artifact missing"


def stage03():
    """Run Stage 03: 03_suspicious_headers.py"""
    outdir = RESULTS_BASE
    marker_json = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    assert marker_json.exists(), "Need Stage 02 output"
    run(
        [
            sys.executable,
            str(
                ROOT
                / "src"
                / "extractor"
                / "pipeline"
                / "poc_simplified"
                / "pipeline"
                / "03_suspicious_headers.py"
            ),
            "run",
            str(marker_json),
            "--pdf-dir",
            str(outdir / "01_annotation_processor"),
            "-o",
            str(outdir),
        ]
    )
    artifact = outdir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    assert artifact.exists(), "Stage 03 artifact missing"


def stage04():
    """Run Stage 04: 04_section_builder.py"""
    outdir = RESULTS_BASE
    verified_json = outdir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    assert verified_json.exists(), "Need Stage 03 output"
    run(
        [
            sys.executable,
            str(
                ROOT
                / "src"
                / "extractor"
                / "pipeline"
                / "poc_simplified"
                / "pipeline"
                / "04_section_builder.py"
            ),
            "run",
            str(verified_json),
            "--pdf-dir",
            str(outdir / "01_annotation_processor"),
            "-o",
            str(outdir),
        ]
    )
    artifact = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    assert artifact.exists(), "Stage 04 artifact missing"


def stage05():
    """Run Stage 05: 05_table_extractor.py"""
    outdir = RESULTS_BASE
    sections_json = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    assert sections_json.exists(), "Need Stage 04 output"
    run(
        [
            sys.executable,
            str(
                ROOT
                / "src"
                / "extractor"
                / "pipeline"
                / "poc_simplified"
                / "pipeline"
                / "05_table_extractor.py"
            ),
            "run",
            str(sections_json),
            "--pdf-dir",
            str(outdir / "01_annotation_processor"),
            "-o",
            str(outdir),
        ]
    )
    artifact = outdir / "05_table_extractor" / "json_output" / "05_tables.json"
    assert artifact.exists(), "Stage 05 artifact missing"


def stage06():
    """Run Stage 06: 06_figure_extractor.py"""
    outdir = RESULTS_BASE
    stage02_json = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    stage04_json = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    assert stage02_json.exists() and stage04_json.exists(), "Need Stage 02 and 04 outputs"
    run(
        [
            sys.executable,
            str(
                ROOT
                / "src"
                / "extractor"
                / "pipeline"
                / "poc_simplified"
                / "pipeline"
                / "06_figure_extractor.py"
            ),
            "run",
            str(stage02_json),
            "--sections",
            str(stage04_json),
            "--pdf-dir",
            str(outdir / "01_annotation_processor"),
            "-o",
            str(outdir),
        ]
    )
    artifact = outdir / "06_figure_extractor" / "json_output" / "06_figures.json"
    assert artifact.exists(), "Stage 06 artifact missing"


def stage07():
    """Run Stage 07: 07_reflow_section.py"""
    outdir = RESULTS_BASE
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    s05 = outdir / "05_table_extractor" / "json_output" / "05_tables.json"
    s06 = outdir / "06_figure_extractor" / "json_output" / "06_figures.json"
    s01 = outdir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    for p in [s04, s05, s06]:
        assert p.exists(), "Need Stage 04, 05, 06 outputs"
    cmd = [
        sys.executable,
        str(
            ROOT
            / "src"
            / "extractor"
            / "pipeline"
            / "poc_simplified"
            / "pipeline"
            / "07_reflow_section.py"
        ),
        "run",
        "--sections",
        str(s04),
        "--tables",
        str(s05),
        "--figures",
        str(s06),
        "-o",
        str(outdir),
    ]
    if s01.exists():
        cmd += ["--annotations", str(s01)]
    run(cmd)
    artifact = outdir / "07_reflow_section" / "json_output" / "07_reflowed.json"
    assert artifact.exists(), "Stage 07 artifact missing"


def main():
    ap = argparse.ArgumentParser(description="Run smoke checks for pipeline stages 01–07.")
    ap.add_argument(
        "--stages",
        required=True,
        help='Space-separated list like "01 02 03 04 05 06 07"',
    )
    ap.add_argument(
        "--pdf",
        default="",
        help="Path to input PDF for Stage 01 (required if '01' included).",
    )
    args = ap.parse_args()

    order = args.stages.split()
    pdf_path = Path(args.pdf) if args.pdf else None

    for s in order:
        if s == "01":
            assert pdf_path and pdf_path.exists(), "Provide --pdf for Stage 01"
            stage01(pdf_path)
        elif s == "02":
            stage02()
        elif s == "03":
            stage03()
        elif s == "04":
            stage04()
        elif s == "05":
            stage05()
        elif s == "06":
            stage06()
        elif s == "07":
            stage07()
        else:
            raise SystemExit(f"Unknown stage '{s}'")

    print("Smoke OK for stages:", " ".join(order))


if __name__ == "__main__":
    main()