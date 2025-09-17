"""
Thin API to run key pipeline stages and return sections.

Runs Stages 01 (clean), 02 (marker blocks), 03 (suspicious header verify),
and 04 (section builder) via their CLI scripts, writing outputs to
`data/results/pipeline` by default, and returns the parsed sections list
from `04_sections.json`.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer


DEFAULT_RESULTS_DIR = Path("data/results/pipeline")


@dataclass
class PipelinePaths:
    base: Path
    anno_dir: Path
    blocks_json: Path
    verified_json: Path
    sections_json: Path


def _run(cmd: List[str], cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> None:
    e = os.environ.copy()
    if env:
        e.update(env)
    # Ensure imports resolve
    e.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def _find_clean_pdf(anno_dir: Path) -> Path:
    candidates = sorted(anno_dir.glob("*_clean.pdf"))
    if not candidates:
        raise FileNotFoundError(f"No '*_clean.pdf' found in {anno_dir}")
    return candidates[0]


def _paths(base: Path) -> PipelinePaths:
    return PipelinePaths(
        base=base,
        anno_dir=base / "01_annotation_processor",
        blocks_json=base / "02_marker_extractor" / "json_output" / "02_marker_blocks.json",
        verified_json=base / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json",
        sections_json=base / "04_section_builder" / "json_output" / "04_sections.json",
    )


def extract_sections(
    pdf_path: Path | str, output_dir: Path | str = DEFAULT_RESULTS_DIR, debug: bool = False
) -> Tuple[List[Dict[str, Any]], Path]:
    """Run key steps and return (sections, sections_json_path)."""
    pdf_path = Path(pdf_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = _paths(out)

    # Stage 01: annotation/cleaner
    # Produces cleaned PDF in p.anno_dir
    _run(
        [
            sys.executable,
            os.fspath(Path("src/extractor/pipeline/steps/01_annotation_processor.py")),
            "run",
            os.fspath(pdf_path),
            "-o",
            os.fspath(out),
        ]
    )

    clean_pdf = _find_clean_pdf(p.anno_dir)

    # Stage 02: marker blocks
    _run(
        [
            sys.executable,
            os.fspath(Path("src/extractor/pipeline/steps/02_marker_extractor.py")),
            "run",
            os.fspath(clean_pdf),
            "-o",
            os.fspath(out),
        ]
    )

    # Stage 03: suspicious header verify
    _run(
        [
            sys.executable,
            os.fspath(Path("src/extractor/pipeline/steps/03_suspicious_headers.py")),
            "run",
            os.fspath(p.blocks_json),
            "--pdf-dir",
            os.fspath(p.anno_dir),
            "-o",
            os.fspath(out),
        ]
    )

    # Stage 04: section builder
    _run(
        [
            sys.executable,
            os.fspath(Path("src/extractor/pipeline/steps/04_section_builder.py")),
            "run",
            os.fspath(p.verified_json),
            "--pdf-dir",
            os.fspath(p.anno_dir),
            "-o",
            os.fspath(out),
        ]
    )

    if not p.sections_json.exists():
        raise FileNotFoundError(f"Sections JSON not found: {p.sections_json}")

    data = json.loads(p.sections_json.read_text())
    sections = data.get("sections") or data.get("result", {}).get("sections") or []
    return sections, p.sections_json


def build_cli() -> typer.Typer:
    """Return a Typer app for this module.

    Exposed as a factory so tests can import and run the CLI with CliRunner
    without side effects at import time.
    """
    app = typer.Typer(add_completion=False, help="Run core pipeline (01→04) and return sections")

    @app.command()
    def run(
        pdf: Path = typer.Argument(
            ..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input PDF"
        ),
        out: Path = typer.Option(
            DEFAULT_RESULTS_DIR, "-o", "--output-dir", help="Results directory"
        ),
        json_out: bool = typer.Option(False, "--json", help="Print sections JSON to stdout"),
    ) -> None:
        sections, path = extract_sections(pdf, out)
        if json_out:
            print(json.dumps({"sections": sections}, indent=2))
        else:
            print(f"Sections JSON: {path}")
            print(f"Sections count: {len(sections)}")

    return app


def cli_main() -> None:
    """CLI entrypoint for running via console_scripts or `python -m`.

    This builds the Typer app and runs it.
    """
    build_cli()()


__all__ = ["extract_sections", "DEFAULT_RESULTS_DIR", "cli_main", "build_cli"]
