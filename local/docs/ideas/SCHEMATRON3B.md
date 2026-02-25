Below is an **updated version of the skill** (drop-in replacement shape) that adds what you asked:

- **Extract HTML tables deterministically** (via `pandas.read_html`)
- **Find `<img>` (and optionally `<video>/<source>`) references in the HTML**
- For images **within a configurable pixel-size window** (min/max), it:
  - loads the image (local files by default; optional remote fetch)
  - extracts **text** (via a **vision LLM** call; OpenAI-compatible endpoint)
  - outputs **original `src`**, resolved URL/path, **`alt`**, and dimensions

- Injects both `tables` and `media_text` into the Schematron context
- Keeps the **bounded self-improvement loop** (default `--max-attempts 3`)

This stays “tight” and deterministic where possible, and makes the media OCR/extraction pluggable.

---

## Updated folder layout

```text
.pi/skills/html-to-schema/
├── SKILL.md
├── run.sh
├── pyproject.toml
├── html_to_schema/
│   ├── __init__.py
│   ├── cli.py
│   ├── pipeline.py
│   ├── cleaning.py
│   ├── normalize.py
│   ├── sectionify.py
│   ├── render_md.py
│   ├── extract.py
│   ├── tables.py          # NEW: html table extraction -> JSON
│   ├── media.py           # NEW: discover/load images + thresholds
│   ├── vision_client.py   # NEW: vision text extraction (OpenAI-compatible)
│   ├── ollama_client.py
│   ├── schematron.py
│   ├── validate.py
│   └── util.py
└── sanity/
    ├── sample.html
    ├── sample.schema.json
    └── verify.py
```

---

## pyproject.toml (add deps)

Add these dependencies:

- `pandas`
- `pillow`

```toml
[project]
dependencies = [
  "typer>=0.12.3",
  "rich>=13.7.1",
  "loguru>=0.7.2",
  "httpx>=0.27.0",
  "beautifulsoup4>=4.12.3",
  "lxml>=5.2.2",
  "trafilatura>=1.12.2",
  "jsonschema>=4.23.0",
  "pandas>=2.2.2",
  "pillow>=10.4.0",
]
```

---

## CLI updates (new options)

### html_to_schema/cli.py (only showing the updated signature + pipeline call)

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional, Literal

import typer
from loguru import logger
from rich.console import Console

from html_to_schema.pipeline import run_pipeline
from html_to_schema.render_md import render_markdown
from html_to_schema.util import read_json_file, read_text_file, write_json_file, write_text_file

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

OutFormat = Literal["json", "md", "both"]
NormMode = Literal["off", "basic", "nfkc"]


