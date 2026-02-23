#!/usr/bin/env python3
import sys
import subprocess
import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main():
    # Ensure repo root on sys.path so prototypes import works
    rr = str(repo_root())
    env = os.environ.copy()
    env["PYTHONPATH"] = rr + os.pathsep + env.get("PYTHONPATH", "")
    mods = [
        "prototypes.gamified.smokes.contracts_smoke",
        "prototypes.gamified.smokes.prompt_contract_smoke",
        "prototypes.gamified.smokes.emit_aggregate_smoke",
        "prototypes.gamified.smokes.wait_here_timeout_smoke",
    ]
    for mod in mods:
        p = subprocess.run([sys.executable, "-m", mod], env=env)
        if p.returncode != 0:
            print("run_all: FAIL at", mod)
            sys.exit(p.returncode)
    print("run_all: OK")


if __name__ == "__main__":
    main()
