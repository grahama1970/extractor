#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: Convert simple table-like constraints to requirements and prove via Lean4 CLI offline.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


def parse_constraints(table_text: str) -> list[str]:
    out: list[str] = []
    for line in table_text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("param"):
            continue
        # Examples: "Speed: 10 m/s <= v <= 20 m/s" or "Temp: T <= 70 C"
        m = re.match(r"([^:]+):\s*(.+)", line)
        if not m:
            continue
        name, expr = m.group(1).strip(), m.group(2).strip()
        out.append(f"The parameter {name} shall satisfy: {expr}")
    return out


@app.command()
def main():
    lean_cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found")
        raise typer.Exit(0)

    table = """
    Param   Constraint
    Speed:  10 m/s <= v <= 20 m/s
    Temp:   T <= 70 C
    """.strip()
    reqs = parse_constraints(table)
    items = [{"requirement": r, "metadata": {"section_id": f"T-{i}"}} for i, r in enumerate(reqs)]

    tmp = Path("/tmp/lean_table_in.json")
    tmp.write_text(json.dumps(items, indent=2))
    out = Path("/tmp/lean_table_out.json")

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
    (Path("scripts/artifacts") / "req_table_constraints_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
