from __future__ import annotations

from pathlib import Path


def test_no_cli_framework_in_steps():
    """Ensure no Typer/click/argparse CLIs live in steps (pure-Python callable steps)."""
    steps_dir = Path("src/extractor/pipeline/steps")
    assert steps_dir.exists()
    offenders: list[str] = []
    for py in steps_dir.glob("*.py"):
        txt = py.read_text(encoding="utf-8", errors="ignore")
        if (
            "typer.Typer(" in txt
            or "click.command" in txt
            or "argparse.ArgumentParser(" in txt
        ):
            offenders.append(py.as_posix())
    assert not offenders, f"CLI frameworks found in steps: {offenders}"

