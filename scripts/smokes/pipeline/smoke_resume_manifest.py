#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: run_all --resume (manifest)

Builds a minimal results tree with dummy JSON outputs + a pipeline_manifest.json
that marks stages complete, then invokes run_all with --resume. Verifies that
our dummy outputs are unchanged and exit code is 0. Artifacts written to
scripts/artifacts/resume_manifest_smoke.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
import sys
import typer

app = typer.Typer(add_completion=False)


STAGES = {
    "01_annotation_processor": ["01_annotation_processor/json_output/01_annotations.json"],
    "02_marker_extractor": ["02_marker_extractor/json_output/02_marker_blocks.json"],
    "03_suspicious_headers": ["03_suspicious_headers/json_output/03_verified_blocks.json"],
    "04_section_builder": ["04_section_builder/json_output/04_sections.json"],
    "05_table_extractor": ["05_table_extractor/json_output/05_tables.json"],
    "06_figure_extractor": ["06_figure_extractor/json_output/06_figures.json"],
    "07_reflow_section": ["07_reflow_section/json_output/07_reflowed.json"],
    "09_section_summarizer": ["09_section_summarizer/json_output/09_summaries.json"],
    "10_arangodb_exporter": [
        "10_arangodb_exporter/json_output/10_flattened_data.json",
        "10_arangodb_exporter/json_output/10_export_confirmation.json",
    ],
    "11_arango_create_graph": ["11_arango_create_graph/json_output/11_graph_confirmation.json"],
    "14_report_generator": ["final_report.json", "final_report.md"],
}


def _write_dummy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps({"ok": True, "path": str(path)}, indent=2))
    else:
        path.write_text("Report placeholder\n")


@app.command()
def main(results: Path = Path("scripts/artifacts/resume_smoke")):
    results.mkdir(parents=True, exist_ok=True)
    # Create dummy outputs and record mtimes
    outputs: dict[str, list[str]] = {}
    mtimes_before: dict[str, float] = {}
    for stage, rels in STAGES.items():
        outputs[stage] = []
        for rel in rels:
            fp = results / rel
            _write_dummy(fp)
            outputs[stage].append(str(fp))
            mtimes_before[str(fp)] = fp.stat().st_mtime
    # Stage 01 expects a *_clean.pdf alongside annotations; create a small placeholder
    clean_pdf = results / "01_annotation_processor" / f"{Path('BHT CV32A65X').stem}_clean.pdf"
    clean_pdf.parent.mkdir(parents=True, exist_ok=True)
    clean_pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    # Manifest
    manifest = {
        stage: {"completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "outputs": outs}
        for stage, outs in outputs.items()
    }
    (results / "pipeline_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Invoke run_all --resume (use project python if available)
    py = os.environ.get("PYTHON", sys.executable)
    cmd = [
        py,
        "src/extractor/pipeline/run_all.py",
        "--pdf",
        str((Path("prototypes/tabbed/pdfs") / "BHT CV32A65X.pdf").resolve()),
        "--results",
        str(results.resolve()),
        "--resume",
        "--offline",
        "--skip-llm03",
        "--skip-descriptions06",
        "--summary-only07",
        "--skip-export10",
        "--skip-graph11",
        "--skip-embeddings10",
        "--fast-embeddings10",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str((Path.cwd() / "src").resolve()))
    start = time.time()
    proc = subprocess.run(cmd, env=env)
    duration = time.time() - start

    # Verify mtimes unchanged
    unchanged = {}
    for p_str, before in mtimes_before.items():
        after = Path(p_str).stat().st_mtime
        unchanged[p_str] = (after == before)

    summary = {
        "ok": (proc.returncode == 0 and all(unchanged.values()) and duration < 15),
        "duration_secs": round(duration, 2),
        "unchanged": unchanged,
        "cmd": cmd,
    }
    Path("scripts/artifacts/resume_manifest_smoke.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    sys.exit(0 if summary["ok"] else 2)


if __name__ == "__main__":
    app()
