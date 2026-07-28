"""Contract tests for the Tau-only model boundary scanner."""

from __future__ import annotations

import subprocess
import sys


def test_tau_boundary_scanner_accepts_current_tree() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_tau_only_model_boundary.py",
            "src/extractor",
            "src/llm_adapter",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "tau_boundary=pass" in result.stdout