@app.command()
def convert(
    html: Path = typer.Option(..., help="Path to local HTML file."),
    schema: Path = typer.Option(..., help="Path to JSON Schema file."),
    out: Path = typer.Option(Path("out.json"), help="Output JSON path."),
    out_format: OutFormat = typer.Option("json", help="Output format: json|md|both."),
    md_out: Path = typer.Option(Path("out.md"), help="Markdown output path (if md/both)."),
    ollama_base_url: str = typer.Option("http://localhost:11434", help="Ollama base URL."),
    model: str = typer.Option("Inference/Schematron:3B", help="Ollama model name/tag."),
    timeout_s: float = typer.Option(120.0, help="Ollama HTTP timeout seconds."),
    max_attempts: int = typer.Option(3, help="Max self-improvement attempts (default 3)."),
    max_html_chars: int = typer.Option(220_000, help="Initial max chars of cleaned HTML."),
    normalize: NormMode = typer.Option("nfkc", help="Normalization: off|basic|nfkc."),
    include_sections: bool = typer.Option(True, help="Include deterministic section hierarchy as model context."),
    emit_sections: bool = typer.Option(False, help="Emit 'sections' into JSON output (only if schema permits)."),

    # NEW: deterministic tables
    extract_tables: bool = typer.Option(True, help="Extract HTML <table> elements deterministically (pandas.read_html)."),
    max_tables: int = typer.Option(20, help="Max tables to include."),

    # NEW: media -> text extraction
    extract_media_text: bool = typer.Option(True, help="Extract text from qualifying <img> media and include src+alt."),
    min_image_px: int = typer.Option(128 * 128, help="Min image area (width*height) to process."),
    max_image_px: int = typer.Option(4000 * 4000, help="Max image area (width*height) to process."),
    min_image_dim: int = typer.Option(200, help="Min width AND height to process (helps skip icons)."),
    fetch_remote_media: bool = typer.Option(False, help="Allow fetching http(s) images referenced by HTML."),
    vision_api_base: Optional[str] = typer.Option(None, help="OpenAI-compatible API base for vision (e.g. Chutes)."),
    vision_api_key: Optional[str] = typer.Option(None, help="API key for vision endpoint."),
    vision_model: str = typer.Option("gpt-4o-mini", help="Vision model name on your vision endpoint."),
    vision_concurrency: int = typer.Option(8, help="Concurrent vision calls (batch)."),

    debug_dir: Optional[Path] = typer.Option(None, help="If set, writes per-attempt debug artifacts here."),
) -> None:
    if max_attempts < 1:
        raise typer.BadParameter("--max-attempts must be >= 1")
    if not html.exists():
        raise typer.BadParameter(f"HTML file not found: {html}")
    if not schema.exists():
        raise typer.BadParameter(f"Schema file not found: {schema}")

    raw_html = read_text_file(html)
    schema_obj = read_json_file(schema)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)

    result = run_pipeline(
        html_path=html,
        raw_html=raw_html,
        json_schema=schema_obj,
        ollama_base_url=ollama_base_url,
        model=model,
        timeout_s=timeout_s,
        max_attempts=max_attempts,
        max_html_chars=max_html_chars,
        normalize_mode=normalize,
        include_sections=include_sections,
        emit_sections=emit_sections,
        extract_tables=extract_tables,
        max_tables=max_tables,
        extract_media_text=extract_media_text,
        min_image_px=min_image_px,
        max_image_px=max_image_px,
        min_image_dim=min_image_dim,
        fetch_remote_media=fetch_remote_media,
        vision_api_base=vision_api_base,
        vision_api_key=vision_api_key,
        vision_model=vision_model,
        vision_concurrency=vision_concurrency,
        debug_dir=debug_dir,
    )

    write_json_file(out, result)
    console.print(f"[green]Wrote[/green] {out}")

    if out_format in ("md", "both"):
        md = render_markdown(result)
        write_text_file(md_out, md)
        console.print(f"[green]Wrote[/green] {md_out}")
```

---

## NEW: tables.py (HTML tables → JSON)

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger


def extract_html_tables_to_json(html: str, *, max_tables: int = 20) -> Dict[str, Any]:
    """
    Deterministically extract HTML <table> elements using pandas.read_html.
    Produces a stable JSON representation.
    """
    try:
        dfs = pd.read_html(html)  # lxml parser
    except ValueError:
        return {"tables": []}
    except Exception as e:
        logger.warning("pandas.read_html failed: {}", e)
        return {"tables": [], "error": str(e)}

    tables = []
    for i, df in enumerate(dfs[:max_tables]):
        # Convert to simple JSON with headers+rows
        headers = [str(c) for c in df.columns.tolist()]
        rows = df.astype(object).where(pd.notnull(df), None).values.tolist()
        tables.append(
            {
                "index": i,
                "headers": headers,
                "rows": rows,
                "source": {"type": "html_table", "index": i},
            }
        )
    return {"tables": tables}
```

---

## NEW: media.py (discover + load images; thresholds; include src+alt)

