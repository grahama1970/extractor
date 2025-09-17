import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_codex_resolves_via_explicit_path_and_runs(tmp_path: Path):
    codex = shutil.which('codex')
    assert codex, 'codex not found on PATH in this environment'

    # Set explicit path and clear PATH to prove resolver uses absolute path
    env = os.environ.copy()
    env['CODEX_BINARY_PATH'] = codex
    env['PATH'] = ''  # simulate non-login shell with empty PATH
    env['PYTHONPATH'] = str(Path.cwd() / 'src')
    env['GAMIFIED_FAST_BENCH'] = '1'

    # Minimal one-variant prompt on a random port; skip backend/dashboard start
    prompt = tmp_path / 'p.md'
    prompt.write_text('\n'.join([
        '## Gamified Run Spec — Bin Resolve',
        '## Codebase', 'repo_root: .',
        '## Approaches', '- name: mul_shift_add',
        '## Runner', 'type: python_benchmark', 'entry: prototypes/gamified/bench/multiply_benchmark.py', 'create_if_missing: true',
        '## Execution', 'max_iters: 1', 'api_base: http://127.0.0.1:59999',
    ]))

    cmd = [
        sys.executable, '-m', 'prototypes.gamified.cli', 'run',
        '--codebase', '.', '--prompt-file', str(prompt), '--instances', '1',
        '--no-autostart-backend', '--no-start-dashboard'
    ]
    rc = subprocess.run(cmd, env=env).returncode
    assert rc == 0
    # Scorecard should exist
    runs = sorted((Path('workspace/runs')).glob('*/scorecard.json'))
    assert runs, 'no scorecard.json found'

