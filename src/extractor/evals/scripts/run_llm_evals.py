#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import typer

from extractor.evals.llm.harness import build_manifest, write_json, now_ts
from extractor.evals.llm.tasks.reflow_section import run_reflow_eval


app = typer.Typer(help="Run LLM evals (lean Phase 1: reflow only)")


@app.command()
def run(
    task: str = typer.Option("reflow", help="Eval task", show_default=True),
    models: Path = typer.Option(
        Path("src/extractor/evals/llm/models.yaml"), help="Path to models.yaml"
    ),
    ratecards: Path = typer.Option(
        Path("src/extractor/evals/providers/ratecards.yaml"), help="Path to ratecards.yaml"
    ),
    registry: Path = typer.Option(
        Path("src/extractor/evals/datasets/registry.json"), help="Dataset registry JSON"
    ),
    prompt_file: Path = typer.Option(
        Path("src/extractor/evals/llm/prompts/reflow_section_system.txt"), help="System prompt file"
    ),
    out: Path = typer.Option(Path("data/evals"), help="Output base directory"),
    assert_pass: bool = typer.Option(
        False, help="Exit non-zero if no passing model found (all metrics ok)"
    ),
    text_min_chars: int = typer.Option(150, help="Minimum contiguous text length to accept"),
    row_tol: float = typer.Option(0.10, help="Row count tolerance (fraction, e.g., 0.10 for 10%)"),
    assert_has_keys: bool = typer.Option(
        True,
        help="Require top-level keys: reflowed_json, ocr_corrections, improvements_made, summary",
    ),
    require_vision: bool = typer.Option(
        True, help="Require the model to accept image inputs (Stage 07 multimodal profile)"
    ),
    max_cost: float = typer.Option(
        None, help="Soft cap: stop adding models once cumulative cost exceeds this USD amount"
    ),
):
    out_base = out
    run_dir = out_base / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    ts = now_ts()
    this_run = run_dir / ts / "llm" / task
    this_run.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(registry, models)
    write_json(this_run / "run_manifest.json", manifest)

    if task != "reflow":
        typer.echo("Only 'reflow' task is implemented in lean Phase 1.")
        raise typer.Exit(2)

    system_text = prompt_file.read_text(encoding="utf-8")
    summary = (
        __import__("asyncio")
        .get_event_loop()
        .run_until_complete(
            run_reflow_eval(
                models,
                ratecards,
                registry,
                system_text,
                this_run,
                text_min_chars=text_min_chars,
                row_tolerance=row_tol,
                require_top_keys=assert_has_keys,
                require_vision=require_vision,
                max_cost=max_cost,
            )
        )
    )
    write_json(this_run / "summary.json", summary)
    out_base.mkdir(parents=True, exist_ok=True)
    (out_base / "summaries").mkdir(parents=True, exist_ok=True)
    write_json(out_base / "summaries" / f"{task}.json", summary)

    rec = summary.get("recommendation", {})
    typer.echo(json.dumps(rec, indent=2))

    any_ok = any(r.get("ok") for r in summary.get("results", []))
    if assert_pass and not any_ok:
        typer.secho("No passing model found (assert-pass enabled).", fg=typer.colors.RED)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
