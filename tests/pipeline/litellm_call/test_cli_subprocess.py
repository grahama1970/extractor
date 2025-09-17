import os
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("litellm-call") is None or os.getenv("LITELLM_CALL_E2E") != "1", reason="console script not installed or E2E disabled")
def test_litellm_call_stdin_smoke(tmp_path):
    # Simple stdin echo-like smoke: we call 'main --stdin' and feed two lines
    cmd = ["litellm-call", "main", "--stdin", "--no-progress"]
    proc = subprocess.run(cmd, input="Hello\nWorld\n", text=True, capture_output=True)
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    out_lines = [line for line in proc.stdout.splitlines() if line.strip()]
    # We don't assert the content here; this is a smoke for plumbing/execution
    assert len(out_lines) == 2


@pytest.mark.skipif(shutil.which("litellm-call") is None or os.getenv("LITELLM_CALL_E2E") != "1", reason="console script not installed or E2E disabled")
def test_litellm_call_file_smoke(tmp_path):
    p = tmp_path / "prompts.txt"
    p.write_text("A\nB\n")
    cmd = ["litellm-call", "main", f"@{p}", "--no-progress"]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