```python
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from PIL import Image
import io


@dataclass
class MediaItem:
    src_raw: str
    src_resolved: str
    alt: Optional[str]
    width: Optional[int]
    height: Optional[int]
    area: Optional[int]
    kind: str  # "image" | "video" (we only process images here)
    status: str  # "ok" | "skipped" | "error"
    reason: Optional[str] = None


def _is_remote(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https")


def discover_images(html: str, *, html_path: Path) -> List[Dict[str, Any]]:
    """
    Returns list of dicts: {src_raw, src_resolved, alt}
    - Resolves relative paths against the HTML file directory.
    - Keeps original src as seen in the HTML.
    """
    soup = BeautifulSoup(html, "lxml")
    base_dir = html_path.parent

    out: List[Dict[str, Any]] = []
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        alt = img.get("alt")
        alt = alt.strip() if isinstance(alt, str) else None

        # Resolve:
        if _is_remote(src):
            resolved = src
        else:
            # local relative path
            resolved = str((base_dir / src).resolve())

        out.append({"src_raw": src, "src_resolved": resolved, "alt": alt})
    return out


def load_image_bytes(
    src_resolved: str,
    *,
    fetch_remote: bool,
    timeout_s: float = 30.0,
) -> Optional[bytes]:
    """
    Loads image bytes from:
    - local file path
    - remote http(s) if fetch_remote=True
    """
    try:
        if _is_remote(src_resolved):
            if not fetch_remote:
                return None
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
                r = client.get(src_resolved)
                r.raise_for_status()
                return r.content
        else:
            return Path(src_resolved).read_bytes()
    except Exception as e:
        logger.warning("Failed to load image {}: {}", src_resolved, e)
        return None


def image_dimensions(image_bytes: bytes) -> tuple[Optional[int], Optional[int]]:
    try:
        im = Image.open(io.BytesIO(image_bytes))
        return int(im.width), int(im.height)
    except Exception:
        return None, None


def filter_media_by_pixels(
    discovered: List[Dict[str, Any]],
    *,
    fetch_remote: bool,
    min_area: int,
    max_area: int,
    min_dim: int,
) -> List[MediaItem]:
    """
    Loads images to measure pixel size; returns MediaItems with status.
    """
    items: List[MediaItem] = []

    for d in discovered:
        src_raw = d["src_raw"]
        src_resolved = d["src_resolved"]
        alt = d.get("alt")

        b = load_image_bytes(src_resolved, fetch_remote=fetch_remote)
        if b is None:
            items.append(
                MediaItem(
                    src_raw=src_raw,
                    src_resolved=src_resolved,
                    alt=alt,
                    width=None,
                    height=None,
                    area=None,
                    kind="image",
                    status="skipped",
                    reason="remote_fetch_disabled_or_load_failed",
                )
            )
            continue

        w, h = image_dimensions(b)
        if not w or not h:
            items.append(
                MediaItem(
                    src_raw=src_raw,
                    src_resolved=src_resolved,
                    alt=alt,
                    width=w,
                    height=h,
                    area=None,
                    kind="image",
                    status="skipped",
                    reason="cannot_read_dimensions",
                )
            )
            continue

        area = w * h
        if w < min_dim or h < min_dim:
            items.append(
                MediaItem(
                    src_raw=src_raw,
                    src_resolved=src_resolved,
                    alt=alt,
                    width=w,
                    height=h,
                    area=area,
                    kind="image",
                    status="skipped",
                    reason=f"below_min_dim({min_dim})",
                )
            )
            continue

        if area < min_area:
            items.append(
                MediaItem(
                    src_raw=src_raw,
                    src_resolved=src_resolved,
                    alt=alt,
                    width=w,
                    height=h,
                    area=area,
                    kind="image",
                    status="skipped",
                    reason=f"below_min_area({min_area})",
                )
            )
            continue

        if area > max_area:
            items.append(
                MediaItem(
                    src_raw=src_raw,
                    src_resolved=src_resolved,
                    alt=alt,
                    width=w,
                    height=h,
                    area=area,
                    kind="image",
                    status="skipped",
                    reason=f"above_max_area({max_area})",
                )
            )
            continue

        items.append(
            MediaItem(
                src_raw=src_raw,
                src_resolved=src_resolved,
                alt=alt,
                width=w,
                height=h,
                area=area,
                kind="image",
                status="ok",
            )
        )

    return items


def to_media_context(items: List[MediaItem], extracted_text: Dict[str, str]) -> Dict[str, Any]:
    """
    Builds JSON context for Schematron:
    includes src_raw, src_resolved, alt, dims, and extracted text (if any).
    """
    out = []
    for it in items:
        out.append(
            {
                "src": it.src_raw,                 # original URL/path as in HTML
                "resolved_src": it.src_resolved,   # resolved local path or remote URL
                "alt": it.alt,
                "width": it.width,
                "height": it.height,
                "area": it.area,
                "status": it.status,
                "reason": it.reason,
                "text": extracted_text.get(it.src_resolved) if it.status == "ok" else None,
            }
        )
    return {"media_text": out}
```

