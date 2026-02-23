#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv, find_dotenv
from litellm import acompletion

load_dotenv(find_dotenv(), override=False)

MODELS = [
    "openai/gpt-5-mini",
    "openai/gpt-5",
    "gemini/gemini-2.5-flash",
    "moonshot/kimi-k2-turbo-preview",
]


def strip_fences_and_crop(s: str) -> str:
    if not s:
        return s
    s2 = s.strip()
    if s2.startswith("```"):
        s2 = s2.split("\n", 1)[1] if "\n" in s2 else s2
        if s2.endswith("```"):
            s2 = s2[:-3]
    s2 = s2.strip()
    if s2 and (s2[0] != "{" or s2[-1] != "}"):
        a = s2.find("{")
        b = s2.rfind("}")
        if a != -1 and b != -1 and b > a:
            s2 = s2[a : b + 1]
    return s2


def parse_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(strip_fences_and_crop(s))
    except Exception:
        return None


def image_file_to_data_url(path: Path) -> str:
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }.get(path.suffix.lower(), "application/octet-stream")
    data = path.read_bytes()
    import base64

    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


async def call_model(
    model: str, system_text: str, user_text: str, image_url: str
) -> Tuple[str, Dict[str, Any]]:
    messages = [
        {"role": "system", "content": system_text},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]
    extras: Dict[str, Any] = {}
    if model.startswith("openai/"):
        extras["response_format"] = {"type": "json_object"}
    resp = await acompletion(model=model, messages=messages, **extras)
    content = getattr(resp.choices[0].message, "content", None) or getattr(resp, "text", None) or ""
    usage = getattr(resp, "usage", None)
    # Prefer provider-reported cost when available
    hidden = getattr(resp, "_hidden_params", {}) or {}
    response_cost = None
    if isinstance(hidden, dict):
        response_cost = hidden.get("response_cost")
    return content or "", {
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
            "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
            "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        },
        "response_cost": response_cost,
    }


def estimate_cost(
    model: str, usage: Dict[str, Any], response_cost: Optional[float]
) -> Optional[float]:
    # Use provider-reported cost if present
    if isinstance(response_cost, (int, float)):
        return float(response_cost)
    # Simple heuristic map (USD per 1K tokens) — adjust as needed
    PRICES = {
        "openai/gpt-5-mini": (0.0005, 0.0015),
        "openai/gpt-5": (0.003, 0.009),
        "gemini/gemini-2.5-flash": (0.00035, 0.00105),
        # Moonshot Kimi pricing (per 1K): from https://platform.moonshot.ai/docs/pricing/chat
        # kimi-k2-turbo-preview: Input (cache miss) $2.40 / 1M => 0.0024 / 1K; Output $10.00 / 1M => 0.01 / 1K
        "moonshot/kimi-k2-turbo-preview": (0.0024, 0.01),
    }
    inp, out = PRICES.get(model, (None, None))
    if inp is None:
        return None
    pt = usage.get("prompt_tokens") or 0
    ct = usage.get("completion_tokens") or 0
    return (pt / 1000.0) * (inp or 0) + (ct / 1000.0) * (out or 0)


def evaluate_structure(parsed: Dict[str, Any], tables_path: Optional[Path]) -> Dict[str, Any]:
    """Strict structural checks for one section with:
    - exactly 1 merged table block with an INFERRED title and columns matching Stage 05 shape when available
    - exactly 1 figure block with an INFERRED title
    - at least one contiguous text block with >=150 chars (good ingestion chunk)
    """
    out = {
        "has_reflowed_json": False,
        "table_count": 0,
        "figure_count": 0,
        "table_title_inferred": False,
        "figure_title_inferred": False,
        "table_shape_ok": None,
        "has_good_text": False,
    }
    if not isinstance(parsed, dict):
        return out
    rj = parsed.get("reflowed_json")
    if not isinstance(rj, dict):
        return out
    out["has_reflowed_json"] = True
    blocks = rj.get("blocks") or []
    # Counts
    tables = [b for b in blocks if isinstance(b, dict) and b.get("type") == "table"]
    figures = [b for b in blocks if isinstance(b, dict) and b.get("type") == "figure"]
    out["table_count"] = len(tables)
    out["figure_count"] = len(figures)

    # Titles must be INFERRED (case-insensitive contains)
    def _is_inferred_title(title: Any) -> bool:
        return isinstance(title, str) and ("inferred" in title.lower()) and len(title.strip()) >= 9

    if tables:
        t0 = tables[0]
        out["table_title_inferred"] = _is_inferred_title(t0.get("title"))
        if tables_path and tables_path.exists():
            try:
                tdata = json.loads(tables_path.read_text())
                tlist = tdata.get("tables") or []
                if tlist:
                    pm = tlist[0].get("pandas_metrics") or {}
                    shape = pm.get("shape") or []
                    rows = len((t0.get("content") or {}).get("rows") or t0.get("rows") or [])
                    cols = len((t0.get("content") or {}).get("columns") or t0.get("columns") or [])
                    out["table_shape_ok"] = (
                        isinstance(shape, list)
                        and len(shape) == 2
                        and cols == int(shape[1] or 0)
                        and rows >= max(1, int(shape[0] or 0))
                    )
            except Exception:
                out["table_shape_ok"] = None

    if figures:
        f0 = figures[0]
        out["figure_title_inferred"] = _is_inferred_title(f0.get("title"))

    # Good contiguous text check (accept text under 'text' or 'content')
    def _get_text_content(b: Dict[str, Any]) -> str:
        t = b.get("text") if isinstance(b.get("text"), str) else b.get("content")
        return t if isinstance(t, str) else ""

    text_blocks = [
        b
        for b in blocks
        if isinstance(b, dict) and b.get("type") == "text" and isinstance(_get_text_content(b), str)
    ]
    out["has_good_text"] = any(len(_get_text_content(b).strip()) >= 150 for b in text_blocks)
    return out


