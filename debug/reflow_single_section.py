#!/usr/bin/env python3
"""
Single-section Stage 07 debug runner (self-contained).

Purpose
- Reproduce the multimodal reflow call for ONE section only.
- Bridge CHUTES_* → OPENAI_* if set; normalize base URL.
- Build a compact prompt with a strict JSON guard.
- Call litellm_call directly and robustly extract JSON.
- Save artifacts under scripts/artifacts/ for inspection.

Usage
  PYTHONPATH=./src \
  python debug/reflow_single_section.py \
    --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
    --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
    --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
    --index 0 --timeout 45

Notes
- This is intentionally minimal and avoids importing the large Stage 07 module.
- Images are omitted by default to reduce first-token latency; add later if desired.
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import Any, Dict, List


# Bridge CHUTES_* → OPENAI_* and normalize base URL
def _bridge_env() -> None:
    base = os.getenv("CHUTES_API_BASE")
    key = os.getenv("CHUTES_API_KEY")
    if base and key:
        b = base.rstrip("/")
        if not b.endswith("/v1"):
            b = b + "/v1"
        os.environ.setdefault("OPENAI_BASE_URL", b)
        os.environ.setdefault("OPENAI_API_KEY", key)


def _first_nonempty_text(sec: Dict[str, Any], max_chars: int = 8000) -> str:
    raw = sec.get("source_text") or sec.get("merged_text") or ""
    if not isinstance(raw, str):
        raw = str(raw)
    raw = raw.replace("\u00a0", " ")
    raw = " ".join(raw.split())
    return raw[:max_chars]


def _extract_first_json_object(raw: str):
    if not isinstance(raw, str) or not raw.strip():
        return None, "empty"
    s = raw.strip()
    try:
        return json.loads(s), "direct"
    except Exception:
        pass
    cleaned = s.replace("```json", "\n").replace("```", "\n").replace("`", "\n")
    start_idx = None
    for i, ch in enumerate(cleaned):
        if ch in "{[":
            start_idx = i
            break
    if start_idx is None:
        return None, "no_brace"
    cand = cleaned[start_idx:]
    depth = 0
    in_str = False
    esc = False
    quote = ''
    end = None
    for i, ch in enumerate(cand):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        else:
            if ch == '"' or ch == "'":
                in_str = True
                quote = ch
                continue
            if ch in "{[":
                depth += 1
            elif ch in "]}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    if end is not None:
        snippet = cand[:end]
        try:
            return json.loads(snippet), "scan"
        except Exception:
            import re as _re

            tmp = _re.sub(r",(\s*[}\]])", r"\1", snippet)
            tmp = _re.sub(r"//.*?$", "", tmp, flags=_re.MULTILINE)
            tmp = _re.sub(r"/\*.*?\*/", "", tmp, flags=_re.DOTALL)
            try:
                return json.loads(tmp.strip()), "repaired"
            except Exception:
                return None, "repaired_failed"
    return None, "scan_failed"


async def _run(args) -> int:
    _bridge_env()
    try:
        from extractor.pipeline.utils.litellm_call import litellm_call
    except Exception as e:
        print(f"Failed to import litellm_call: {e}", file=sys.stderr)
        return 2

    sec_p = Path(args.sections)
    tab_p = Path(args.tables)
    fig_p = Path(args.figures)
    if not (sec_p.exists() and tab_p.exists() and fig_p.exists()):
        print("One or more input files do not exist.", file=sys.stderr)
        return 2
    sections = json.loads(sec_p.read_text()).get("sections", [])
    tables = json.loads(tab_p.read_text()).get("tables", [])
    figures = json.loads(fig_p.read_text()).get("figures", [])

    if not sections:
        print("No sections found in sections JSON.", file=sys.stderr)
        return 2

    # Build simple joins by section_id
    tables_by_sid: Dict[str, List[Dict[str, Any]]] = {}
    for t in tables:
        sid = t.get("section_id")
        if sid is not None:
            tables_by_sid.setdefault(sid, []).append(t)
    figs_by_sid: Dict[str, List[Dict[str, Any]]] = {}
    for f in figures:
        sid = f.get("section_id")
        if sid is not None:
            figs_by_sid.setdefault(sid, []).append(f)

    idx = args.index if args.index is not None else 0
    if idx < 0 or idx >= len(sections):
        print(f"Section index out of range: {idx} (size={len(sections)})", file=sys.stderr)
        return 2
    sec = sections[idx]
    sid = sec.get("id", f"sec_{idx}")
    sec["tables"] = tables_by_sid.get(sid, [])
    sec["figures"] = figs_by_sid.get(sid, [])
    # Minimal text fields
    src_text = sec.get("source_text") or sec.get("merged_text")
    if not src_text:
        blocks = sec.get("blocks", []) or []
        parts = [ (b.get("text") or "").strip() for b in blocks if (b.get("text") or "").strip() ]
        sec["source_text"] = "\n".join(parts)
        sec["merged_text"] = " ".join(parts)

    model = (
        args.model
        or os.getenv("LITELLM_VLM_MODEL")
        or os.getenv("LITELLM_DEFAULT_MODEL")
        or "openai/deepseek-ai/DeepSeek-V3-0324-turbo"
    )
    guard = (
        "Return ONLY one JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary.\n"
        "- reflowed_json.blocks must be an array of {type, ...} where type ∈ {paragraph, list, table, figure}.\n"
        "- Do not include markdown fences or commentary."
    )
    context = {
        "title": sec.get("title", "Untitled"),
        "level": sec.get("level", 0),
        "text": _first_nonempty_text(sec, max_chars=args.max_chars),
        "table_count": len(sec.get("tables", [])),
        "figure_count": len(sec.get("figures", [])),
    }
    messages = [
        {"role": "system", "content": [{"type": "text", "text": "You are a JSON-only reflow engine."}]},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": guard + "\nContext:\n" + json.dumps(context, ensure_ascii=False)[:6000]},
            ],
        },
    ]

    # Call once
    out = await litellm_call(
        [
            {
                "model": model,
                "messages": messages,
                "timeout": args.timeout,
                "temperature": 0,
            }
        ],
        wrap_json=False,
        concurrency=1,
        desc=f"debug:reflow_single:{sid}",
        num_retries=0,
        request_timeout=args.timeout,
        show_progress=False,
    )
    # Tolerate multiple return shapes: object with .content, dict with 'content', or raw string
    first = out[0] if out else None
    if first is None:
        content = ""
    elif hasattr(first, "content"):
        content = first.content or ""
    elif isinstance(first, dict) and "content" in first:
        content = first.get("content") or ""
    else:
        content = str(first)
    parsed, strat = _extract_first_json_object(content)
    ok = isinstance(parsed, dict) and isinstance(parsed.get("reflowed_json"), dict)

    # Save artifacts
    art = Path("scripts/artifacts")
    art.mkdir(parents=True, exist_ok=True)
    (art / f"reflow_single_{sid}_raw.txt").write_text(content)
    result_payload = {
        "ok": ok,
        "model": model,
        "parse_strategy": strat,
        "section_id": sid,
        "response_excerpt": content[:400],
        "json": parsed if isinstance(parsed, (dict, list)) else None,
    }
    (art / f"reflow_single_{sid}_result.json").write_text(json.dumps(result_payload, indent=2, ensure_ascii=False))
    print(json.dumps(result_payload, indent=2, ensure_ascii=False))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--figures", required=True)
    ap.add_argument("--index", type=int, default=0, help="Section index to process (default: 0)")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--model", type=str, default="", help="Override model (e.g., openai/deepseek-ai/DeepSeek-V3-0324-turbo)")
    ap.add_argument("--max-chars", type=int, default=6000)
    args = ap.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
