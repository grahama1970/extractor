#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "fastapi>=0.111.0",
#   "uvicorn>=0.30.0",
#   "httpx>=0.27.0",
#   "python-arango>=7.6.3",
#   "tenacity>=9.0.0",
#   "python-dotenv>=1.0.1",
# ]
# ///

"""
Show & Tell runner for the Gamified project.

Runs a 3-variant Codex execution, prints Run ID, winner, and Web Logger URLs.
Requires ArangoDB to be running and Codex CLI path provided (or in PATH).

Usage:
  export ARANGO_HOST=127.0.0.1 ARANGO_PORT=8529 ARANGO_USERNAME=root ARANGO_PASSWORD=openSesame ARANGO_DB=marker
  export CODEX_BINARY_PATH=/absolute/path/to/codex
  ./scripts/gamified_show_and_tell.py --codebase .

Optional:
  --prompt "approaches: mul_shift_add, mul_karatsuba, mul_chunked"
  --codex-bin /absolute/path/to/codex
  --run-id my-demo-001
"""

from __future__ import annotations
import os, sys, subprocess, time, json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _ts_id(prefix: str = "show") -> str:
  return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}"


@app.command()
def main(
  codebase: Path = typer.Option(Path("."), exists=True, file_okay=False, dir_okay=True, help="Project directory to pass to the CLI"),
  prompt: str = typer.Option("approaches: mul_shift_add, mul_karatsuba, mul_chunked", help="Inline prompt string (alternatively use CLI prompt-file)"),
  codex_bin: str = typer.Option(os.environ.get("CODEX_BINARY_PATH", "codex"), help="Path to Codex CLI (or 'codex' on PATH)"),
  run_id: str = typer.Option(_ts_id(), help="Run ID to use for artifact grouping"),
  instances: int = typer.Option(3, help="Number of concurrent instances"),
  dashboard_port: int = typer.Option(5199, help="Dashboard dev port"),
):
  # Preflight Arango env
  missing = [k for k in ["ARANGO_HOST","ARANGO_PORT","ARANGO_USERNAME","ARANGO_PASSWORD","ARANGO_DB"] if not os.environ.get(k)]
  if missing:
    typer.secho(f"Missing Arango env: {', '.join(missing)}", fg=typer.colors.RED)
    raise typer.Exit(code=2)

  # Run the Typer app via module to avoid nested uv
  env = os.environ.copy()
  # Ensure repo imports resolve
  src = (Path(__file__).resolve().parents[1] / "src").as_posix()
  env["PYTHONPATH"] = f"{src}:{env.get('PYTHONPATH','')}" if src not in env.get('PYTHONPATH','') else env.get('PYTHONPATH','')

  cmd = [
    sys.executable, "-m", "prototypes.gamified.cli", "run",
    "--codebase", str(codebase),
    "--instances", str(instances),
    "--run-id", run_id,
    "--codex-bin-opt", codex_bin,
    "--dashboard-port", str(dashboard_port),
    "--prompt", prompt,
  ]
  typer.secho(f"[show] running: {' '.join(cmd)}", fg=typer.colors.BLUE)
  rc = subprocess.run(cmd, env=env).returncode
  if rc != 0:
    typer.secho(f"Run failed with exit code {rc}", fg=typer.colors.RED)
    raise typer.Exit(code=rc)

  run_root = Path("workspace/runs") / run_id
  scorecard = run_root / "scorecard.json"
  api_txt = run_root / "api_base.txt"
  if not scorecard.exists():
    typer.secho("scorecard.json not found", fg=typer.colors.RED)
    raise typer.Exit(code=3)
  js = json.loads(scorecard.read_text())
  winner = js.get("winner")
  api_base = api_txt.read_text().strip() if api_txt.exists() else None
  dash_url = f"http://localhost:{dashboard_port}"
  scoreboard_url = f"{api_base.rstrip('/')}/scoreboard?run_id={run_id}" if api_base else "<unknown>"
  proto_dash = f"{api_base.rstrip('/')}/proto/dashboard" if api_base else "<unknown>"

  typer.echo("")
  typer.secho("Show & Tell Summary", fg=typer.colors.GREEN)
  typer.echo(f"- Run ID: {run_id}")
  typer.echo(f"- Winner: {winner}")
  typer.echo(f"- Scorecard: {scorecard}")
  typer.echo(f"- API scoreboard: {scoreboard_url}")
  typer.echo(f"- Dashboard (Vite): {dash_url}")
  typer.echo(f"- Dashboard (backend proto): {proto_dash}")
  typer.echo("")
  typer.echo("Tip: Use Cmd/Ctrl+K → 'Copy Share URL' to share a filtered view.")


if __name__ == "__main__":
  app()

