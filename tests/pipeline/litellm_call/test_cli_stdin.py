from typing import List

import pytest
from typer.testing import CliRunner

import extractor.pipeline.utils.litellm_call as lc


@pytest.fixture()
def runner() -> CliRunner:
    """Return a CliRunner instance for testing command-line interfaces."""
    return CliRunner()


def test_main_reads_stdin_with_input(monkeypatch, runner: CliRunner):
    """Test CLI input handling by simulating standard input prompts."""
    async def fake_call(prompts: List[object], **kwargs):
        """Simulate responses for input prompts."""
        return [f"ans:{p}" for p in prompts]

    monkeypatch.setattr(lc, "litellm_call", fake_call)
    app = lc.build_cli()
    res = runner.invoke(app, ["main", "--stdin"], input="X\nY\n")
    assert res.exit_code == 0
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert lines == ["ans:X", "ans:Y"]
