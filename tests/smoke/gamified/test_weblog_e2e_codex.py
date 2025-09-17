import os
import sys
import time
import urllib.request
import json
from pathlib import Path


def _run(cmd):
    return os.system(cmd)


def _latest_run_id() -> str:
    runs = sorted(Path('workspace/runs').glob('*/instances'))
    return runs[-1].parent.name if runs else ''


def test_weblog_e2e_codex_backend_autostart(tmp_path: Path):
    # Minimal single-variant prompt; let CLI pick a free local port for backend
    prompt = tmp_path / 'prompt_web.md'
    prompt.write_text('\n'.join([
        '## Gamified Run Spec — Web E2E',
        '## Codebase', 'repo_root: .',
        '## Approaches', '- name: mul_shift_add',
        '## Runner', 'type: python_benchmark', 'entry: prototypes/gamified/bench/multiply_benchmark.py', 'create_if_missing: true',
        '## Execution', 'max_iters: 1', 'api_base: http://127.0.0.1',
    ]))

    cmd = (
        'GAMIFIED_FAST_BENCH=1 PYTHONPATH=./src '
        + sys.executable
        + ' -m prototypes.gamified.cli run --codebase . '
        + f'--prompt-file {prompt.as_posix()} '
        + '--instances 1 --sequential --autostart-backend --no-start-dashboard '
        + '--api-base http://127.0.0.1'
    )
    rc = _run(cmd)
    assert rc == 0

    rid = _latest_run_id()
    assert rid, 'no run created'
    run_root = Path('workspace/runs')/rid
    api_file = run_root / 'api_base.txt'
    assert api_file.exists(), 'missing api_base.txt'
    api_base = api_file.read_text().strip()
    # Proto dashboard should respond
    with urllib.request.urlopen(f'{api_base}/proto/dashboard', timeout=5) as r:
        assert 200 <= getattr(r, 'status', 200) < 500
    # Scorecard exists
    sc = run_root / 'scorecard.json'
    assert sc.exists(), 'missing scorecard.json'
    js = json.loads(sc.read_text())
    assert js.get('winner'), 'winner not set'
