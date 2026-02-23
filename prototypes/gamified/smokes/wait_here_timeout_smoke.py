#!/usr/bin/env python3
import sys, subprocess
from pathlib import Path

PROMPT = "prototypes/gamified/docs/prompt_multiplication_with_tasks.md"


def sh(cmd: list[str]):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def latest_run_id():
    runs = sorted(Path("workspace/runs").glob("*/instances"))
    return runs[-1].parent.name if runs else ""


def main():
    cmd = [
        sys.executable,
        "-m",
        "prototypes.gamified.cli",
        "run",
        "--codebase",
        ".",
        "--prompt-file",
        PROMPT,
        "--instances",
        "1",
        "--sequential",
        "--instance-timeout-s",
        "3",
        "--idle-timeout-s",
        "3",
        "--no-autostart-backend",
        "--no-start-dashboard",
    ]
    p = sh(cmd)
    # Even on timeout, runner exits 0; assert scorecard exists
    rid = latest_run_id()
    sc = Path("workspace/runs") / rid / "scorecard.json"
    if not sc.exists():
        print("wait_here_timeout_smoke: missing scorecard for run_id", rid)
        sys.exit(1)
    print("wait_here_timeout_smoke: OK (run_id=%s)" % rid)


if __name__ == "__main__":
    main()
