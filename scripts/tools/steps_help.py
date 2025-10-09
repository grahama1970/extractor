#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import List, Dict


def main() -> int:
    root = Path('src/extractor/pipeline/steps')
    steps: List[Path] = sorted(root.glob('*.py'))
    results: List[Dict[str, str]] = []
    env = os.environ.copy()
    env['PYTHONPATH'] = env.get('PYTHONPATH') or 'src'
    for p in steps:
        name = p.name
        if name.startswith('_') or name == '07_reflow_section.py':
            continue
        try:
            res = subprocess.run(['python', str(p), '--help'], capture_output=True, text=True, timeout=25, env=env)
            ok = (res.returncode == 0)
            results.append({
                'file': str(p),
                'ok': 'ok' if ok else 'fail',
                'rc': str(res.returncode),
                'note': '' if ok else (res.stderr or res.stdout)[:160]
            })
        except subprocess.TimeoutExpired:
            results.append({'file': str(p), 'ok': 'timeout', 'rc': 'timeout', 'note': ''})
        except Exception as e:
            results.append({'file': str(p), 'ok': 'error', 'rc': 'error', 'note': str(e)[:160]})

    print(json.dumps(results, indent=2))
    # print a small table
    okn = sum(1 for r in results if r['ok'] == 'ok')
    failn = sum(1 for r in results if r['ok'] == 'fail')
    print(f"\nSteps OK: {okn}, Fail: {failn}, Total: {len(results)}")
    return 0 if failn == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
