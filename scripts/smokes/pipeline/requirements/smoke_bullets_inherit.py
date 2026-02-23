#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: Bullet list inherits modal verb (shall) from heading; prove via Lean4 CLI offline.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


def extract_bullets_inherit(text: str) -> list[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: list[str] = []
    modal = None
    for ln in lines:
        m = re.search(r"\b(shall|must|will|should)\b", ln, flags=re.IGNORECASE)
        if m:
            modal = m.group(1)
            continue
        if ln.startswith(("- ", "* ", "• ")) and modal:
            core = ln[2:].strip()
            out.append(f"The system {modal} {core}")
    return out


@app.command()
def main():
    lean_cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found")
        raise typer.Exit(0)

    text = """
    The system shall support the following:
    - mode A
    - mode B
    - logging of events
    """.strip()
    reqs = extract_bullets_inherit(text)
    items = [{"requirement": r, "metadata": {"section_id": f"BLT-{i}"}} for i, r in enumerate(reqs)]

    tmp = Path("/tmp/lean_bullets_in.json")
    tmp.write_text(json.dumps(items, indent=2))
    out = Path("/tmp/lean_bullets_out.json")

    cmd = [
        "/home/graham/workspace/experiments/extractor/.venv/bin/python",
        str(lean_cli),
        "batch",
        "--input-file",
        str(tmp),
        "--output-file",
        str(out),
        "--deterministic",
        "--no-llm",
        "--max-workers",
        "1",
    ]
    env = __import__("os").environ.copy()
    env["PYTHONPATH"] = "/home/graham/workspace/experiments/lean4/src:" + env.get("PYTHONPATH", "")
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0 or not out.exists():
        typer.echo("Lean4 batch failed", err=True)
        raise typer.Exit(1)

    data = json.loads(out.read_text())
    summary = {
        "input_count": len(items),
        "proved": sum(1 for r in data.get("proof_results", []) if r.get("status") == "proved"),
        "out": str(out),
    }
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "req_bullets_inherit_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
