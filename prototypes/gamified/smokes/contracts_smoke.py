#!/usr/bin/env python3
import os, sys, subprocess


def main():
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "./src")
    cmd = [sys.executable, "-m", "pytest", "-q", "tests/smoke/gamified/test_contracts.py"]
    p = subprocess.run(cmd, env=env)
    if p.returncode != 0:
        print("contracts_smoke: FAIL")
        sys.exit(p.returncode)
    print("contracts_smoke: OK")


if __name__ == "__main__":
    main()
