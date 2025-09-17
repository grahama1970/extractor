#!/usr/bin/env python3
import sys, subprocess
from pathlib import Path

PROMPT = 'prototypes/gamified/docs/prompt_multiplication_with_tasks.md'

REQUIRED = [
    '## Original Prompt',
    '## Context',
    '## Gamified Rules (Summary)',
    '## Execute Exactly (non-interactive)',
    '## Monitoring',
]


def sh(cmd: list[str]):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def latest_runs_root() -> Path | None:
    runs = sorted(Path('workspace/runs').glob('*/instances'))
    return runs[-1] if runs else None


def main():
    p = sh([sys.executable, '-m', 'prototypes.gamified.cli', 'run', '--codebase', '.', '--prompt-file', PROMPT, '--instances', '2', '--emit-only', '--no-autostart-backend', '--no-start-dashboard'])
    if p.returncode != 0:
        print('prompt_contract_smoke: emit failed')
        print(p.stderr)
        sys.exit(1)
    root = latest_runs_root()
    if root is None:
        print('prompt_contract_smoke: no instances found')
        sys.exit(1)
    ok = True
    for d in sorted(root.glob('codex_*_*')):
        pr = d/'prompt.md'
        if not pr.exists():
            print('missing prompt:', pr)
            ok = False
            continue
        txt = pr.read_text(encoding='utf-8')
        for sec in REQUIRED:
            if sec not in txt:
                print(f"missing section '{sec}' in {pr}")
                ok = False
    if not ok:
        sys.exit(1)
    print('prompt_contract_smoke: OK')

if __name__ == '__main__':
    main()