---

## NEW: vision_client.py (batched vision calls, concurrency)

This is the “Chutes/scillm-like” batching concept, implemented as a robust OpenAI-compatible client with concurrency.

```python
from __future__ import annotations

import base64
import asyncio
from typing import Dict, List, Optional

import httpx
from loguru import logger


def _b64_data_url(image_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _guess_mime(path_or_url: str) -> str:
    p = path_or_url.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".jpg") or p.endswith(".jpeg"):
        return "image/jpeg"
    if p.endswith(".webp"):
        return "image/webp"
    if p.endswith(".gif"):
        return "image/gif"
    # fallback; many endpoints accept jpeg
    return "image/jpeg"


async def _vision_one(
    client: httpx.AsyncClient,
    *,
    api_base: str,
    api_key: str,
    model: str,
    image_bytes: bytes,
    image_id: str,
    alt: Optional[str],
) -> str:
    """
    Calls OpenAI-compatible /v1/chat/completions with vision content.
    Returns extracted text.
    """
    url = f"{api_base.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}

    mime = _guess_mime(image_id)
    img_url = _b64_data_url(image_bytes, mime)

    prompt = (
        "Extract all readable text from this image. "
        "Preserve tables as plain text rows/columns where possible. "
        "Return ONLY the extracted text (no markdown fences)."
    )
    if alt:
        prompt += f"\nALT TEXT (from HTML): {alt}"

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You are a precise OCR+layout extraction engine."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": img_url}},
                ],
            },
        ],
    }

    r = await client.post(url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


async def extract_text_batched(
    *,
    api_base: str,
    api_key: str,
    model: str,
    images: List[dict],
    concurrency: int = 8,
    timeout_s: float = 120.0,
) -> Dict[str, str]:
    """
    images: list of {id, bytes, alt}
    Returns mapping id -> extracted_text
    """
    sem = asyncio.Semaphore(max(1, concurrency))
    results: Dict[str, str] = {}

    async with httpx.AsyncClient(timeout=timeout_s) as client:

        async def run_one(img: dict) -> None:
            async with sem:
                try:
                    txt = await _vision_one(
                        client,
                        api_base=api_base,
                        api_key=api_key,
                        model=model,
                        image_bytes=img["bytes"],
                        image_id=img["id"],
                        alt=img.get("alt"),
                    )
                    results[img["id"]] = txt
                except Exception as e:
                    logger.warning("Vision extraction failed for {}: {}", img["id"], e)
                    results[img["id"]] = ""

        await asyncio.gather(*(run_one(img) for img in images))

    return results
```

---

## pipeline.py updates (inject tables + media_text context)

Key changes:

- accept `html_path`
- extract tables + media within each attempt (after cleaning/focus)
- call vision batch when enabled and configured
- include `tables_json` and `media_text_json` in Schematron context

