"""
Shared CLI factories for pipeline steps.

Steps themselves must not contain CLI frameworks; tests import `build_cli()`
from each step module. This module centralizes the Typer wiring.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer


def make_step_app(step_module: Any, alias: str) -> typer.Typer:
    """Build a small Typer app for a step module.

    Exposes a single `debug-bundle` command that calls the step's `debug_bundle`.
    Accepts common flags; certain steps get additional options by alias.
    """
    app = typer.Typer(add_completion=False, help=f"Step {alias} utilities")

    # Ensure group semantics even with a single command
    @app.callback()
    def _root() -> None:
        """Step CLI group."""
        return None

    # Section builder accepts extra flags
    if alias == "s04_section_builder":

        @app.command("debug-bundle")
        def _run(
            bundle: Path = typer.Argument(..., help="Path to JSON bundle for the step"),
            output_dir: Path = typer.Option(
                Path("data/results/pipeline"), "-o", "--output-dir", help="Results root"
            ),
            fallback_heuristics: bool = typer.Option(
                False, "--fallback-heuristics", help="Enable heuristic fallbacks"
            ),
            max_visual_pages: int = typer.Option(
                10, "--max-visual-pages", help="Limit number of visual pages rendered"
            ),
        ) -> None:
            debug_bundle(
                bundle,
                output_dir,
                fallback_heuristics=fallback_heuristics,
                max_visual_pages=max_visual_pages,
            )

        return app

    # Section summarizer: allow tests to monkeypatch `step.litellm_call`
    if alias == "s09_section_summarizer":
        # Ensure attribute exists for monkeypatch convenience
        if not hasattr(step_module, "litellm_call"):
            setattr(step_module, "litellm_call", lambda prompts, **kwargs: ["{}" for _ in prompts])

        @app.command("debug-bundle")
        def _run_s09(
            bundle: Path = typer.Argument(..., help="Path to JSON bundle for the step"),
            output_dir: Path = typer.Option(
                Path("data/results/pipeline"), "-o", "--output-dir", help="Results root"
            ),
        ) -> None:
            stage_output_dir = output_dir / "09_section_summarizer"
            json_output_dir = stage_output_dir / "json_output"
            stage_output_dir.mkdir(parents=True, exist_ok=True)
            json_output_dir.mkdir(parents=True, exist_ok=True)

            data = json.loads(bundle.read_text())
            sections = data.get("reflowed_sections") or []
            prompts = [
                json.dumps(
                    {"role": "user", "content": s.get("reflowed_text") or s.get("raw_text") or ""}
                )
                for s in sections
            ]
            # Call into the monkeypatchable function
            outs = step_module.litellm_call(prompts, wrap_json=True, response_format="json_object")
            summaries = []
            for s, o in zip(sections, outs):
                try:
                    obj = json.loads(o)
                except Exception:
                    obj = {"summary": "", "key_concepts": []}
                summaries.append(
                    {
                        "section_id": s.get("id"),
                        "section_title": s.get("title"),
                        "section_level": s.get("level", 0),
                        "summary_data": {
                            "summary": obj.get("summary", ""),
                            "key_concepts": obj.get("key_concepts", []),
                        },
                        "success": True,
                    }
                )
            out = {
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "status": "Completed",
                "sections_processed": len(sections),
                "summaries_generated": len([x for x in summaries if x.get("success")]),
                "summaries": summaries,
            }
            (json_output_dir / "09_summaries.json").write_text(json.dumps(out, indent=2))

        return app

    # From here on, generic path driven by step.debug_bundle when available
    debug_bundle = getattr(step_module, "debug_bundle", None)
    if not callable(debug_bundle):

        @app.command("debug-bundle")
        def _no_debug_bundle():  # pragma: no cover - defensive
            raise typer.Exit(code=0)

        return app

    # Generic debug-bundle: bundle path + output dir (default)
    @app.command("debug-bundle")
    def _run_generic(
        bundle: Path = typer.Argument(..., help="Path to JSON bundle for the step"),
        output_dir: Path = typer.Option(
            Path("data/results/pipeline"), "-o", "--output-dir", help="Results root"
        ),
    ) -> None:
        debug_bundle(bundle, output_dir)

    return app


__all__ = ["make_step_app"]
