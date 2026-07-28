import subprocess
import sys
from pathlib import Path


def _run(cmd):
    """Execute a command, capturing stdout and stderr as text."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _runs_set():
    """Return a set of parent directory names from run instances."""
    return set(p.parent.name for p in Path("workspace/runs").glob("*/instances"))


def test_emit_only_writes_launch_script(tmp_path: Path):
    """Verify emit flag writes only launch script."""
    before = _runs_set()
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
    after = _runs_set()
    added = list(after - before)
    assert added, "no new run created"
    root = Path("workspace/runs") / added[0]
    sh = root / "launch_all.sh"
    assert sh.exists(), "missing launch_all.sh"
    txt = sh.read_text()
    assert "codex exec -C" in txt and "/prompt.md" in txt