async def main() -> None:
    base = Path("tests/stage07_manual")
    outdir = base / "evals"
    outdir.mkdir(parents=True, exist_ok=True)

    # Load Stage 07-like inputs
    context_text = (base / "context_text.txt").read_text(encoding="utf-8")
    img_url = image_file_to_data_url(base / "images" / "section.png")

    # Optional Stage 05 tables for shape/columns hints
    tables_path = Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json")
    hint_cols: list[str] = []
    hint_shape: list[int] | None = None
    if tables_path.exists():
        try:
            tdata = json.loads(tables_path.read_text())
            tlist = tdata.get("tables") or []
            if tlist:
                pm = tlist[0].get("pandas_metrics") or {}
                hint_shape = pm.get("shape") or None
                hint_cols = [str(c) for c in (pm.get("columns") or [])]
        except Exception:
            hint_shape = None
            hint_cols = []

    # Build stricter system prompt: 1 section, 1 merged table (INFERRED title), 1 figure (INFERRED title), good contiguous text
    system_text = (
        "Return ONLY a JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. "
        "No code fences. In reflowed_json.blocks: produce exactly 1 table block and exactly 1 figure block. "
        "Table: MERGE any fragmented/continued tables into a single logical table; set title to 'INFERRED: ...'; "
        "columns must match the provided hints (count and order) when given; do not alter cell values; include rows. "
        "Figure: include a figure block with title 'INFERRED: ...' and a short caption; set image_ref when applicable. "
        "Also include contiguous text blocks that read well as a self-contained knowledge chunk (not just bullets)."
    )

    # Compose user text with compact hints from Stage 05
    hint_text = ""
    if hint_cols or hint_shape:
        hint_text = f"\n\nTable Hints:\n- columns: {json.dumps(hint_cols, ensure_ascii=False)}\n- shape: {json.dumps(hint_shape)}\n"
    user_text = (context_text[:2400] + hint_text).strip()

    results: List[Dict[str, Any]] = []
    for model in MODELS:
        print(f"\n=== Evaluating {model} ===")
        content, meta = await call_model(model, system_text, user_text, img_url)
        parsed = parse_json(content)
        struct = evaluate_structure(parsed or {}, tables_path if tables_path.exists() else None)
        # ok means: reflowed_json exists; exactly 1 table and 1 figure; both titles inferred; good text; shape ok or unknown
        ok = (
            struct["has_reflowed_json"]
            and struct["table_count"] == 1
            and struct["figure_count"] == 1
            and struct["table_title_inferred"]
            and struct["figure_title_inferred"]
            and struct["has_good_text"]
            and (struct["table_shape_ok"] in (True, None))
        )
        usage = meta.get("usage", {})
        cost = estimate_cost(model, usage, meta.get("response_cost")) or None
        mslug = model.replace("/", "__")
        (outdir / f"{mslug}__raw.txt").write_text(content or "", encoding="utf-8")
        if parsed:
            (outdir / f"{mslug}__parsed.json").write_text(
                json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        r = {"model": model, "ok": ok, "usage": usage, "est_cost_usd": cost, "structure": struct}
        results.append(r)
        print(json.dumps(r, indent=2))

    # pick recommendation: OK first, then lowest cost
    candidates = [r for r in results if r["ok"]]
    if candidates:
        best = sorted(
            candidates, key=lambda r: (r["est_cost_usd"] if r["est_cost_usd"] is not None else 1e9)
        )[0]
    else:
        best = sorted(
            results, key=lambda r: (r["est_cost_usd"] if r["est_cost_usd"] is not None else 1e9)
        )[0]
    summary = {"results": results, "recommendation": best}
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nRecommendation:")
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
