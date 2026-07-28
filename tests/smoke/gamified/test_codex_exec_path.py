import os
import shutil
import subprocess
import sys
from pathlib import Path
import importlib.util as imps
import pytest


def _has_codex() -> bool:
    """Determine 'codex' executable presence."""
    return shutil.which("codex") is not None


def _has_run_codex_exec() -> bool:
    """Check if the deprecated codex execution module exists."""
    return imps.find_spec("extractor.pipeline.utils.deprecated_codex_call") is not None


@pytest.mark.skipif(
    not os.getenv("RUN_CODEX_SMOKE"), reason="Opt-in: set RUN_CODEX_SMOKE=1 to run Codex exec smoke"
)
@pytest.mark.skipif(not _has_codex(), reason="codex CLI not found on PATH")
@pytest.mark.skipif(not _has_run_codex_exec(), reason="run_codex_exec not importable")
def test_codex_exec_end_to_end(tmp_path: Path):
    """Skip tests based on environment variables and conditions."""
    prompt = tmp_path / "prompt_quick.md"
    prompt.write_text(
        "\n".join(
            [
                "## Gamified Run Spec — Quick Codex",
                "## Codebase",
                "repo_root: .",
                "## Approaches",
                "- name: mul_shift_add",
                "## Runner",
                "type: python_benchmark",
                "entry: prototypes/gamified/bench/multiply_benchmark.py",
                "create_if_missing: true",
                "## Scoring",
                "plateau: { epsilon: 0.15, window: 3 }",
                "## Execution",
                "max_iters: 1",
                "api_base: http://localhost:8000",
            ]
        )
    )

    cmd = [
        sys.executable,
        "-m",
        "prototypes.gamified.cli",
        "run",
        "--codebase",
        ".",
        "--prompt-file",
        str(prompt),
        "--instances",
        "1",
        "--sequential",
        "--no-autostart-backend",
        "--no-start-dashboard",
        # default exec-mode=codex; yolo default True
    ]
    p = subprocess.run(cmd)
    assert p.returncode == 0
    # A run should exist with a scorecard
    runs = sorted(Path("workspace/runs").glob("*/scorecard.json"))
    assert runs, "no scorecard.json found"
