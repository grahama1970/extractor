import shutil
import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run an external command, capturing its stdout and stderr."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_wait_here_with_short_timeouts_creates_scorecard(tmp_path: Path):
    # Skip if codex CLI is not available in PATH
    if shutil.which("codex") is None:
        return
    run_id = f"test-wait-{int(time.time())}"
    cmd = [
        sys.executable,
        "scripts/gamified.py",
        "run",
        "--codebase",
        ".",
        "--prompt-file",
        "prototypes/gamified/docs/prompt_multiplication_with_tasks.md",
        "--instances",
        "1",
        "--sequential",
        "--instance-timeout-s",
        "3",
        "--idle-timeout-s",
        "3",
        "--no-autostart-backend",
        "--no-start-dashboard",
        "--run-id",
        run_id,
    ]
    _run(cmd)
    # Return code can be 0 even on timeouts (handled internally); assert scorecard exists
    sc = Path(f"workspace/runs/{run_id}/scorecard.json")
    assert sc.exists(), f"missing scorecard for run_id={run_id}"
