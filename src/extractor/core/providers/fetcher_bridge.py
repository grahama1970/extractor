"""Helpers that bridge fetcher downloads into provider workflows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple, Union, TYPE_CHECKING

from loguru import logger

from extractor.core.fetcher_client import FetcherDownload, download_with_fetcher

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from extractor.core.schema.unified_document import DocumentMetadata


_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def ensure_local_source(
    source: Union[str, Path],
    *,
    use_fetcher: bool = True,
    download_mode: str = "rolling_extract",
    window_size: int = 4000,
    window_step: int = 2000,
    run_artifacts_dir: Optional[Path] = None,
) -> Tuple[Path, Optional[FetcherDownload]]:
    """Return a local path for the source and optional FetcherDownload metadata."""

    if isinstance(source, Path):
        return source, None

    source_str = str(source)
    if not (use_fetcher and _URL_PATTERN.match(source_str)):
        return Path(source_str), None

    download = download_with_fetcher(
        source_str,
        run_artifacts_dir=run_artifacts_dir,
        window_size=window_size,
        window_step=window_step,
    )
    logger.debug(
        "fetcher_bridge downloaded %s to %s (windows=%s)",
        source_str,
        download.path,
        len(download.windows),
    )
    return download.path, download


def attach_fetcher_metadata(
    metadata: "DocumentMetadata",
    download: Optional[FetcherDownload],
) -> None:
    """Inject fetcher metadata/rolling windows into document metadata."""

    if not download:
        return

    format_meta = getattr(metadata, "format_metadata", None) or {}
    if not isinstance(format_meta, dict):
        format_meta = {}

    format_meta["fetcher_blob_path"] = str(download.path)
    if download.metadata.get("download_mode"):
        format_meta["fetcher_download_mode"] = download.metadata.get("download_mode")
    if download.metadata.get("rolling_windows_path"):
        format_meta["fetcher_rolling_windows_path"] = download.metadata.get("rolling_windows_path")
    if download.windows:
        format_meta["fetcher_rolling_windows_count"] = len(download.windows)

    metadata.format_metadata = format_meta


__all__ = ["ensure_local_source", "attach_fetcher_metadata"]
