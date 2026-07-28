
from extractor.core.providers import fetcher_bridge
from extractor.core.fetcher_client import FetcherDownload, RollingWindow
from extractor.core.schema.unified_document import DocumentMetadata


def test_ensure_local_source_passthrough(tmp_path, monkeypatch):
    """Confirms `ensure_local_source` passes through local paths."""
    path, download = fetcher_bridge.ensure_local_source(tmp_path)
    assert path == tmp_path
    assert download is None


def test_ensure_local_source_downloads_url(monkeypatch, tmp_path):
    """Test local source download functionality with a mocked URL."""
    fake_path = tmp_path / "blob.bin"
    fake_path.write_text("hi", encoding="utf-8")
    fake_download = FetcherDownload(
        path=fake_path,
        metadata={
            "download_mode": "rolling_extract",
            "rolling_windows_path": str(tmp_path / "windows.jsonl"),
        },
        windows=[RollingWindow(index=0, start=0, end=4, text="test")],
    )

    monkeypatch.setattr(fetcher_bridge, "download_with_fetcher", lambda *_, **__: fake_download)

    path, download = fetcher_bridge.ensure_local_source("https://example.com/doc")
    assert path == fake_path
    assert download is fake_download


def test_attach_fetcher_metadata(tmp_path):
    """Attach metadata to a fetcher download instance."""
    metadata = DocumentMetadata()
    download = FetcherDownload(
        path=tmp_path / "blob.txt",
        metadata={
            "download_mode": "rolling_extract",
            "rolling_windows_path": str(tmp_path / "windows.jsonl"),
        },
        windows=[RollingWindow(index=0, start=0, end=10, text="sample")],
    )

    fetcher_bridge.attach_fetcher_metadata(metadata, download)

    assert metadata.format_metadata["fetcher_blob_path"].endswith("blob.txt")
    assert metadata.format_metadata["fetcher_download_mode"] == "rolling_extract"
    assert metadata.format_metadata["fetcher_rolling_windows_count"] == 1
