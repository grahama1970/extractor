import os
import re
import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)


def test_emit_only_generates_contractual_prompts(tmp_path: Path):
    run_id = f"test-emit-{int(time.time())}"
    cmd = [
        sys.executable,
        "scripts/gamified.py",
        "run",
        "--codebase",
        ".",
        "--prompt-file",
        "prototypes/gamified/docs/prompt_multiplication_with_tasks.md",
        "--instances",
        "2",
        "--emit-only",
        "--no-autostart-backend",
        "--no-start-dashboard",
        "--run-id",
        run_id,
    ]
    r = _run(cmd)
    assert r.returncode == 0, r.stderr

    inst_root = Path(f"workspace/runs/{run_id}/instances")
    assert inst_root.exists()
    inst_dirs = sorted(inst_root.glob("codex_*_*"))
    assert len(inst_dirs) >= 2

    # Contract: required sections present in each prompt
    required = [
        "## Original Prompt",
        "## Context",
        "## Gamified Rules (Summary)",
        "## Execute Exactly (non-interactive)",
        "## Monitoring",
    ]
    for d in inst_dirs:
        prompt = d / "prompt.md"
        assert prompt.exists(), f"missing prompt: {prompt}"
        txt = prompt.read_text()
        for sec in required:
            assert sec in txt, f"section '{sec}' missing in {prompt}"

