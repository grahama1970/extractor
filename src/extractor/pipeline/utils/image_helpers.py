from __future__ import annotations

import base64
import hashlib
import io
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

import httpx
from PIL import Image
from urlextract import URLExtract

from strip_tags import strip_tags
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error

# Supported image extensions
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}


def _get_cache_dir(explicit_dir: Optional[str] = None) -> Optional[Path]:
    d = explicit_dir or os.getenv("LITELLM_IMAGE_CACHE_DIR")
    if not d:
        return None
    p = Path(d).expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception as exc:
        log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
        raise
        return None


def safe_image(path: Path) -> bool:
    try:
        return (
            path.exists() and path.suffix.lower() in IMAGE_EXT and Image.open(path).verify() is None
        )
    except Exception as exc:
        log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
        raise
        return False


def extract_images(text: str) -> Tuple[List[str], str]:
    """
    Return a tuple of (image_refs, cleaned_text).
    - image_refs includes remote URLs and local file paths that look like images.
    - cleaned_text replaces found refs with {Image i} placeholders.
    """
    found: List[str] = []
    seen: set[str] = set()
    extractor = URLExtract()

    plain = strip_tags(text)

    # Remote URLs
    for url in extractor.find_urls(plain):
        u = url.strip()
        if u.lower().endswith(tuple(IMAGE_EXT)) and u not in seen:
            found.append(u)
            seen.add(u)

    # Local files
    tokens = re.findall(r'(?:"[^"]*"|\'[^\']*\'|\S+)', plain)
    for tok in tokens:
        t = tok.strip("\"'")
        if not t:
            continue
        cand = Path(t).expanduser().resolve()
        if safe_image(cand) and str(cand) not in seen:
            found.append(str(cand))
            seen.add(str(cand))

    cleaned = text
    for i, img in enumerate(found, 1):
        cleaned = cleaned.replace(img, f"{{Image {i}}}")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return found, cleaned


def _hash_key(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def compress_image_cached(
    path_str: str, max_kb: int = 1000, cache_dir: Optional[str] = None
) -> str:
    """Return base64 data-URI for a local image, compressed if needed.
    If a cache directory is provided (via arg or env LITELLM_IMAGE_CACHE_DIR),
    persist results across runs keyed by file path + mtime + size + max_kb.
    """
    path = Path(path_str)
    stat = path.stat()
    key = f"local:{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{max_kb}"
    cache_base = _get_cache_dir(cache_dir)
    if cache_base is not None:
        fp = cache_base / f"{_hash_key(key)}.b64"
        if fp.exists():
            try:
                return fp.read_text()
            except Exception as exc:
                log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
                raise

    img_bytes = path.read_bytes()
    max_bytes = max_kb * 1024

    if len(img_bytes) <= max_bytes:
        mime = f"image/{path.suffix[1:].lower()}"
        out = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"
        if cache_base is not None:
            try:
                fp.write_text(out)
            except Exception as exc:
                log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
                raise
        return out

    img = Image.open(io.BytesIO(img_bytes))
    quality = 85
    while quality > 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if len(buf.getvalue()) <= max_bytes:
            out = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
            if cache_base is not None:
                try:
                    fp.write_text(out)
                except Exception as exc:
                    log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
                    raise
            return out
        quality -= 10

    img.thumbnail((max(img.width // 2, 1), max(img.height // 2, 1)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=30)
    out = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    if cache_base is not None:
        try:
            fp.write_text(out)
        except Exception as exc:
            log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
            raise
    return out


def fetch_remote_image_cached(
    url: str, timeout: int = 10, cache_dir: Optional[str] = None
) -> Optional[str]:
    """Download remote image and return base64 data-URI. Cache by URL when enabled."""
    key = f"remote:{url}"
    cache_base = _get_cache_dir(cache_dir)
    if cache_base is not None:
        fp = cache_base / f"{_hash_key(key)}.b64"
        if fp.exists():
            try:
                return fp.read_text()
            except Exception as exc:
                log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
                raise

    try:
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
        mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
        out = f"data:{mime};base64,{base64.b64encode(r.content).decode()}"
        if cache_base is not None:
            try:
                fp.write_text(out)
            except Exception as exc:
                log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
                raise
        return out
    except Exception as exc:
        log_stage_error('image_helpers.py', exc, {'context': 'image_helpers.py'})
        raise
        return None


def compress_image(path_str: str, max_kb: int = 1000, *, cache_dir: Optional[str] = None) -> str:
    """Public wrapper to compress a local image and return a data URL.

    Allows explicit cache_dir override while honoring LITELLM_IMAGE_CACHE_DIR via _get_cache_dir.
    """
    return compress_image_cached(path_str, max_kb=max_kb, cache_dir=cache_dir)


def fetch_remote_image(url: str, *, cache_dir: Optional[str] = None) -> Optional[str]:
    """Public wrapper to fetch a remote image and return a data URL.

    Allows explicit cache_dir override while honoring LITELLM_IMAGE_CACHE_DIR via _get_cache_dir.
    Logs a warning when the fetch fails.
    """
    out = fetch_remote_image_cached(url, timeout=10, cache_dir=cache_dir)
    if out is None:
        logger.warning(f"Failed to fetch remote image: {url}")
    return out