```python
from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from html_to_schema.cleaning import clean_html, CleaningMode, focus_main_container, slice_html_for_tokens
from html_to_schema.extract import extract_trafilatura, TrafilaturaResult
from html_to_schema.normalize import normalize_text, NormMode
from html_to_schema.sectionify import build_section_hierarchy
from html_to_schema.schematron import schematron_extract_json
from html_to_schema.tables import extract_html_tables_to_json
from html_to_schema.media import discover_images, filter_media_by_pixels, load_image_bytes, to_media_context
from html_to_schema.vision_client import extract_text_batched
from html_to_schema.validate import validate_or_errors
from html_to_schema.util import write_text_file, write_json_file


@dataclass(frozen=True)
class AttemptPlan:
    cleaning_mode: CleaningMode
    focus_main: bool
    html_slice_chars: Optional[int]
    prompt_strict: bool
    prompt_repair: bool


def _build_attempt_plans(max_attempts: int) -> list[AttemptPlan]:
    plans: list[AttemptPlan] = [
        AttemptPlan(CleaningMode.CONSERVATIVE, False, None, False, False),
        AttemptPlan(CleaningMode.FOCUSED_MAIN, True, 140_000, True, True),
        AttemptPlan(CleaningMode.AGGRESSIVE_BOILERPLATE, True, 100_000, True, True),
    ]
    return plans[:max_attempts]


def run_pipeline(
    *,
    html_path: Path,
    raw_html: str,
    json_schema: Dict[str, Any],
    ollama_base_url: str,
    model: str,
    timeout_s: float,
    max_attempts: int,
    max_html_chars: int,
    normalize_mode: NormMode,
    include_sections: bool,
    emit_sections: bool,

    extract_tables: bool,
    max_tables: int,

    extract_media_text: bool,
    min_image_px: int,
    max_image_px: int,
    min_image_dim: int,
    fetch_remote_media: bool,
    vision_api_base: Optional[str],
    vision_api_key: Optional[str],
    vision_model: str,
    vision_concurrency: int,

    debug_dir: Optional[Path],
) -> Dict[str, Any]:
    plans = _build_attempt_plans(max_attempts=max_attempts)
    last_err: str | None = None

    raw_html = normalize_text(raw_html, normalize_mode)

    for i, plan in enumerate(plans, start=1):
        attempt_id = f"attempt_{i:02d}"
        logger.info(
            "Attempt {}/{}: cleaning_mode={} focus_main={} slice_chars={} strict={} repair={}",
            i, len(plans),
            plan.cleaning_mode.value, plan.focus_main, plan.html_slice_chars,
            plan.prompt_strict, plan.prompt_repair,
        )

        cleaned = clean_html(raw_html, mode=plan.cleaning_mode)
        cleaned = normalize_text(cleaned, normalize_mode)

        if len(cleaned) > max_html_chars:
            cleaned = cleaned[:max_html_chars]
            logger.warning("Cleaned HTML truncated to max_html_chars={}", max_html_chars)

        if plan.focus_main:
            cleaned = focus_main_container(cleaned)
            cleaned = normalize_text(cleaned, normalize_mode)

        if plan.html_slice_chars is not None:
            cleaned = slice_html_for_tokens(cleaned, plan.html_slice_chars)

        section_outline = build_section_hierarchy(cleaned) if include_sections else None
        tf = extract_trafilatura(cleaned, normalize_mode=normalize_mode)

        # Deterministic HTML tables
        tables_json = extract_html_tables_to_json(cleaned, max_tables=max_tables) if extract_tables else {"tables": []}

        # Media text extraction (images only here; keeps src + alt)
        media_json = {"media_text": []}
        if extract_media_text:
            discovered = discover_images(cleaned, html_path=html_path)
            media_items = filter_media_by_pixels(
                discovered,
                fetch_remote=fetch_remote_media,
                min_area=min_image_px,
                max_area=max_image_px,
                min_dim=min_image_dim,
            )

            # Prepare bytes for qualifying images
            qualifying = []
            for it in media_items:
                if it.status != "ok":
                    continue
                b = load_image_bytes(it.src_resolved, fetch_remote=fetch_remote_media)
                if not b:
                    continue
                qualifying.append({"id": it.src_resolved, "bytes": b, "alt": it.alt})

            extracted_map: Dict[str, str] = {}
            if qualifying:
                if not (vision_api_base and vision_api_key):
                    logger.warning("extract_media_text enabled but vision_api_base/api_key not set; skipping OCR.")
                else:
                    extracted_map = asyncio.run(
                        extract_text_batched(
                            api_base=vision_api_base,
                            api_key=vision_api_key,
                            model=vision_model,
                            images=qualifying,
                            concurrency=vision_concurrency,
                            timeout_s=timeout_s,
                        )
                    )

            media_json = to_media_context(media_items, extracted_map)

        raw_model_out = schematron_extract_json(
            cleaned_html=cleaned,
            trafilatura=tf,
            json_schema=json_schema,
            ollama_base_url=ollama_base_url,
            model=model,
            timeout_s=timeout_s,
            strict=plan.prompt_strict,
            repair_instructions=None,
            section_outline=section_outline,
            tables_json=tables_json,
            media_json=media_json,
        )

        try:
            obj = json.loads(raw_model_out.strip())
        except Exception as e:
            last_err = f"{attempt_id}: JSON parse error: {e}"
            _write_debug(debug_dir, attempt_id, cleaned, tf, raw_model_out, {
                "parse_error": str(e),
                "section_outline": section_outline,
                "tables_json": tables_json,
                "media_json": media_json,
            })
            continue

        if emit_sections and section_outline is not None:
            obj.setdefault("sections", section_outline.get("sections"))

        ok, errors = validate_or_errors(json_schema, obj)
        if ok:
            _write_debug(debug_dir, attempt_id, cleaned, tf, raw_model_out, {
                "status": "ok",
                "section_outline": section_outline,
                "tables_json": tables_json,
                "media_json": media_json,
            })
            return obj

        last_err = f"{attempt_id}: schema validation failed with {len(errors)} errors"
        logger.warning(last_err)

        if plan.prompt_repair:
            repair_text = _format_errors_for_repair(errors)
            raw_model_out_2 = schematron_extract_json(
                cleaned_html=cleaned,
                trafilatura=tf,
                json_schema=json_schema,
                ollama_base_url=ollama_base_url,
                model=model,
                timeout_s=timeout_s,
                strict=True,
                repair_instructions=repair_text,
                section_outline=section_outline,
                tables_json=tables_json,
                media_json=media_json,
            )
            try:
                obj2 = json.loads(raw_model_out_2.strip())
            except Exception as e:
                last_err = f"{attempt_id}: repair JSON parse error: {e}"
                _write_debug(debug_dir, attempt_id, cleaned, tf, raw_model_out_2, {
                    "schema_errors": errors,
                    "repair_parse_error": str(e),
                    "section_outline": section_outline,
                    "tables_json": tables_json,
                    "media_json": media_json,
                }, suffix="_repair")
                continue

            if emit_sections and section_outline is not None:
                obj2.setdefault("sections", section_outline.get("sections"))

            ok2, errors2 = validate_or_errors(json_schema, obj2)
            if ok2:
                _write_debug(debug_dir, attempt_id, cleaned, tf, raw_model_out_2, {
                    "status": "ok_after_repair",
                    "section_outline": section_outline,
                    "tables_json": tables_json,
                    "media_json": media_json,
                }, suffix="_repair")
                return obj2

            last_err = f"{attempt_id}: repair validation failed with {len(errors2)} errors"
            _write_debug(debug_dir, attempt_id, cleaned, tf, raw_model_out_2, {
                "schema_errors": errors,
                "schema_errors_after_repair": errors2,
                "section_outline": section_outline,
                "tables_json": tables_json,
                "media_json": media_json,
            }, suffix="_repair")

    raise RuntimeError(last_err or "Failed to produce schema-valid JSON.")


def _format_errors_for_repair(errors: list[dict[str, Any]]) -> str:
    lines = []
    for e in errors[:25]:
        lines.append(f"- path={e.get('path')} error={e.get('message')}")
    return "Fix the JSON to satisfy these schema validation errors:\n" + "\n".join(lines)


def _write_debug(
    debug_dir: Optional[Path],
    attempt_id: str,
    cleaned_html: str,
    tf: TrafilaturaResult,
    raw_model_output: str,
    meta: Dict[str, Any],
    suffix: str = "",
) -> None:
    if debug_dir is None:
        return
    adir = debug_dir / f"{attempt_id}{suffix}"
    adir.mkdir(parents=True, exist_ok=True)

    write_text_file(adir / "cleaned.html", cleaned_html)
    write_json_file(adir / "trafilatura.json", tf.to_dict())
    write_text_file(adir / "model_output.txt", raw_model_output)
    write_json_file(adir / "meta.json", meta)
```

