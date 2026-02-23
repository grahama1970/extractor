"""Helpers that bridge fetcher downloads into provider workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union, TYPE_CHECKING

from loguru import logger

from extractor.core.fetcher_client import (
    FetcherDownload,
    RollingWindow,
    download_with_fetcher,
    _load_rolling_windows,
)

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from extractor.core.schema.unified_document import DocumentMetadata


_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)

# Common patterns for rolling windows files (created by fetcher)
# Fetcher output structure: run/artifacts/<run-id>/
#   - downloads/ (raw files)
#   - text_blobs/ (extracted text)
#   - results.jsonl (metadata with rolling_windows_path)
_ROLLING_WINDOWS_PATTERNS = [
    "{stem}_rolling_windows.jsonl",
    "{stem}.rolling_windows.jsonl",
    "rolling_windows.jsonl",
    "{stem}_windows.jsonl",
    "../text_blobs/{stem}.txt",  # Fetcher text_blobs directory
    "../text_blobs/{stem}.jsonl",
]


def _discover_rolling_windows(file_path: Path) -> Optional[FetcherDownload]:
    """Look for sibling rolling windows JSONL file for a local file.

    When memory agent calls fetcher first, then extractor with a file path,
    the rolling windows file should be in the same directory.

    Args:
        file_path: Local file path to find rolling windows for

    Returns:
        FetcherDownload with windows if found, None otherwise
    """
    if not file_path.exists():
        return None

    parent = file_path.parent
    stem = file_path.stem

    # Try each pattern
    for pattern in _ROLLING_WINDOWS_PATTERNS:
        candidate = parent / pattern.format(stem=stem)
        if candidate.exists():
            logger.info("Discovered rolling windows at: {}", candidate)
            # Load the windows using the existing loader
            metadata = {"rolling_windows_path": str(candidate)}
            windows = _load_rolling_windows(metadata)
            if windows:
                return FetcherDownload(
                    path=file_path,
                    metadata=metadata,
                    windows=windows,
                )

    # Also check for metadata.json that might contain the path
    metadata_file = parent / f"{stem}_metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
            if "rolling_windows_path" in metadata:
                windows = _load_rolling_windows(metadata)
                if windows:
                    logger.info("Discovered rolling windows via metadata.json")
                    return FetcherDownload(
                        path=file_path,
                        metadata=metadata,
                        windows=windows,
                    )
        except Exception as e:
            logger.debug("Failed to load metadata.json: {}", e)

    # Check parent's results.jsonl (fetcher output format)
    # Structure: run/artifacts/<run-id>/downloads/file.html
    # Results at: run/artifacts/<run-id>/results.jsonl
    results_jsonl = parent.parent / "results.jsonl"
    if results_jsonl.exists():
        try:
            with open(results_jsonl, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                        # Match by file_path field
                        result_path = result.get("file_path", "")
                        if result_path and Path(result_path).name == file_path.name:
                            rw_path = result.get("rolling_windows_path")
                            if rw_path:
                                metadata = {"rolling_windows_path": rw_path}
                                windows = _load_rolling_windows(metadata)
                                if windows:
                                    logger.info("Discovered rolling windows via results.jsonl")
                                    return FetcherDownload(
                                        path=file_path,
                                        metadata=result,
                                        windows=windows,
                                    )
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug("Failed to load results.jsonl: {}", e)

    return None


def ensure_local_source(
    source: Union[str, Path],
    *,
    use_fetcher: bool = True,
    download_mode: str = "rolling_extract",
    window_size: int = 4000,
    window_step: int = 2000,
    run_artifacts_dir: Optional[Path] = None,
) -> Tuple[Path, Optional[FetcherDownload]]:
    """Return a local path for the source and optional FetcherDownload metadata.

    For local files, attempts to discover sibling rolling windows files
    that may have been created by a prior fetcher run.
    """

    if isinstance(source, Path):
        # Try to discover rolling windows for local paths
        fetch_download = _discover_rolling_windows(source)
        return source, fetch_download

    source_str = str(source)
    if not (use_fetcher and _URL_PATTERN.match(source_str)):
        local_path = Path(source_str)
        # Try to discover rolling windows for local paths
        fetch_download = _discover_rolling_windows(local_path)
        return local_path, fetch_download

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


__all__ = ["ensure_local_source", "attach_fetcher_metadata", "_discover_rolling_windows"]
