import json
from types import SimpleNamespace

import pytest

from extractor.core import fetcher_client
from extractor.core.fetcher_client import FetcherDownload, RollingWindow


def test_sanity_check_accepts_defaults():
    fetcher_client._sanity_check_fetcher_defaults("download_only", 1024, 512)


def test_sanity_check_rejects_bad_step():
    with pytest.raises(ValueError):
        fetcher_client._sanity_check_fetcher_defaults("download_only", 100, 200)


def test_download_with_fetcher_returns_blob(tmp_path, monkeypatch):
    blob = tmp_path / "blob.pdf"
    blob.write_bytes(b"data")
    windows_file = tmp_path / "windows.jsonl"
    windows_file.write_text(json.dumps({"index": 0, "start": 0, "end": 4, "text": "abcd"}) + "\n")
    fake_result = SimpleNamespace(
        metadata={
            "blob_path": str(blob),
            "blob_size": 4,
            "rolling_windows_path": str(windows_file),
        }
    )

    fake_module = SimpleNamespace(
        fetch_url=lambda *args, **kwargs: fake_result,
    )

    monkeypatch.setenv("FETCHER_DOWNLOAD_MODE", "download_only")
    monkeypatch.setattr(fetcher_client, "fetcher_module", fake_module)
    monkeypatch.setattr(fetcher_client, "FETCHER_IMPORT_ERROR", None)

    download = fetcher_client.download_with_fetcher(
        "https://example.com/file.pdf",
        run_artifacts_dir=tmp_path,
        fetch_config=SimpleNamespace(),
    )

    assert isinstance(download, FetcherDownload)
    assert download.path == blob
    assert download.metadata["blob_size"] == 4
    assert download.windows
    assert isinstance(download.windows[0], RollingWindow)
