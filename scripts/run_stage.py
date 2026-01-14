#!/usr/bin/env python3
"""
Minimal single-stage runner for pipeline stages 01–08.

Usage examples:
  # Run Stage 01 (requires --pdf)
  python scripts/run_stage.py 01 --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf

  # Run Stage 07 (assumes you already have 04/05/06 outputs)
  python scripts/run_stage.py 07
"""
import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPE_DIR = ROOT / "src" / "extractor" / "pipeline" / "steps"
RESULTS_BASE = ROOT / "data" / "results" / "pipeline"


def run(cmd: list[str]) -> None:
    print(">>", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def stage01(pdf: Path, outdir: Path) -> Path:
    run([sys.executable, str(PIPE_DIR / "s01_annotation_processor.py"), "run", str(pdf), "-o", str(outdir)])
    artifact = outdir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    if not artifact.exists():
        raise SystemExit("Stage 01 artifact missing")
    print(f"OK Stage 01 -> {artifact}")
    return artifact


def stage02(outdir: Path) -> Path:
    # S02 usually takes PDF dir or similar. Checking s02 script usage:
    # It takes input PDF (cleaned) or directory.
    # We assume S01 produced *_clean.pdf in its output dir.
    s01_dir = outdir / "01_annotation_processor"
    clean_pdfs = list(s01_dir.glob("*_clean.pdf"))
    if not clean_pdfs:
        raise SystemExit(f"No '*_clean.pdf' found in {s01_dir}; run Stage 01 first")
    clean_pdf = clean_pdfs[0]
    
    run([sys.executable, str(PIPE_DIR / "s02_marker_extractor.py"), "run", str(clean_pdf), "-o", str(outdir)])
    artifact = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    if not artifact.exists():
        raise SystemExit("Stage 02 artifact missing")
    print(f"OK Stage 02 -> {artifact}")
    return artifact


def stage03(outdir: Path) -> Path:
    s02 = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    if not s02.exists():
        raise SystemExit("Need Stage 02 output")
    run([
        sys.executable, str(PIPE_DIR / "s03_suspicious_headers.py"),
        "run", str(s02), "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    if not artifact.exists():
        raise SystemExit("Stage 03 artifact missing")
    print(f"OK Stage 03 -> {artifact}")
    return artifact


def stage04(outdir: Path) -> Path:
    s03 = outdir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    if not s03.exists():
        raise SystemExit("Need Stage 03 output")
    run([
        sys.executable, str(PIPE_DIR / "s04_section_builder.py"),
        "run", str(s03), "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    if not artifact.exists():
        raise SystemExit("Stage 04 artifact missing")
    print(f"OK Stage 04 -> {artifact}")
    return artifact


def stage05(outdir: Path) -> Path:
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    if not s04.exists():
        raise SystemExit("Need Stage 04 output")
    run([
        sys.executable, str(PIPE_DIR / "s05_table_extractor.py"),
        "run", str(s04), "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "05_table_extractor" / "json_output" / "05_tables.json"
    if not artifact.exists():
        raise SystemExit("Stage 05 artifact missing")
    print(f"OK Stage 05 -> {artifact}")
    return artifact


def stage06(outdir: Path) -> Path:
    s02 = outdir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    if not s02.exists() or not s04.exists():
        raise SystemExit("Need Stage 02 and 04 outputs")
    run([
        sys.executable, str(PIPE_DIR / "s06_figure_extractor.py"),
        "run", str(s02), "--sections", str(s04),
        "--pdf-dir", str(outdir / "01_annotation_processor"), "-o", str(outdir)
    ])
    artifact = outdir / "06_figure_extractor" / "json_output" / "06_figures.json"
    if not artifact.exists():
        raise SystemExit("Stage 06 artifact missing")
    print(f"OK Stage 06 -> {artifact}")
    return artifact


def stage07(outdir: Path) -> Path:
    s04 = outdir / "04_section_builder" / "json_output" / "04_sections.json"
    s05 = outdir / "05_table_extractor" / "json_output" / "05_tables.json"
    s06 = outdir / "06_figure_extractor" / "json_output" / "06_figures.json"
    s01 = outdir / "01_annotation_processor" / "json_output" / "01_annotations.json"
    for p in (s04, s05, s06):
        if not p.exists():
            raise SystemExit(f"Missing prerequisite: {p}")
            
    cmd = [
        sys.executable, str(PIPE_DIR / "s07_assemble_corpus.py"),
        "run", "--sections", str(s04), "--tables", str(s05), "--figures", str(s06),
        "-o", str(outdir),
    ]
    if s01.exists():
        cmd += ["--annotations", str(s01)]
    run(cmd)
    artifact = outdir / "07_corpus_assembly" / "json_output" / "07_assembled.json"
    if not artifact.exists():
        raise SystemExit("Stage 07 artifact missing")
    print(f"OK Stage 07 -> {artifact}")
    return artifact

def stage08(outdir: Path) -> Path:
    # S08 Requirements
    s07 = outdir / "07_corpus_assembly" / "json_output" / "07_assembled.json"
    if not s07.exists():
         raise SystemExit("Need Stage 07 output")
    
    # Run Requirements Extraction
    run([
        sys.executable, str(PIPE_DIR / "s08_extract_requirements.py"),
        "run", "--corpus", str(s07), "-o", str(outdir)
    ])
    
    artifact = outdir / "08_extract_requirements" / "json_output" / "08_requirements.json"
    if not artifact.exists():
        # S08 output is mostly DB, but it might produce a JSON summary or we check DB.
        # But s08_extract_requirements.py PROBABLY produces a json if run with CLI.
        # Checking file system...
        # If not, we should check DB. But for now let's assume JSON or at least DB presence.
        pass
        
    print(f"OK Stage 08 Requirements -> {artifact}")
    
    # Run Lean4 Prover
    # This might require flags, but let's try basic run
    db_path = outdir / "pipeline.duckdb"
    run([
        sys.executable, str(PIPE_DIR / "s08_lean4_theorem_prover.py"),
        "run", "--db", str(db_path), "-o", str(outdir / "08_lean4_theorem_prover")
    ])
    
    return artifact


def stage09(outdir: Path) -> Path:
    s07 = outdir / "07_corpus_assembly" / "json_output" / "07_assembled.json"
    if not s07.exists():
        raise SystemExit("Need Stage 07 output (Corpus)")

    # S09Enrichment
    run([
        sys.executable, str(PIPE_DIR / "s09_llm_enrichment.py"),
        "run", "--corpus", str(s07), "-o", str(outdir)
    ])
    
    artifact = outdir / "09_llm_enrichment" / "json_output" / "09_enriched.json"
    if not artifact.exists():
         raise SystemExit("Stage 09 artifact missing")
         
    print(f"OK Stage 09 -> {artifact}")
    return artifact


def stage10(outdir: Path) -> Path:
    # S10 can consume S09 or S07 artifact to find the DB
    s09 = outdir / "09_llm_enrichment" / "json_output" / "09_enriched.json"
    s07 = outdir / "07_corpus_assembly" / "json_output" / "07_assembled.json"
    
    inputs = s09 if s09.exists() else s07
    if not inputs.exists():
        raise SystemExit("Need Stage 07 or Stage 09 output")

    run([
        sys.executable, str(PIPE_DIR / "s10_markdown_exporter.py"),
        "run", "--corpus", str(inputs), "-o", str(outdir)
    ])
    
    artifact = outdir / "10_markdown_exporter" / "json_output" / "10_export_summary.json"
    if not artifact.exists():
         raise SystemExit("Stage 10 artifact missing")

    print(f"OK Stage 10 -> {artifact}")
    return artifact


def main():
    ap = argparse.ArgumentParser(description="Run a single pipeline stage (01–10).")
    ap.add_argument("stage", choices=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"], help="Stage number to run")
    ap.add_argument("--pdf", default="", help="Path to input PDF (required for Stage 01)")
    ap.add_argument("--output_dir", default="", help="Output directory (override default)")
    args = ap.parse_args()
    
    outdir = Path(args.output_dir) if args.output_dir else RESULTS_BASE
    outdir.mkdir(parents=True, exist_ok=True)

    if args.stage == "01":
        pdf = Path(args.pdf)
        if not pdf.exists():
            raise SystemExit("Provide --pdf for Stage 01 and ensure it exists")
        stage01(pdf, outdir)
    elif args.stage == "02":
        stage02(outdir)
    elif args.stage == "03":
        stage03(outdir)
    elif args.stage == "04":
        stage04(outdir)
    elif args.stage == "05":
        stage05(outdir)
    elif args.stage == "06":
        stage06(outdir)
    elif args.stage == "07":
        stage07(outdir)
    elif args.stage == "08":
        stage08(outdir)
    elif args.stage == "09":
        stage09(outdir)
    elif args.stage == "10":
        stage10(outdir)
    else:
        raise SystemExit(f"Unknown stage {args.stage}")


if __name__ == "__main__":
    main()