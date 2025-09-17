import base64
from pathlib import Path

import pytest

from extractor.pipeline.utils import litellm_image_utils as ih


def test_extract_images_local_and_remote(tmp_path: Path):
    # create a tiny PNG
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not available")

    img_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(img_path)

    text = f"Describe this {img_path} and also https://example.com/cat.jpg"
    imgs, cleaned = ih.extract_images(text)
    assert str(img_path) in imgs
    assert any(u.endswith("cat.jpg") for u in imgs)
    assert "{Image 1}" in cleaned and "{Image 2}" in cleaned


def test_fetch_remote_image_cached_failure(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            raise RuntimeError("404")

    def fake_get(url, timeout):
        raise RuntimeError("network fail")

    import extractor.pipeline.utils.litellm_image_utils as image_helpers

    monkeypatch.setattr(image_helpers.httpx, "get", fake_get)
    out = ih.fetch_remote_image_cached("http://does-not-exist.example/foo.jpg", timeout=1)
    assert out is None


def test_compress_image_cached_returns_data_uri(tmp_path: Path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not available")

    big = tmp_path / "big.jpg"
    Image.new("RGB", (2000, 2000), color=(0, 128, 255)).save(big, format="JPEG", quality=95)
    out = ih.compress_image_cached(str(big), max_kb=100)
    assert isinstance(out, str)
    assert out.startswith("data:image/")


def test_core_to_messages_grouping_extras():
    # Ensure extra kwargs are preserved for individual (non-batch) path
    # Use the unified litellm_call module
    from extractor.pipeline.utils.litellm_call import _to_messages_and_model, MODEL

    item = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.3,
    }
    model, messages, extra = _to_messages_and_model(item, MODEL)
    assert model == MODEL
    assert isinstance(messages, list) and messages
    assert extra.get("temperature") == 0.3
