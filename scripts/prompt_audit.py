#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12.3","rich>=13.7.0","python-dotenv>=1.0.0"]
# ///
"""Prompt audit gate (shared schema; ready for Kimi paved-path integration).

Current mode: offline validation of artifacts. It fails if:
- A prompt JSON is missing or unparsable.
- A doc mirror is missing.
- A critique file is missing or contains P0/P1 or attempts>3.

Planned: add Kimi call using docs/prompts_extractor/GRADE_PROMPT.md and save results to critiques.
"""

import json
from pathlib import Path
from typing import List, Dict
import typer
from rich import print

GRADE_PROMPT_PATH = Path("docs/prompts_extractor/GRADE_PROMPT.md")
DEFAULT_PROMPTS_DIR = Path("src/extractor/pipeline/prompts")
DEFAULT_DOCS_DIR = Path("docs/prompts_extractor")
DEFAULT_CRITIQUES_DIR = DEFAULT_DOCS_DIR / "critiques"
AUDIT_OUTPUT = Path("data/audit/prompt_audit.json")

app = typer.Typer(add_completion=False)


class AuditError(RuntimeError):
    pass


def list_prompts(prompts_dir: Path) -> List[Path]:
    return sorted(prompts_dir.glob("*.json"))


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text())


def audit_prompt(prompt_path: Path, docs_dir: Path, crit_dir: Path) -> Dict:
    name = prompt_path.stem  # e.g., 07_reflow_section
    doc_path = docs_dir / f"{name}_PROMPT.md"
    crit_path = crit_dir / f"{name}.json"

    if not doc_path.exists():
        raise AuditError(f"Missing doc mirror for {prompt_path.name}: {doc_path}")
    if not crit_path.exists():
        raise AuditError(f"Missing critique for {prompt_path.name}: {crit_path}")

    # Validate prompt json loads
    _ = load_json(prompt_path)

    crit = load_json(crit_path)
    highest = str(crit.get("highest_severity", "")).upper()
    ok = crit.get("ok")
    attempts = crit.get("attempts")

    if ok is not True:
        raise AuditError(f"{prompt_path.name}: ok={ok}")
    if highest in {"P0", "P1"}:
        raise AuditError(f"{prompt_path.name}: highest_severity={highest}")
    if attempts is not None:
        try:
            if int(attempts) > 3:
                raise AuditError(f"{prompt_path.name}: attempts={attempts} > 3")
        except ValueError:
            raise AuditError(f"{prompt_path.name}: attempts not int")

    return {
        "prompt": prompt_path.name,
        "doc": str(doc_path),
        "critique": str(crit_path),
        "highest_severity": highest or "unknown",
        "attempts": attempts,
        "status": "pass",
    }


@app.command()
def main(
    prompts_dir: Path = typer.Option(DEFAULT_PROMPTS_DIR, exists=True, file_okay=False),
    docs_dir: Path = typer.Option(DEFAULT_DOCS_DIR, exists=True, file_okay=False),
    critiques_dir: Path = typer.Option(DEFAULT_CRITIQUES_DIR, exists=True, file_okay=False),
    write_output: bool = typer.Option(
        True, help="Write audit result to data/audit/prompt_audit.json"
    ),
):
    if not GRADE_PROMPT_PATH.exists():
        raise typer.Exit(code=1)

    prompts = list_prompts(prompts_dir)
    if not prompts:
        raise typer.Exit(code=1)

    results = []
    try:
        for p in prompts:
            res = audit_prompt(p, docs_dir, critiques_dir)
            results.append(res)
    except AuditError as e:
        print(f"[red]PROMPT AUDIT FAIL[/red]: {e}")
        raise typer.Exit(code=1)

    if write_output:
        AUDIT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_OUTPUT.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    app()
