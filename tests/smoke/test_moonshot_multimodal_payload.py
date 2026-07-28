import asyncio
import base64
from pathlib import Path

import extractor.pipeline.utils.litellm_call as lc


class _Recorder:
    """Record asynchronous completion calls."""
    def __init__(self):
        """Initialize an empty list to store call records."""
        self.calls = []

    async def acompletion(self, *, model, messages, **kwargs):
        """Simulate an async completion API call, returning a mock response."""
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})

        class _Resp:
            """Build a mock API response object for testing purposes."""
            def __init__(self):
                """Initialize usage and hidden parameters for the object."""
                self.usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
                self._hidden_params = {"response_cost": 0.0, "cache_hit": False}
                self.choices = [
                    type("_C", (), {"text": None, "message": type("_M", (), {"content": "ok"})()})()
                ]

        return _Resp()


def _make_png(path: Path):
    # Minimal 1x1 PNG
    png_bytes = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/YSJ6xkAAAAASUVORK5CYII="
    )
    path.write_bytes(png_bytes)


def test_moonshot_multimodal_payload(tmp_path: Path, monkeypatch):
    # Prepare a tiny image file
    img = tmp_path / "dot.png"
    _make_png(img)

    # Patch Router to recorder (no network)
    rec = _Recorder()
    monkeypatch.setattr(lc, "Router", lambda *a, **k: rec)

    # Build a single prompt with image and moonshot model
    item = {"text": "describe", "image": str(img), "model": "moonshot/kimi-k2-turbo-preview"}
    out = asyncio.run(lc.litellm_call([item], show_progress=False))

    assert out == ["ok"], out
    assert rec.calls, "No Router calls recorded"
    call = rec.calls[0]
    assert call["model"].startswith("moonshot/"), call["model"]

    # Validate message parts include a user message with image part
    msgs = call["messages"]
    assert isinstance(msgs, list) and msgs, msgs
    user = msgs[0]
    assert user.get("role") == "user", user
    content = user.get("content")
    assert isinstance(content, list) and any(p.get("type") == "image_url" for p in content), content

    # Ensure we don't pass OpenAI-only response_format to moonshot
    kwargs = call["kwargs"]
    assert "response_format" not in kwargs, f"Unexpected response_format in kwargs: {kwargs}"
