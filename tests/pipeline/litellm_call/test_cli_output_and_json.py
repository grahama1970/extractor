from __future__ import annotations

import json
from typing import List

import pytest
from typer.testing import CliRunner

import extractor.pipeline.utils.litellm_call as lc


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_output_and_quiet(monkeypatch, runner: CliRunner, tmp_path):
    async def fake_call(prompts: List[object], **kwargs):
        return [f"ans:{i}" for i, _ in enumerate(prompts)]

    monkeypatch.setattr(lc, "litellm_call", fake_call)
    app = lc.build_cli()

    out_file = tmp_path / "out.txt"
    # Quiet: nothing to stdout, results go to file
    res = runner.invoke(
        app,
        [
            "main",
            "Hello",
            "World",
            "--quiet",
            "--output",
            str(out_file),
        ],
    )
    assert res.exit_code == 0
    assert res.stdout.strip() == ""
    lines = [line for line in out_file.read_text().splitlines() if line.strip()]
    assert lines == ["ans:0", "ans:1"]


def test_json_shorthand_sets_flags(monkeypatch, runner: CliRunner):
    captured = {}

    async def fake_call(prompts: List[object], **kwargs):
        captured.update(kwargs)
        return [json.dumps({"ok": True})]

    monkeypatch.setattr(lc, "litellm_call", fake_call)
    app = lc.build_cli()
    res = runner.invoke(app, ["main", 'Return only {\\"ok\\":true}', "--json"])
    assert res.exit_code == 0
    # Ensure --json mapped to both settings
    assert captured.get("wrap_json") is True
    assert captured.get("response_format") == "json_object"
