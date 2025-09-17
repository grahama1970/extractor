#!/usr/bin/env python3
import subprocess, sys

scripts = [
    'prototypes.gamified.smokes.contracts_smoke',
    'prototypes.gamified.smokes.prompt_contract_smoke',
    'prototypes.gamified.smokes.emit_aggregate_smoke',
    'prototypes.gamified.smokes.wait_here_timeout_smoke',
]


def main():
    for mod in scripts:
        p = subprocess.run([sys.executable, '-m', mod])
        if p.returncode != 0:
            print('run_all: FAIL at', mod)
            sys.exit(p.returncode)
    print('run_all: OK')


if __name__ == '__main__':
    main()

