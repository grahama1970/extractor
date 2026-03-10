"""
Thin API to run key pipeline stages and return sections.

DEPRECATION NOTICE (2025‑10‑27):
- This module previously spawned subprocesses to call per‑step CLIs.
- It now calls the step functions directly (no subprocess) to align with the
  function‑first pipeline (`extractor.pipeline.run_pipeline`).
- Prefer using `run_pipeline` for full multi‑stage runs. This module remains as
  a convenience for 01→04 extraction.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
import subprocess  # kept for tests that monkeypatch api.subprocess.run
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import time
from datetime import datetime

import typer


DEFAULT_RESULTS_DIR = Path("data/results/pipeline")


@dataclass
class PipelinePaths:
    base: Path
    anno_dir: Path
    blocks_json: Path
    verified_json: Path
    sections_json: Path


def _noop_env(_: Optional[Dict[str, str]] = None) -> None:
    # Kept for compatibility with older call sites that passed env
    return None


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
    """Run key steps and return (sections, sections_json_path).

    Uses subprocess to invoke per-step scripts so tests can monkeypatch
    `api.subprocess.run` and stub artifacts deterministically.
    """
    pdf_path = Path(pdf_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = _paths(out)

    # Minimal execution log and results to seed diagnostics/reporting
    t_start = time.time()
    execution_log: List[Dict[str, Any]] = []
    results: Dict[str, Dict[str, Any]] = {}
    output_files: List[str] = []

    def _log(status: str, step: str, details: str = "") -> None:
        execution_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "status": status,
                "step": step,
                "details": details,
            }
        )

    steps_dir = Path(__file__).resolve().parent / "steps"

    # Stage 01
    _log("started", "01_annotation_processor", os.fspath(pdf_path))
    t0 = time.time()
    try:
        cmd = [
            "python",
            os.fspath(steps_dir / "s01_annotation_processor.py"),
            "run",
            os.fspath(pdf_path),
            "-o",
            os.fspath(out),
        ]
        _run(cmd)
        took = time.time() - t0
        results["01_annotation_processor"] = {"success": True, "duration": took}
        _log("completed", "01_annotation_processor", f"ok in {took:.3f}s")
    except Exception as e:
        took = time.time() - t0
        results["01_annotation_processor"] = {"success": False, "duration": took, "error": str(e)}
        _log("failed", "01_annotation_processor", str(e))
        _write_summary(pdf_path, out, t_start, execution_log, results, output_files)
        raise

    clean_pdf = _find_clean_pdf(p.anno_dir)

    # Stage 02 - pdf_oxide extraction (MIT-licensed, replaces PyMuPDF)
    extractor_script = "s02_pdf_oxide_adapter.py"
    _log("started", "02_marker_extractor", os.fspath(clean_pdf))
    t0 = time.time()
    try:
        cmd = [
            "python",
            os.fspath(steps_dir / extractor_script),
            os.fspath(clean_pdf),
            "-o",
            os.fspath(out),
        ]
        _run(cmd)
        took = time.time() - t0
        results["02_marker_extractor"] = {
            "success": True,
            "duration": took,
            "output": os.fspath(p.blocks_json),
        }
        output_files.append(os.fspath(p.blocks_json))
        _log("completed", "02_marker_extractor", f"wrote {p.blocks_json.name} in {took:.3f}s")
    except Exception as e:
        took = time.time() - t0
        results["02_marker_extractor"] = {"success": False, "duration": took, "error": str(e)}
        _log("failed", "02_marker_extractor", str(e))
        _write_summary(pdf_path, out, t_start, execution_log, results, output_files)
        raise

    # Stage 03
    _log("started", "03_suspicious_headers", os.fspath(p.blocks_json))
    t0 = time.time()
    try:
        cmd = [
            "python",
            os.fspath(steps_dir / "s03_suspicious_headers.py"),
            "run",
            os.fspath(p.blocks_json),
            os.fspath(p.anno_dir),
            "-o",
            os.fspath(out),
        ]
        _run(cmd)
        took = time.time() - t0
        results["03_suspicious_headers"] = {
            "success": True,
            "duration": took,
            "output": os.fspath(p.verified_json),
        }
        output_files.append(os.fspath(p.verified_json))
        _log("completed", "03_suspicious_headers", f"wrote {p.verified_json.name} in {took:.3f}s")
    except Exception as e:
        took = time.time() - t0
        results["03_suspicious_headers"] = {"success": False, "duration": took, "error": str(e)}
        _log("failed", "03_suspicious_headers", str(e))
        _write_summary(pdf_path, out, t_start, execution_log, results, output_files)
        raise

    # Stage 04
    _log("started", "04_section_builder", os.fspath(p.verified_json))
    t0 = time.time()
    try:
        cmd = [
            "python",
            os.fspath(steps_dir / "s04_section_builder.py"),
            "run",
            os.fspath(p.verified_json),
            os.fspath(p.anno_dir),
            "-o",
            os.fspath(out),
        ]
        _run(cmd)
        took = time.time() - t0
        results["04_section_builder"] = {
            "success": True,
            "duration": took,
            "output": os.fspath(p.sections_json),
        }
        output_files.append(os.fspath(p.sections_json))
        _log("completed", "04_section_builder", f"wrote {p.sections_json.name} in {took:.3f}s")
    except Exception as e:
        took = time.time() - t0
        results["04_section_builder"] = {"success": False, "duration": took, "error": str(e)}
        _log("failed", "04_section_builder", str(e))
        _write_summary(pdf_path, out, t_start, execution_log, results, output_files)
        raise

    if not p.sections_json.exists():
        raise FileNotFoundError(f"Sections JSON not found: {p.sections_json}")

    data = json.loads(p.sections_json.read_text())
    sections = data.get("sections") or data.get("result", {}).get("sections") or []
    _write_summary(pdf_path, out, t_start, execution_log, results, output_files)
    return sections, p.sections_json


def _write_summary(
    pdf_path: Path,
    out: Path,
    t_start: float,
    execution_log: List[Dict[str, Any]],
    results: Dict[str, Dict[str, Any]],
    output_files: List[str],
) -> None:
    """Best-effort write of a minimal pipeline summary."""
    try:
        successes = sum(1 for r in results.values() if r.get("success"))
        summary = {
            "pipeline_status": "completed" if successes == len(results) else "failed",
            "pdf_path": os.fspath(pdf_path),
            "total_duration": round(time.time() - t_start, 3),
            "processors": {
                "total": len(results),
                "successful": successes,
                "failed": max(0, len(results) - successes),
            },
            "results": results,
            "execution_log": execution_log,
            "output_files": output_files,
        }
        (out / "pipeline_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception:
        # Never raise from diagnostics write
        pass


def _run(cmd: List[str], cwd: Path | None = None, env: Dict[str, str] | None = None) -> None:
    """Thin wrapper so tests can monkeypatch command execution.

    Default behavior: call subprocess.run with provided cwd/env.
    """
    subprocess.run(cmd, cwd=cwd, env=env)  # type: ignore[attr-defined]


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
