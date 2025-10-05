#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger

from extractor.pipeline.utils.litellm_call import litellm_call


app = typer.Typer(help="07b: Gated paragraph polish (temp=0).")


PARA_NOISE_THRESHOLD = float(os.getenv("PARA_NOISE_THRESHOLD", "0.18"))
DISABLE_LLM = os.getenv("STAGE07_DISABLE_LLM", "").lower() in {"1", "true", "yes", "y"}


def _noise_score(text: str) -> float:
    if not text:
        return 0.0
    t = text
    splits = t.count("-") + t.count(" ")
    repeat = sum(1 for tok in t.split() if len(tok) == 1)
    weird_caps = sum(1 for tok in t.split() if tok.isupper() and len(tok) > 3)
    L = max(1, len(t))
    return min(1.0, 0.06 * splits + 0.04 * repeat + 0.08 * weird_caps)


@app.command("run")
def run(
    canonical_json: Path = typer.Option(..., "--canonical", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    base = output_dir
    out_dir = base / "07b_paragraph_polish"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json.read_text())
    sections: List[Dict[str, Any]] = payload.get("sections", [])

    results: Dict[str, Dict[str, str]] = {}
    if DISABLE_LLM:
        for s in sections:
            sid = s.get("id")
            m: Dict[str, str] = {}
            for p in s.get("paragraphs", []):
                txt = p.get("text", "")
                if _noise_score(txt) >= PARA_NOISE_THRESHOLD:
                    m[p.get("pid")] = txt  # identity polish under offline
            results[sid] = m
    else:
        prompts = []
        index: List[tuple[str, str]] = []  # (sid, pid)
        for s in sections:
            sid = s.get("id")
            for p in s.get("paragraphs", []):
                txt = p.get("text", "")
                if _noise_score(txt) < PARA_NOISE_THRESHOLD:
                    continue
                pid = p.get("pid")
                index.append((sid, pid))
                prompts.append({
                    "model": os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL") or "openai/zai-org/GLM-4.5-Air",
                    "messages": [
                        {"role": "system", "content": [{"type": "text", "text": "You are a careful copy editor. Return ONLY corrected text (no JSON)."}]},
                        {"role": "user", "content": [{"type": "text", "text": f"Fix broken hyphenation and excessive spaces; keep wording.\n\nText:\n{txt}"}]},
                    ],
                    "kwargs": {"temperature": 0, "top_p": 1, "timeout": 30}
                })
        if prompts:
            out = __import__("asyncio").run(litellm_call(prompts, wrap_json=False, concurrency=min(4, int(os.getenv("STAGE07_CONCURRENCY", "4"))), desc="07b_polish"))
        else:
            out = []
        results = {}
        for i, (sid, pid) in enumerate(index):
            content = out[i].content if i < len(out) and out[i] else ""
            results.setdefault(sid, {})[pid] = (content or "").strip()

    outp = out_dir / "07b_paragraph_polish.json"
    outp.write_text(json.dumps({"polish": results}, indent=2, ensure_ascii=False))
    logger.success(f"07b: wrote {outp}")


if __name__ == "__main__":
    app()