---

## schematron.py update (accept `tables_json` and `media_json`)

Only the signature + prompt assembly changes:

```python
def schematron_extract_json(
    *,
    cleaned_html: str,
    trafilatura: TrafilaturaResult,
    json_schema: Dict[str, Any],
    ollama_base_url: str,
    model: str,
    timeout_s: float,
    strict: bool,
    repair_instructions: Optional[str],
    section_outline: Optional[Dict[str, Any]],
    tables_json: Optional[Dict[str, Any]],
    media_json: Optional[Dict[str, Any]],
) -> str:
    ...
    if tables_json is not None:
        parts.append("DETERMINISTIC HTML TABLES (preferred source):\n" + json.dumps(tables_json, indent=2) + "\n")

    if media_json is not None:
        parts.append(
            "MEDIA TEXT EXTRACTION (images with src/alt/dims; may include OCR text):\n"
            + json.dumps(media_json, indent=2)
            + "\n"
        )
    ...
```

And you keep the existing rules: “prefer deterministic tables; don’t invent facts.”

---

## What you get (per your requirement)

Each qualifying image yields an entry like:

```json
{
  "src": "images/specs.png",
  "resolved_src": "/abs/path/to/images/specs.png",
  "alt": "Spec table for model X",
  "width": 1200,
  "height": 800,
  "area": 960000,
  "status": "ok",
  "reason": null,
  "text": "…extracted text…"
}
```

