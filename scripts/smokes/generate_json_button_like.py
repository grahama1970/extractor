#!/usr/bin/env python3
"""
Deprecated: Generate JSON button-like smoke (litellm). Extractor is SciLLM-only; this smoke is kept as a no-op.

- Loads a known table image fixture (tests/stage07_manual/images/table1.png)
- Applies the same 20% expansion logic on a given bounding box (normalized coords)
- Crops with PIL, encodes as data:image/png;base64
- Calls litellm_call with the exact JSON schema prompt (no max tokens specified)
- Asserts the returned JSON has keys: title (str), columns (list[str]), data (list[list])
- Saves a JSON report artifact under scripts/artifacts/

Usage:
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  python scripts/smokes/generate_json_button_like.py
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from PIL import Image
from dotenv import load_dotenv, find_dotenv

print("SKIP: generate_json_button_like smoke deprecated (SciLLM-only)")
raise SystemExit(0)


def expand_box(
    x: float, y: float, w: float, h: float, factor: float = 1.2
) -> tuple[float, float, float, float]:
    """Expand a normalized box by factor around its center, clamped to [0,1]."""

    def clamp(v: float, lo=0.0, hi=1.0) -> float:
        return max(lo, min(hi, v))

    cx = x + w / 2.0
    cy = y + h / 2.0
    nw = clamp(w * factor)
    nh = clamp(h * factor)
    nx = clamp(cx - nw / 2.0)
    ny = clamp(cy - nh / 2.0)
    return nx, ny, nw, nh


def crop_to_data_url(img: Image.Image, box_norm: tuple[float, float, float, float]) -> str:
    """Crop the image using a normalized box and return a PNG data URL."""
    nx, ny, nw, nh = box_norm
    W, H = img.size
    sx = int(round(nx * W))
    sy = int(round(ny * H))
    sw = int(round(min(W - sx, nw * W)))
    sh = int(round(min(H - sy, nh * H)))
    if sw <= 2 or sh <= 2:
        raise ValueError("crop too small")
    region = img.crop((sx, sy, sx + sw, sy + sh))
    buf = io.BytesIO()
    region.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


async def run() -> Dict[str, Any]:
    load_dotenv(find_dotenv())

    # Fixture image with a visible table
    root = Path(__file__).resolve().parents[2]
    fixture = root / "tests/stage07_manual/images/table1.png"
    if not fixture.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture}")
    img = Image.open(fixture).convert("RGBA")

    # Use most of the image as the initial box (normalized)
    x, y, w, h = 0.05, 0.05, 0.90, 0.90
    box_expanded = expand_box(x, y, w, h, 1.2)
    data_url = crop_to_data_url(img, box_expanded)

    prompt = (
        "You are an expert table extractor. Given an image of a table from a PDF, return ONLY a strict JSON object with EXACT keys and types:\n\n"
        "{\n"
        '  "title": string,            // concise title; if inferred, prefix with INFERRED_\n'
        '  "columns": string[],        // header cells as strings\n'
        '  "data": string[][]          // row-major 2D array of cell text\n'
        "}\n\n"
        "Rules:\n- Respond with a single JSON object only (no markdown, no code fences, no commentary).\n- Do not include any extra keys.\n- Normalize whitespace; keep cell contents as plain strings."
    )

    params = {
        "model": os.getenv("LITELLM_DEFAULT_MODEL", "gemini/gemini-2.5-flash"),
        "text": prompt,
        "image": data_url,
    }

    # Call litellm_call with JSON mode; no max token restriction is explicitly passed here
    results = await litellm_call(
        [params],
        wrap_json=True,
        response_format="json_object",
        desc="Generate JSON Smoke",
        show_progress=False,
        concurrency=1,
    )
    out = results[0] if results else ""

    # Normalize result to dict
    obj: Dict[str, Any]
    if isinstance(out, str):
        try:
            obj = json.loads(out)
        except Exception as e:
            return {"ok": False, "error": f"non_json_output: {e}", "raw": out[:2000]}
    else:
        content = getattr(out, "content", None)
        if isinstance(content, str):
            try:
                obj = json.loads(content)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"non_json_output: {e}",
                    "raw": (content or "")[:2000],
                }
        else:
            return {"ok": False, "error": "empty_output"}

    # Validate schema presence
    title = obj.get("title")
    columns = obj.get("columns")
    data = obj.get("data")
    ok = isinstance(title, str) and isinstance(columns, list) and isinstance(data, list)
    return {"ok": ok, "data": obj, "error": None if ok else "missing_keys_or_types"}


def main() -> int:
    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run())
    ts = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
    out_path = out_dir / f"generate_json_button_like_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artifact: {out_path}")
    if report.get("ok"):
        print("generate_json_button_like: OK")
        return 0
    else:
        print("generate_json_button_like: FAIL", report.get("error") or "unknown")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
