import asyncio
import base64
from pathlib import Path

import extractor.pipeline.utils.litellm_call as lc


class _Recorder:
    def __init__(self):
        self.calls = []

    async def acompletion(self, *, model, messages, **kwargs):
        # Record the first call only
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})

        class _Resp:
            def __init__(self):
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


def test_gemini_multimodal_payload(tmp_path: Path, monkeypatch):
    # Prepare a tiny image file
    img = tmp_path / "dot.png"
    _make_png(img)

    # Patch Router with recorder
    rec = _Recorder()
    monkeypatch.setattr(lc, "Router", lambda *a, **k: rec)

    # Build a single prompt with image and Gemini model
    item = {"text": "describe", "image": str(img), "model": "gemini/gemini-2.5-flash"}
    out = asyncio.run(lc.litellm_call([item], show_progress=False))

    assert out == ["ok"], out
    assert rec.calls, "No Router calls recorded"
    call = rec.calls[0]
    assert call["model"].startswith("gemini/"), call["model"]

    # Validate message parts include a user message with image part
    msgs = call["messages"]
    assert isinstance(msgs, list) and msgs, msgs
    user = msgs[0]
    assert user.get("role") == "user", user
    content = user.get("content")
    assert isinstance(content, list) and any(p.get("type") == "image_url" for p in content), content

    # Ensure token-limit keys and response_format are not sent for Gemini
    kwargs = call["kwargs"]
    for k in ("max_tokens", "max_output_tokens", "response_format"):
        assert k not in kwargs, f"Found forbidden kwarg for Gemini: {k}={kwargs.get(k)}"
