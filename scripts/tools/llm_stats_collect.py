#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "rich>=13.7.1",
# ]
# ///
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any
import typer
from rich.console import Console
from rich.table import Table


app = typer.Typer(add_completion=False)
console = Console()


def _safe_load(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


@app.command()
def collect(
    root: Path = typer.Option(Path("data/results/pipeline"), "--root", help="Pipeline output root"),
    out: Path = typer.Option(Path("data/results/pipeline/llm_stats_pipeline.json"), "--out"),
):
    """Aggregate llm_stats.json from all stage json_output/ folders into a single pipeline-level report."""
    stages: Dict[str, Dict[str, Any]] = {}
    total_counts: Dict[str, int] = {"ok": 0, "empty_content": 0, "invalid_json": 0, "provider_error": 0}
    total = 0
    fb_total = 0

    for stage_dir in root.glob("**/json_output"):
        stats_path = stage_dir / "llm_stats.json"
        if not stats_path.exists():
            continue
        data = _safe_load(stats_path)
        if not data:
            continue
        stage = str(data.get("stage") or stage_dir.parent.name)
        stages[stage] = data
        cnts = (data.get("counts") or {})
        for k in total_counts.keys():
            total_counts[k] += int(cnts.get(k, 0))
        total += int(data.get("total") or 0)
        fb_total += int(data.get("fallback_used") or 0)

    pipeline = {
        "stages": stages,
        "total": total,
        "counts": total_counts,
        "fallback_used": fb_total,
        "fallback_rate": (fb_total / total) if total else 0.0,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pipeline, indent=2))

    table = Table(title="LLM Stats (Pipeline)")
    table.add_column("metric"); table.add_column("value")
    table.add_row("total", str(total))
    for k, v in total_counts.items():
        table.add_row(k, str(v))
    table.add_row("fallback_used", str(fb_total))
    table.add_row("fallback_rate", f"{pipeline['fallback_rate']:.3f}")
    console.print(table)
    console.print(f"Saved: {out}")


@app.command()
def gate(
    pipeline_stats: Path = typer.Argument(Path("data/results/pipeline/llm_stats_pipeline.json")),
    max_invalid: int = typer.Option(0, "--max-invalid", help="Maximum invalid_json allowed"),
    max_fallback_rate: float = typer.Option(0.10, "--max-fallback-rate", help="Maximum fallback rate allowed"),
):
    """Fail (exit 1) if pipeline-level llm stats exceed thresholds."""
    data = _safe_load(pipeline_stats)
    if not data:
        console.print("[yellow]No pipeline stats found; skipping gate.[/yellow]")
        raise typer.Exit(0)
    counts = data.get("counts") or {}
    invalid = int(counts.get("invalid_json") or 0)
    fb_rate = float(data.get("fallback_rate") or 0.0)
    ok = (invalid <= max_invalid) and (fb_rate <= max_fallback_rate)
    console.print(f"invalid_json={invalid} (max {max_invalid}) fallback_rate={fb_rate:.3f} (max {max_fallback_rate:.3f})")
    raise typer.Exit(0 if ok else 1)


if __name__ == "__main__":
    app()

