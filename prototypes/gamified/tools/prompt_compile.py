#!/usr/bin/env python3
from __future__ import annotations

"""
Prompt Compiler (LLM-assisted)
Transforms a research-heavy prompt into a structured, testable Markdown prompt that
our POP optimizer can validate and the orchestrator can run.
Usage:
  python -m prototypes.gamified.tools.prompt_compile compile RESEARCH.md     -o prototypes/gamified/docs/02_tokamak_prompt.md --show-diff
Environment:
  - Uses litellm and the project's default model (LITELLM_DEFAULT_MODEL or fallback).
  - Requires provider API keys as usual for litellm.
"""
import difflib
import os
import sys
from pathlib import Path
from typing import Optional
import typer

app = typer.Typer(add_completion=False)
SYSTEM_INSTRUCTIONS = """
You are a Prompt Compiler for a gamified orchestrator that will run three concurrent
code-generation instances and judge them. Convert the user's research text into a
single, unambiguous Markdown prompt with these required sections and rules:
- Sections (exact headings):
  ## Codebase  (include: repo_root: .)
  ## Approaches  (YAML list; each item has name, summary, verification, outputs)
  ## Runner     (type: analysis_sim; add short notes if needed)
  ## Scoring    (weights that sum to 100; keys: correctness, robustness, speed, brevity)
  ## Constraints (YAML: edge_density_threshold, q_min, beta_max, heat_flux_peak_max; with units)
  ## Evidence   (YAML checklist per approach with keys: stability_margin, density_ok, heat_flux_peak, constraints_ok)
  ## Execution  (concurrency: 3, codex_exec: true, autostart_backend: true, autostart_dashboard: true)
  ## References (bullet list of URLs/DOIs/arXiv IDs)
  ## Tasks      (json tasks code block; add two pre-run tasks that log context and refs)
- Approach names must be snake_case and distinct.
- Do NOT leave placeholders like "define" or "TBD" in Constraints; propose reasonable defaults with units.
- Keep summaries concise (<= 350 chars) and use active voice.
- Prefer realistic values for constraints (provide units) and mention if conservative.
- Outputs must be judgeable: numeric stability_margin >= 0, density_ok boolean, heat_flux_peak numeric, constraints_ok boolean.
- Keep the total token count modest; no long essays. Use compact YAML where possible.
"""


def _show_diff(raw: str, compiled: str) -> str:
    diff = difflib.unified_diff(
        raw.splitlines(), compiled.splitlines(), fromfile="research", tofile="compiled", lineterm=""
    )
    return "\n".join(diff)


def _call_llm_compile(research_text: str) -> str:
    try:
        # Prefer project default model via litellm
        from extractor.pipeline.utils.litellm_call import MODEL as DEFAULT_MODEL  # type: ignore
        import litellm
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"LLM runtime unavailable: {e}")
    model = os.environ.get("LITELLM_DEFAULT_MODEL", DEFAULT_MODEL)
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS.strip()},
        {"role": "user", "content": research_text},
    ]
    # Temperature low for determinism; providers handled by litellm router config
    resp = litellm.completion(model=model, messages=messages, temperature=0.2, max_tokens=2500)

    def _extract_text(r: object) -> str | None:  # type: ignore[override]
        try:
            ch0 = r.choices[0]  # type: ignore[attr-defined]
            msg = getattr(ch0, "message", None)
            if isinstance(msg, dict):
                val = msg.get("content")
            else:
                val = getattr(msg, "content", None)
            # litellm may return a list of content parts for some providers
            if isinstance(val, list):
                out_parts = []
                for p in val:
                    if isinstance(p, str):
                        out_parts.append(p)
                    elif isinstance(p, dict):
                        t = p.get("text") or p.get("content") or p.get("value")
                        if isinstance(t, str):
                            out_parts.append(t)
                if out_parts:
                    return "\n".join(out_parts).strip()
            if isinstance(val, str) and val.strip():
                return val
            # Other adapter shapes
            txt = getattr(ch0, "text", None)
            if isinstance(txt, str) and txt.strip():
                return txt
        except Exception:
            pass
        # Last resort: some adapters expose output_text
        try:
            ot = getattr(r, "output_text", None)
            if isinstance(ot, str) and ot.strip():
                return ot
        except Exception:
            pass
        return None

    text = _extract_text(resp)
    if not text:
        # Retry once with a safer default text model if available
        fallback_model = os.environ.get("PROMPT_COMPILER_MODEL", "gpt-4o-mini")
        if fallback_model != model:
            try:
                resp2 = litellm.completion(
                    model=fallback_model, messages=messages, temperature=0.2, max_tokens=2500
                )
                text = _extract_text(resp2)
            except Exception:
                text = None
    if not text or not isinstance(text, str) or not text.strip():
        raise RuntimeError("LLM returned empty content")
    return text


@app.command()
def compile(
    research_path: Path = typer.Argument(..., help="Path to research Markdown"),
    out_path: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write compiled prompt to this path"
    ),
    rules_path: Path = typer.Option(
        Path("prototypes/gamified/rules/prompt_optimization.yaml"),
        "--rules",
        help="Rules file for POP validation",
    ),
    show_diff: bool = typer.Option(True, "--show-diff", help="Show diff research → compiled"),
    optimize: bool = typer.Option(True, "--optimize", help="Run POP optimizer after compilation"),
):
    raw = research_path.read_text(encoding="utf-8")
    try:
        compiled = _call_llm_compile(raw)
    except Exception as e:
        print(f"WARNING: LLM compilation failed ({e}); falling back to raw research text.")
        compiled = raw
    if show_diff:
        print("\n--- Diff (research → compiled) ---\n")
        print(_show_diff(raw, compiled))
    if optimize:
        try:
            from prototypes.gamified.tools.prompt_opt import PromptOptimizer  # type: ignore
            import yaml  # type: ignore

            rules_obj = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
            opt = PromptOptimizer(rules_obj)
            optimized, rep = opt.validate_and_optimize(compiled)
            if rep.errors:
                print(
                    "\nERROR: compiled prompt failed POP validation. Please address the following:"
                )
                for e in rep.errors:
                    print(f" - [{e.code}] {e.message}")
                raise typer.Exit(code=2)
            compiled = optimized
            print("\n[compiler] POP optimization completed.")
        except Exception as e:
            print(f"WARNING: POP optimizer unavailable or failed: {e}")
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(compiled, encoding="utf-8")
        print(f"[compiler] wrote → {out_path}")
    else:
        print("\n--- Compiled Markdown ---\n")
        print(compiled)


if __name__ == "__main__":
    app()
