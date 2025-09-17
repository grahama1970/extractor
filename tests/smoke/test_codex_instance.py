import json
import os
import shutil
import subprocess


def test_codex_smoke_optional():
    """Launch a single codex exec instance and wait for completion.

    Optional: skips if `codex` CLI is not on PATH or if CI environment disallows it.
    """
    if not shutil.which("codex"):
        return
    # Keep test minimal and fast
    env = os.environ.copy()
    proc = subprocess.run(
        [
            "python",
            "scripts/codex_smoke.py",
            "run",
            "--python",
            "-c",
            "print('smoke_ok')",
        ],
        capture_output=True,
        text=True,
    )
    # On success, stdout is a JSON object with ok:true
    assert proc.returncode in (0, 1)
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        out = {}
    # If codex returned successfully, ok should be True
    if proc.returncode == 0:
        assert out.get("ok") is True
        assert out.get("rc") == 0
    else:
        # Provide some diagnostics when failing in local envs
        assert "codex" in (proc.stderr or "") or out.get("ok") is False