And this is included in the prompt context for Schematron so it can fill your schema.

---

## Usage examples

### Default (tables + media enabled, local images only)

```bash
./run.sh convert --html page.html --schema schema.json --out out.json
```

### Enable remote image fetch + Chutes/OpenAI-compatible vision OCR

```bash
./run.sh convert \
  --html page.html \
  --schema schema.json \
  --out out.json \
  --fetch-remote-media \
  --vision-api-base https://YOUR_ENDPOINT \
  --vision-api-key $YOUR_KEY \
  --vision-model gpt-4o-mini \
  --vision-concurrency 16
```

### Tight pixel thresholds (skip icons; skip huge wallpapers)

```bash
./run.sh convert \
  --html page.html --schema schema.json --out out.json \
  --min-image-dim 250 \
  --min-image-px 65536 \
  --max-image-px 9000000
```

---

## One important caveat (so you don’t get bitten)

If your schema has `additionalProperties: false`, **do not inject `sections`** unless your schema includes it. Same principle if you later decide to “emit” `tables` or `media_text` into the final JSON—either:

- define those fields in the schema, or
- keep them as _prompt-only context_ (what I’m doing by default).

If you paste your actual JSON Schema, I can also make the skill _schema-aware_ about where to place:

- `tables`
- `media_text`
- `sections`
  so it never fails on `additionalProperties: false`.
