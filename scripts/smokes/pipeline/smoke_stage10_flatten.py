#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
import subprocess
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Stage 10 flatten smoke")


def run_smoke() -> None:
    load_dotenv(find_dotenv())
    origin = Path(__file__).resolve().parent.parent / "smoke_stage10_flatten.py"
    res = subprocess.run([Path("/usr/bin/env"), "python", str(origin)], text=True)
    raise SystemExit(res.returncode)


@app.command()
def main() -> None:
    run_smoke()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke()
