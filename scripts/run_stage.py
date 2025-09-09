#!/usr/bin/env python3
"""
Minimal single-stage runner for pipeline stages 01–07.

Usage examples:
  # Run Stage 01 (requires --pdf)
  python scripts/run_stage.py 01 --pdf src/extractor/pipeline/poc_simplified/input/BHT_CV32A65X_marked.pdf

  # Run Stage 07 (assumes you already have 04/05/06 outputs; auto-discovers 01 annotations if present)
  python scripts/run_stage.py 07
"""
import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPE_DIR = ROOT / "src" / "extractor" / "pipeline" / "poc_simplified" / "pipeline"
RESULTS_BASE = ROOT / "src" / "extractor" / "pipeline" / "poc_simplified" / "results"


def run(cmd: list[str]) -> None:
    print(">>", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def stage01(pdf: Path) -> Path:
    outdir = RESULTS_BASE
    run([sys.executable, str(PIPE_DIR / "01_annotation_processor.py"), "run", str(pdf), "-o", str(outdir)])
    artifact = outdir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    if not artifact.exists():
        raise SystemExit("Stage 01 artifact missing")
    print(f"OK Stage 01 -> {artifact}")
    return artifact


def stage02() -> Path:
    outdir = RESULTS_BASE
    clean_pdfs = list((outdir / "01_annotation_processor").glob("*_clean.pdf"))
    if not clean_pdfs:
        raise SystemExit("No '*_clean.pdf' found from Stage 01; run Stage 01 first")
    clean_pdf = clean_pdfs[0]
    run([sys.executable, str(PIPE_DIR / "02_marker_extractor.py"), "run", str(clean_pdf), "-o", str(outdir)])
    artifact = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    if not artifact.exists():
        raise SystemExit("Stage 02 artifact missing")
    print(f"OK Stage 02 -> {artifact}")
    return artifact


def stage03() -> Path:
    outdir = RESULTS_BASE
    s02 = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    if not s02.exists():
        raise SystemExit("Need Stage 02 output")
    run([
        sys.executable, str(PIPE_DIR / "03_suspicious_headers.py"),
        "run", str(s02), "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    if not artifact.exists():
        raise SystemExit("Stage 03 artifact missing")
    print(f"OK Stage 03 -> {artifact}")
    return artifact


def stage04() -> Path:
    outdir = RESULTS_BASE
    s03 = outdir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    if not s03.exists():
        raise SystemExit("Need Stage 03 output")
    run([
        sys.executable, str(PIPE_DIR / "04_section_builder.py"),
        "run", str(s03), "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    if not artifact.exists():
        raise SystemExit("Stage 04 artifact missing")
    print(f"OK Stage 04 -> {artifact}")
    return artifact


def stage05() -> Path:
    outdir = RESULTS_BASE
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    if not s04.exists():
        raise SystemExit("Need Stage 04 output")
    run([
        sys.executable, str(PIPE_DIR / "05_table_extractor.py"),
        "run", str(s04), "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "05_table_extractor" / "json_output" / "05_tables.json"
    if not artifact.exists():
        raise SystemExit("Stage 05 artifact missing")
    print(f"OK Stage 05 -> {artifact}")
    return artifact


def stage06() -> Path:
    outdir = RESULTS_BASE
    s02 = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    if not s02.exists() or not s04.exists():
        raise SystemExit("Need Stage 02 and 04 outputs")
    run([
        sys.executable, str(PIPE_DIR / "06_figure_extractor.py"),
        "run", str(s02), "--sections", str(s04),
        "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "06_figure_extractor" / "json_output" / "06_figures.json"
    if not artifact.exists():
        raise SystemExit("Stage 06 artifact missing")
    print(f"OK Stage 06 -> {artifact}")
    return artifact


def stage07() -> Path:
    outdir = RESULTS_BASE
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    s05 = outdir / "05_table_extractor" / "json_output" / "05_tables.json"
    s06 = outdir / "06_figure_extractor" / "json_output" / "06_figures.json"
    s01 = outdir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    for p in (s04, s05, s06):
        if not p.exists():
            raise SystemExit("Need Stage 04, 05, 06 outputs")
    cmd = [
        sys.executable, str(PIPE_DIR / "07_reflow_section.py"),
        "run", "--sections", str(s04), "--tables", str(s05), "--figures", str(s06),
        "-o", str(outdir),
    ]
    if s01.exists():
        cmd += ["--annotations", str(s01)]
    run(cmd)
    artifact = outdir / "07_reflow_section" / "json_output" / "07_reflowed.json"
    if not artifact.exists():
        raise SystemExit("Stage 07 artifact missing")
    print(f"OK Stage 07 -> {artifact}")
    return artifact


def main():
    ap = argparse.ArgumentParser(description="Run a single pipeline stage (01–07).")
    ap.add_argument("stage", choices=["01", "02", "03", "04", "05", "06", "07"], help="Stage number to run")
    ap.add_argument("--pdf", default="", help="Path to input PDF (required for Stage 01)")
    args = ap.parse_args()

    if args.stage == "01":
        pdf = Path(args.pdf)
        if not pdf.exists():
            raise SystemExit("Provide --pdf for Stage 01 and ensure it exists")
        stage01(pdf)
    elif args.stage == "02":
        stage02()
    elif args.stage == "03":
        stage03()
    elif args.stage == "04":
        stage04()
    elif args.stage == "05":
        stage05()
    elif args.stage == "06":
        stage06()
    elif args.stage == "07":
        stage07()
    else:
        raise SystemExit(f"Unknown stage {args.stage}")


if __name__ == "__main__":
    main()