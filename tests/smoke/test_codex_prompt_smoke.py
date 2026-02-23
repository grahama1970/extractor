import json
import shutil
import subprocess
from pathlib import Path


def test_codex_prompt_smoke_optional(tmp_path: Path):
    """Ensure we can launch codex with a prompt file and wait for completion.

    Optional: skips if `codex` CLI is not on PATH.
    """
    if not shutil.which("codex"):
        return
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# Smoke Prompt\nHello from prompt.", encoding="utf-8")
    proc = subprocess.run(
        [
            "python",
            "scripts/codex_prompt_smoke.py",
            "run",
            "--prompt-file",
            str(prompt),
        ],
        capture_output=True,
        text=True,
    )
    # Expect a JSON line with ok:true and a child summary
    assert proc.returncode in (0, 1)
    try:
        data = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception:
        data = {}
    if proc.returncode == 0:
        assert data.get("ok") is True
        assert data.get("child", {}).get("ok") is True
    else:
        # When failing, ensure diagnostics are present
        assert data.get("ok") is False or "codex" in (proc.stderr or "")
