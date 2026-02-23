#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path

PROMPT = "prototypes/gamified/docs/prompt_multiplication_with_tasks.md"


def sh(cmd: list[str], **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)


def latest_run_id() -> str:
    runs = sorted(Path("workspace/runs").glob("*/instances"))
    if not runs:
        return ""
    return runs[-1].parent.name


def synthesize_iters(inst_root: Path):
    for d in inst_root.glob("codex_*_*"):
        variant = d.name.split("_", 2)[-1]
        blob = {
            "approach": variant,
            "correctness": {"S": True, "M": False, "L": False},
            "timings_ms": {"S": 0.05, "M": 1e9, "L": 1e9},
            "robust": True,
            "loc": 10,
        }
        (d / "iter_01.json").write_text(json.dumps(blob), encoding="utf-8")


def main():
    # Emit prompts using canonical CLI module
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
        "2",
        "--emit-only",
        "--no-autostart-backend",
        "--no-start-dashboard",
    ]
    p = sh(cmd)
    if p.returncode != 0:
        print("emit_aggregate_smoke: emit failed")
        print(p.stderr)
        sys.exit(1)
    rid = latest_run_id()
    if not rid:
        print("emit_aggregate_smoke: no run_id found")
        sys.exit(1)
    inst_root = Path("workspace/runs") / rid / "instances"
    synthesize_iters(inst_root)
    # Aggregate
    p2 = sh(
        [
            sys.executable,
            "-m",
            "prototypes.gamified.cli",
            "run",
            "--codebase",
            ".",
            "--run-id",
            rid,
            "--aggregate-only",
            "--no-autostart-backend",
            "--no-start-dashboard",
        ]
    )
    if p2.returncode != 0:
        print("emit_aggregate_smoke: aggregate failed")
        print(p2.stderr)
        sys.exit(1)
    sc = Path("workspace/runs") / rid / "scorecard.json"
    if not sc.exists():
        print("emit_aggregate_smoke: missing scorecard")
        sys.exit(1)
    print("emit_aggregate_smoke: OK (run_id=%s)" % rid)


if __name__ == "__main__":
    main()
