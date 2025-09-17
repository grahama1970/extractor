import json
from typing import List

import pytest
from typer.testing import CliRunner

import extractor.pipeline.utils.litellm_call as lc


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_sanity_ok_exit_zero(monkeypatch, runner: CliRunner):
    async def fake_call(prompts: List[object], **kwargs):
        return [json.dumps({"ok": True})]

    monkeypatch.setattr(lc, "litellm_call", fake_call)
    app = lc.build_cli()
    res = runner.invoke(app, ["sanity", "--wrap-json"])  # model default
    assert res.exit_code == 0
    data = json.loads(res.stdout.strip())
    assert data.get("ok") is True or (isinstance(data.get("content"), dict) and data["content"].get("ok") is True)


def test_main_multiple_prompts_args(monkeypatch, runner: CliRunner):
    async def fake_call(prompts: List[object], **kwargs):
        # Return one result per prompt
        return [f"ans{i}" for i, _ in enumerate(prompts)]

    monkeypatch.setattr(lc, "litellm_call", fake_call)
    app = lc.build_cli()
    res = runner.invoke(app, ["main", "Hello", "World"])  # sources as args
    assert res.exit_code == 0
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert lines == ["ans0", "ans1"]

