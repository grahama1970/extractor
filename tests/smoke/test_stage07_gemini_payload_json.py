import json
from pathlib import Path



class _Recorder:
    def __init__(self):
        self.calls = []

    async def acompletion(self, *, model, messages, **kwargs):
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})

        class _Resp:
            def __init__(self, text: str):
                self.usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
                self._hidden_params = {"response_cost": 0.0, "cache_hit": False}
                self.choices = [
                    type("_C", (), {"text": None, "message": type("_M", (), {"content": text})()})()
                ]

        minimal = {
            "reflowed_json": {
                "section_id": "s1",
                "title": "T",
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "ok",
                        "source": {"pages": [], "block_ids": []},
                    }
                ],
            },
            "ocr_corrections": {},
            "improvements_made": "",
            "summary": "",
        }
        return _Resp(json.dumps(minimal))


def _mk_png(p: Path):
    import base64

    p.write_bytes(
        base64.b64decode(
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/YSJ6xkAAAAASUVORK5CYII="
        )
    )


def test_stage07_gemini_json_and_multi_images(tmp_path: Path, monkeypatch):
    # Import after patching PYTHONPATH in test runner
    from extractor.pipeline.steps import s07_reflow_section as s07

    # Build minimal section with multiple images
    base = tmp_path / "results"
    base.mkdir(parents=True, exist_ok=True)

    sec_img = base / "sec.png"
    fig_img = base / "fig.png"
    tab_img = base / "tab.png"
    ann_img = base / "ann.png"
    for p in (sec_img, fig_img, tab_img, ann_img):
        _mk_png(p)

    section = {
        "id": "s1",
        "title": "Test",
        "blocks": [{"text": "Hello world"}],
        "visual_path": str(sec_img),
        "tables": [
            {
                "table_index": 0,
                "table_image_path": str(tab_img),
                "pandas_metrics": {"shape": [2, 2], "data_density": 0.1},
                "camelot_metrics": {"accuracy": 0.0, "whitespace": 0.0},
            }
        ],
        "figures": [{"figure_id": "f1", "image_path": str(fig_img)}],
        "annotations": [{"id": "a1", "image_path": str(ann_img)}],
    }

    # Build messages directly using the helper without executing the full LLM call
    messages = s07.build_reflow_request_messages(
        section,
        base,
        include_images=True,
        model="gemini/gemini-2.5-flash",
        context_text="Hello world",
    )
    # Gemini shaping: single user message with JSON guard in the first text part
    assert messages[0]["role"] == "user"
    parts = messages[0].get("content")
    assert isinstance(parts, list) and parts
    first_text = next((p for p in parts if p.get("type") in ("input_text", "text")), None)
    assert first_text and (
        "Return ONLY a JSON object" in first_text.get("text", "")
        or "Return exactly this JSON" in first_text.get("text", "")
    )
    # Expect at least section + table + figure + annotation images (>=3)
    img_parts = [
        p for p in parts if isinstance(p, dict) and p.get("type") in ("image_url", "input_image")
    ]
    assert len(img_parts) >= 3, f"got {len(img_parts)} image parts"
