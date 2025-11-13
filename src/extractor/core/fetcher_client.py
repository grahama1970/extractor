"""Thin wrapper around the fetcher project for URL -> local file downloads.

Provides a `download_with_fetcher` helper that sources rolling window JSONLs
when fetcher is configured with `FETCHER_DOWNLOAD_MODE=rolling_extract` so
extraction modules automatically see text chunks alongside the raw blob.
"""

from __future__ import annotations

import os
from pathlib import Path
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

try:  # The dependency is declared in pyproject, but be defensive during tests.
    from fetcher.workflows import fetcher as fetcher_module
    from fetcher.workflows.web_fetch import FetchConfig
except Exception as exc:  # pragma: no cover - surfaced via _ensure_fetcher_available
    fetcher_module = None  # type: ignore
    FetchConfig = Any  # type: ignore
    FETCHER_IMPORT_ERROR = exc
else:
    FETCHER_IMPORT_ERROR = None


SUPPORTED_MODES = {"download_only", "rolling_extract"}
DEFAULT_MODE = os.getenv("EXTRACTOR_FETCHER_DOWNLOAD_MODE", "rolling_extract")
DEFAULT_ARTIFACTS = Path(os.getenv("EXTRACTOR_FETCHER_ARTIFACTS", "run/fetcher_artifacts"))


def _sanity_check_fetcher_defaults(mode: str, window_size: int, window_step: int) -> None:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported fetcher download mode: {mode}")
    if window_size <= 0 or window_step <= 0:
        raise ValueError("Rolling window parameters must be positive")
    if window_step > window_size:
        raise ValueError("Window step cannot exceed window size")


def _ensure_fetcher_available() -> None:
    if fetcher_module is None or FETCHER_IMPORT_ERROR is not None:
        raise RuntimeError(
            "fetcher is not installed; run 'uv sync' in extractor with the local path dependency"
        ) from FETCHER_IMPORT_ERROR


@dataclass
class RollingWindow:
    index: int
    start: int
    end: int
    text: str


@dataclass
class FetcherDownload:
    path: Path
    metadata: Dict[str, Any]
    windows: List[RollingWindow]

    def has_windows(self) -> bool:
        return bool(self.windows)


def _load_rolling_windows(metadata: Dict[str, Any]) -> List[RollingWindow]:
    windows_path = metadata.get("rolling_windows_path")
    if not windows_path:
        return []
    path = Path(windows_path)
    if not path.exists():
        logger.warning("Rolling windows path missing: %s", path)
        return []
    loaded: List[RollingWindow] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                loaded.append(
                    RollingWindow(
                        index=int(payload.get("index", len(loaded))),
                        start=int(payload.get("start", 0)),
                        end=int(payload.get("end", 0)),
                        text=payload.get("text", ""),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping malformed rolling window line: %s", exc)
    return loaded


def download_with_fetcher(
    url: str,
    *,
    fetch_config: Optional[FetchConfig] = None,
    run_artifacts_dir: Optional[Path] = None,
    window_size: int = 4000,
    window_step: int = 2000,
) -> FetcherDownload:
    """Fetch a URL and return the downloaded blob plus rolling windows (if any)."""

    _ensure_fetcher_available()
    mode = os.getenv("FETCHER_DOWNLOAD_MODE", DEFAULT_MODE)
    run_dir = run_artifacts_dir or DEFAULT_ARTIFACTS
    run_dir.mkdir(parents=True, exist_ok=True)

    # Sanitise env knobs so we don't regress due to typos.
    _sanity_check_fetcher_defaults(mode, window_size, window_step)

    config = fetch_config or FetchConfig()
    result = fetcher_module.fetch_url(
        url,
        fetch_config=config,
        cache_path=None,
        run_artifacts_dir=run_dir,
        download_mode=mode,
        rolling_window_size=window_size,
        rolling_window_step=window_step,
    )

    metadata = result.metadata or {}
    blob_path = metadata.get("blob_path")
    if not blob_path:
        raise RuntimeError("fetcher did not emit a blob_path; check FETCHER_DOWNLOAD_MODE")

    path = Path(blob_path)
    if not path.exists():
        raise FileNotFoundError(f"Blob path missing on disk: {path}")

    logger.debug(
        "Fetcher downloaded %s -> %s (%s bytes)",
        url,
        path,
        metadata.get("blob_size"),
    )
    windows = _load_rolling_windows(metadata)

    return FetcherDownload(path=path, metadata=metadata, windows=windows)


def sanity_check() -> None:
    """Lightweight guard to ensure defaults look reasonable at import time."""

    _sanity_check_fetcher_defaults(DEFAULT_MODE, 4000, 2000)


sanity_check()
