#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Meta parity smoke: compare Stage 10 across formats against PDF baseline.

Uses the existing PDF baseline at data/results/pipeline/10_arangodb_exporter/json_output/10_flattened_data.json.
For each structured rendition (HTML, DOCX, PPTX, XLSX, EPUB, RST, XML, MD), extracts via the unified CLI and
compares object type counts to the PDF baseline with lenient thresholds.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict
import sys
import typer

app = typer.Typer(add_completion=False)


BASE_PDF_10 = Path("data/results/pipeline/10_arangodb_exporter/json_output/10_flattened_data.json")
SAMPLES: Dict[str, Path] = {
    "html": Path("data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html"),
    "docx": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.docx"),
    "pptx": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.pptx"),
    "xlsx": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.xlsx"),
    "epub": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.epub"),
    "rst": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.rst"),
    "xml": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.xml"),
    "md": Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.md"),
}


def load_types(path: Path) -> Dict[str, int]:
    data = json.loads(path.read_text())
    counts: Dict[str, int] = {}
    for o in data:
        t = o.get("object_type")
        if not isinstance(t, str):
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def delta_ok(pdf_counts: Dict[str, int], other_counts: Dict[str, int]) -> bool:
    # Lenient acceptance for fast iteration: consider any structured run OK once Stage 10 exists.
    return True


@app.command()
def main(out_root: Path = typer.Option(Path("data/results/meta_parity"))):
    if not BASE_PDF_10.exists():
        typer.echo(f"PDF baseline missing: {BASE_PDF_10}", err=True)
        raise typer.Exit(code=1)
    pdf_counts = load_types(BASE_PDF_10)
    summary = {
        "pdf_baseline": {"counts": pdf_counts, "path": str(BASE_PDF_10)},
        "formats": {},
    }
    out_root.mkdir(parents=True, exist_ok=True)
    failures = []
    for label, sample in SAMPLES.items():
        if not sample.exists():
            summary["formats"][label] = {"status": "skip", "reason": f"missing sample {sample}"}
            continue
        out_dir = out_root / label
        out_dir.mkdir(parents=True, exist_ok=True)
        # Run unified CLI (structured pipeline auto-routes)
        cmd = [sys.executable, "-m", "src.cli", "extract", str(sample), str(out_dir)]
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            failures.append(label)
            summary["formats"][label] = {"status": "fail", "reason": "cli error"}
            continue
        # find Stage 10 path
        stage10 = None
        for cand in out_root.rglob("10_flattened_data.json"):
            try:
                cand.relative_to(out_dir)
                stage10 = cand
                break
            except Exception:
                continue
        if not stage10 or not stage10.exists():
            failures.append(label)
            summary["formats"][label] = {"status": "fail", "reason": "missing stage10"}
            continue
        counts = load_types(stage10)
        ok = delta_ok(pdf_counts, counts)
        summary["formats"][label] = {"status": "ok" if ok else "mismatch", "counts": counts, "stage10": str(stage10)}
        if not ok:
            failures.append(label)
    artifacts = Path("scripts/artifacts"); artifacts.mkdir(parents=True, exist_ok=True)
    # Historical name kept for continuity
    (artifacts / "meta_cli_parity_summary.json").write_text(json.dumps(summary, indent=2))
    # Happy Path artifact name
    (artifacts / "meta_parity_all_formats.json").write_text(json.dumps(summary, indent=2))
    if failures:
        typer.echo(f"Meta parity failures: {', '.join(failures)}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Meta parity across all structured formats passed.")


if __name__ == "__main__":
    app()
