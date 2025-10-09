#!/usr/bin/env python3
"""
Step‑07 Prompt Lab: iterate prompt variants and models, capture artifacts.

Usage (examples)
  PYTHONPATH=./src \
  python debug/step07_prompt_lab.py \
    --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
    --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
    --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
    --index 0 \
    --models "openai/deepseek-ai/DeepSeek-V3.1,openai/zai-org/GLM-4.5-Air" \
    --guards strict,minimal \
    --include-images false \
    --timeout 60 --max-chars 8000 --out-dir scripts/artifacts/prompt_lab

  # Try Gemini if all fail
  PYTHONPATH=./src python debug/step07_prompt_lab.py ... --try-gemini true

Outputs
  scripts/artifacts/prompt_lab/
    run_<ts>/<model_slug>/<guard>/raw.txt
    run_<ts>/<model_slug>/<guard>/result.json

Notes
  - Bridges CHUTES_* → OPENAI_* and normalizes /v1 automatically.
  - Works without Stage‑07 imports; self‑contained.
  - Starts with text‑first prompting; images optional.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _bridge_env() -> None:
    base = os.getenv("CHUTES_API_BASE")
    key = os.getenv("CHUTES_API_KEY")
    if base and key:
        b = base.rstrip("/")
        if not b.endswith("/v1"):
            b = b + "/v1"
        os.environ.setdefault("OPENAI_BASE_URL", b)
        os.environ.setdefault("OPENAI_API_KEY", key)


def _read_inputs(sections: Path, tables: Path, figures: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    secs = json.loads(sections.read_text()).get("sections", [])
    tabs = json.loads(tables.read_text()).get("tables", [])
    figs = json.loads(figures.read_text()).get("figures", [])
    return secs, tabs, figs


def _sanitize_text(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    return " ".join(s.split())


def _extract_first_json(raw: str) -> Tuple[Any, str]:
    if not isinstance(raw, str) or not raw.strip():
        return None, "empty"
    s = raw.strip()
    try:
        return json.loads(s), "direct"
    except Exception:
        pass
    cleaned = s.replace("```json", "\n").replace("```", "\n").replace("`", "\n")
    start = None
    for i, ch in enumerate(cleaned):
        if ch in "{[":
            start = i
            break
    if start is None:
        return None, "no_brace"
    cand = cleaned[start:]
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


def _build_messages(sec: Dict[str, Any], guard: str, max_chars: int, *, include_images: bool, results_base_dir: Path | None) -> List[Dict[str, Any]]:
    # Guard presets
    if guard == "strict":
        system = (
            "You are a strict JSON reflow engine. Return exactly ONE JSON object with keys: "
            "reflowed_json, ocr_corrections, improvements_made, summary. "
            "No code fences or prose."
        )
        guard_text = (
            "Return ONLY one JSON object. Required keys: reflowed_json, ocr_corrections, improvements_made, summary.\n"
            "reflowed_json.blocks may contain: heading, paragraph, list, table, figure."
        )
    elif guard == "minimal":
        system = "Return JSON only."
        guard_text = "One JSON object. Keys: reflowed_json, ocr_corrections, improvements_made, summary."
    else:
        system = "Return JSON only."
        guard_text = "One JSON object with reflowed_json and related fields."

    title = _sanitize_text(sec.get("title", "Untitled"))
    p0 = int(sec.get("page_start") or 0)
    p1 = int(sec.get("page_end") or p0)
    text = _sanitize_text(sec.get("source_text") or sec.get("merged_text") or "")
    text = text[:max_chars]
    context = {
        "title": title,
        "page_start": p0,
        "page_end": p1,
        "table_count": len(sec.get("tables", [])),
        "figure_count": len(sec.get("figures", [])),
    }
    # Text part first
    user_parts: List[Dict[str, Any]] = [
        {"type": "text", "text": guard_text + "\nContext:\n" + json.dumps(context, ensure_ascii=False) + "\n\nText:\n" + text}
    ]
    # Optional image parts (section image → up to 2 table crops → first figure)
    if include_images and results_base_dir is not None:
        try:
            from extractor.pipeline.utils.image_io import (
                get_section_image_b64,
                get_table_image_b64,
                get_figure_image_b64,
            )
            # Section image
            b64 = get_section_image_b64(sec, results_base_dir)
            if b64:
                user_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
            # Up to 2 tables
            for t in (sec.get("tables") or [])[:2]:
                tb64 = get_table_image_b64(t, results_base_dir)
                if tb64:
                    user_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{tb64}"}})
            # First figure (optional)
            figs = sec.get("figures") or []
            if figs:
                fb64 = get_figure_image_b64(figs[0], results_base_dir)
                if fb64:
                    user_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{fb64}"}})
        except Exception:
            pass

    return [
        {"role": "system", "content": [{"type": "text", "text": system}]},
        {"role": "user", "content": user_parts},
    ]


async def _try_one(model: str, messages: List[Dict[str, Any]], timeout: int) -> Tuple[str, str, Any]:
    # Returns (content, error, parsed)
    from extractor.pipeline.utils.litellm_call import litellm_call

    try:
        out = await litellm_call(
            [
                {
                    "model": model,
                    "messages": messages,
                    "timeout": timeout,
                    "temperature": 0,
                    "top_p": 1,
                    "response_format": {"type": "json_object"},
                }
            ],
            wrap_json=False,
            concurrency=1,
            desc=f"prompt_lab:{model}",
            num_retries=0,
            request_timeout=timeout,
            show_progress=False,
        )
        first = out[0] if out else None
        if first is None:
            return "", "empty_response", None
        content = getattr(first, "content", None) or (first.get("content") if isinstance(first, dict) else str(first))
        parsed, strat = _extract_first_json(content)
        return content, "", {"parsed": parsed, "parse_strategy": strat}
    except Exception as e:
        return "", f"{type(e).__name__}: {e}", None


async def _run(args) -> int:
    _bridge_env()
    sections_path = Path(args.sections)
    secs, tabs, figs = _read_inputs(sections_path, Path(args.tables), Path(args.figures))
    if not secs:
        print("No sections found", file=sys.stderr)
        return 2
    idx = max(0, min(args.index, len(secs) - 1))
    sec = secs[idx]
    sid = str(sec.get("id", f"section_{idx}"))
    # minimal text fields if missing; also attach tables/figures by section_id
    if not (sec.get("source_text") or sec.get("merged_text")):
        blocks = sec.get("blocks", []) or []
        parts = [(b.get("text") or "").strip() for b in blocks if (b.get("text") or "").strip()]
        sec["source_text"] = "\n".join(parts)
        sec["merged_text"] = " ".join(parts)

    # Join tables/figures by section id
    sid = sec.get("id")
    if sid is not None:
        by_sid_t = {}
        for t in tabs:
            if t.get("section_id") == sid:
                by_sid_t.setdefault(sid, []).append(t)
        by_sid_f = {}
        for f in figs:
            if f.get("section_id") == sid:
                by_sid_f.setdefault(sid, []).append(f)
        sec.setdefault("tables", by_sid_t.get(sid, []))
        sec.setdefault("figures", by_sid_f.get(sid, []))

    models = [m.strip() for m in (args.models.split(",") if args.models else []) if m.strip()]
    if not models:
        # Fallback to env or a sensible default
        envm = os.getenv("LITELLM_VLM_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or "openai/zai-org/GLM-4.5-Air"
        models = [envm]
    guards = [g.strip() for g in (args.guards.split(",") if args.guards else ["strict"]) if g.strip()]

    ts = time.strftime("%Y%m%d_%H%M%S")
    root = Path(args.out_dir) / f"run_{ts}"
    root.mkdir(parents=True, exist_ok=True)
    summary: List[Dict[str, Any]] = []

    # Compute results_base_dir for images: ascend to pipeline root (…/pipeline)
    # Example sections path: data/results/pipeline/04_section_builder/json_output/04_sections.json
    try:
        results_base_dir = sections_path.parents[3]  # …/pipeline
    except Exception:
        results_base_dir = None

    for model in models:
        mslug = model.replace("/", "_")
        for guard in guards:
            messages = _build_messages(sec, guard, args.max_chars, include_images=args.include_images, results_base_dir=results_base_dir)
            content, err, parsed = await _try_one(model, messages, args.timeout)
            ok = bool(parsed and isinstance(parsed.get("parsed"), dict) and (
                parsed["parsed"].get("reflowed_json")
                or ("title" in parsed["parsed"] and "blocks" in parsed["parsed"])  # plausible for auto-wrap
            ))
            outdir = root / mslug / guard
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / "raw.txt").write_text(content or err or "")
            result = {
                "ok": ok,
                "model": model,
                "guard": guard,
                "parse_strategy": (parsed or {}).get("parse_strategy"),
                "has_reflowed_json": bool(parsed and isinstance(parsed.get("parsed"), dict) and parsed["parsed"].get("reflowed_json")),
                "wrapper_candidate": bool(parsed and isinstance(parsed.get("parsed"), dict) and ("title" in parsed["parsed"] and "blocks" in parsed["parsed"]))
            }
            (outdir / "result.json").write_text(json.dumps({**result, "json": (parsed or {}).get("parsed")}, indent=2, ensure_ascii=False))
            summary.append(result)

    # Optional Gemini try if all failed
    if args.try_gemini and all(not r["ok"] for r in summary):
        gmodel = "gemini/gemini-2.5-flash"
        messages = _build_messages(sec, guards[0], args.max_chars)
        content, err, parsed = await _try_one(gmodel, messages, args.timeout)
        ok = bool(parsed and isinstance(parsed.get("parsed"), dict) and parsed["parsed"].get("reflowed_json"))
        outdir = root / gmodel.replace("/", "_") / guards[0]
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "raw.txt").write_text(content or err or "")
        (outdir / "result.json").write_text(json.dumps({
            "ok": ok,
            "model": gmodel,
            "guard": guards[0],
            "parse_strategy": (parsed or {}).get("parse_strategy"),
            "json": (parsed or {}).get("parsed")
        }, indent=2, ensure_ascii=False))
        summary.append({"ok": ok, "model": gmodel, "guard": guards[0]})

    # Write run summary
    (root / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({"out_dir": str(root), "runs": summary}, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--figures", required=True)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--models", type=str, default="")
    ap.add_argument("--guards", type=str, default="strict")
    ap.add_argument("--include-images", type=str, default="false")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--max-chars", type=int, default=8000)
    ap.add_argument("--out-dir", type=str, default="scripts/artifacts/prompt_lab")
    ap.add_argument("--try-gemini", type=str, default="false")
    args = ap.parse_args()
    # Booleans via strings for simplicity
    args.include_images = args.include_images.lower() in ("1","true","yes","y")
    args.try_gemini = args.try_gemini.lower() in ("1","true","yes","y")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
