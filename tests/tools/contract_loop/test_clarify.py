import json

import pytest

from tools.contract_loop.clarify import (
    ClarifyOption,
    ClarifyQuestion,
    ClarifyTimeout,
    normalize_questions,
    run_clarification_flow,
)


def test_normalize_questions_from_strings():
    """Tests normalization of questions from string inputs."""
    qs = normalize_questions(["First?", "Second?"])
    assert len(qs) == 2
    assert qs[0].id == "q1"
    assert qs[1].prompt == "Second?"


def test_single_question_flow_tui_handler(tmp_path):
    """Test single question flow with a TUI handler and output directory."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    path = run_clarification_flow(
        out_dir,
        "step",
        1,
        ["Is this ok?"],
        10,
        tui_handler=lambda q: {"text": "looks good"},
    )
    data = json.loads(path.read_text())
    # Response format: {"id": "q1", "text": "looks good"} - handler response is spread into saved response
    assert data["responses"][0]["text"] == "looks good"


def test_multi_question_flow_with_fake_runner(tmp_path):
    """Test multi-question flow using a fake runner."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    q = ClarifyQuestion(
        id="choice",
        prompt="Pick one",
        kind="single-choice",
        options=[ClarifyOption(id="a", label="Option A")],
    )

    def fake_runner(session):
        """Record fake questionnaire responses to the session."""
        session.save_responses(
            [{"id": q.id, "selectedOptions": ["a"]}],
            extra={"responses": [{"id": q.id, "selectedOptions": ["a"]}]},
        )

    path = run_clarification_flow(
        out_dir,
        "step",
        2,
        [q, q],
        10,
        flask_runner=fake_runner,
    )
    data = json.loads(path.read_text())
    assert data["attempt"] == 2
    assert data["responses"][0]["selectedOptions"] == ["a"]


def test_flask_runner_timeout(tmp_path):
    """Test handling of timeout exceptions in the clarification flow."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    q = ClarifyQuestion(id="q1", prompt="Need more info?", kind="text")

    def fake_runner(_session):
        """Simulate a timeout by raising ClarifyTimeout."""
        raise ClarifyTimeout("timeout")

    with pytest.raises(ClarifyTimeout):
        run_clarification_flow(
            out_dir,
            "step",
            1,
            [q, q],
            1,
            flask_runner=fake_runner,
        )
