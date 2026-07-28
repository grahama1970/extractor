import subprocess
import sys
from pathlib import Path


def _run(cmd):
    """Execute a command, capturing its output as text."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_status_cli_reports_table(tmp_path: Path):
    # Emit-only to ensure a run exists
    p = _run(
        [
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
        ]
    )
    assert p.returncode == 0

    # Status should print a header and at least one variant row
    s = _run([sys.executable, "scripts/gamified.py", "status"])
    assert s.returncode == 0
    out = s.stdout.strip()
    assert "instance status (variant | status | last_iter | age)" in out
    assert "- " in out  # at least one row
