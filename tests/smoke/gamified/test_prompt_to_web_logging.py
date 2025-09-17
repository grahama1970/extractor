import os
import sys
import time
import json
from pathlib import Path
import shutil
import importlib.util as imps
import pytest


def _run(cmd):
    return os.system(cmd)


def _latest_run_id() -> str:
    runs = sorted(Path('workspace/runs').glob('*/instances'))
    return runs[-1].parent.name if runs else ''


def test_prompt_to_results_and_proto_dashboard(tmp_path: Path):
    # Run one codex-mode instance with no backend autostart (avoid port conflicts)
    prompt = tmp_path / 'prompt_quick.md'
    prompt.write_text(
        "\n".join([
            "## Gamified Run Spec — Quick",
            "## Codebase", "repo_root: .",
            "## Approaches", "- name: mul_shift_add",
            "## Runner", "type: python_benchmark", "entry: prototypes/gamified/bench/multiply_benchmark.py", "create_if_missing: true",
            "## Scoring", "plateau: { epsilon: 0.15, window: 3 }",
            "## Execution", "max_iters: 1", "api_base: http://localhost:8000",
        ])
    )
    cmd = (
        "GAMIFIED_FAST_BENCH=1 PYTHONPATH=./src "
        + sys.executable
        + " -m prototypes.gamified.cli run --codebase . "
        + f"--prompt-file {prompt.as_posix()} "
        + "--instances 1 --sequential --no-autostart-backend --no-start-dashboard"
        # default exec-mode=codex (primary path)
    )
    rc = _run(cmd)
    assert rc == 0

    rid = _latest_run_id()
    assert rid, "no run created"
    sc_path = Path('workspace/runs') / rid / 'scorecard.json'
    assert sc_path.exists(), "missing scorecard.json"
    js = json.loads(sc_path.read_text())
    assert js.get('winner'), "winner not set in scorecard"

    # Scorecard mirrors are also written to bench/results; assert presence
    out = Path('bench/results/multiply_scorecard.json').read_text()
    assert 'winner' in out
