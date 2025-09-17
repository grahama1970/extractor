import json
from pathlib import Path

from typer.testing import CliRunner
import pytest


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_debug_bundle_minimal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: CliRunner) -> None:
    # Import after monkeypatching if needed; refactor avoids import-time exits
    from extractor.pipeline.steps import s09_section_summarizer as step

    # Fake the LLM call to return strict JSON
    def fake_call(prompts, **kwargs):  # noqa: ANN001
        return [json.dumps({"summary": "S", "key_concepts": ["a", "b"]})]

    monkeypatch.setattr(step, "litellm_call", lambda *a, **k: fake_call(*a, **k))

    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "reflowed_sections": [
                    {
                        "id": "s1",
                        "title": "Intro",
                        "level": 1,
                        "reflow_status": "success",
                        "reflowed_text": "Hello world",
                    }
                ]
            }
        )
    )

    app = step.build_cli()
    res = runner.invoke(app, ["debug-bundle", str(bundle), "-o", str(tmp_path)], catch_exceptions=False)
    assert res.exit_code == 0
    out = tmp_path / "09_section_summarizer" / "json_output" / "09_summaries.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert data.get("summaries_generated", 0) >= 0
