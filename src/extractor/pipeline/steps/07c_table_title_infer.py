#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger

from extractor.pipeline.utils.litellm_call import litellm_call


app = typer.Typer(help="07c: Infer table titles for null/weak titles only (gated).")

DISABLE_LLM = os.getenv("STAGE07_DISABLE_LLM", "").lower() in {"1", "true", "yes", "y"}


def _weak_title(title: str | None) -> bool:
    if not title:
        return True
    t = title.strip()
    return len(t) < 6


@app.command("run")
def run(
    canonical_json: Path = typer.Option(..., "--canonical", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    base = output_dir
    out_dir = base / "07c_table_title_infer"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json.read_text())
    sections: List[Dict[str, Any]] = payload.get("sections", [])

    titles: Dict[str, Dict[str, str]] = {}
    if DISABLE_LLM:
        for s in sections:
            sid = s.get("id")
            tmap: Dict[str, str] = {}
            for t in s.get("tables", []):
                if _weak_title(t.get("title")):
                    tmap[t.get("raw_table_id") or t.get("normalized_label") or f"tid_{id(t)}"] = (t.get("title") or "").strip()
            titles[sid] = tmap
    else:
        prompts = []
        index: List[tuple[str, str]] = []
        for s in sections:
            sid = s.get("id")
            for t in s.get("tables", []):
                if not _weak_title(t.get("title")):
                    continue
                key = t.get("raw_table_id") or t.get("normalized_label") or f"tid_{id(t)}"
                cols = (t.get("pandas_metrics") or {}).get("columns") or []
                rows = (t.get("pandas_df") or [])[:2]
                msg = (
                    "Suggest a concise, factual title for this table; no invented data; one short sentence.\n"
                    f"Columns: {cols}\nSample rows: {rows}"
                )
                prompts.append({
                    "model": os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL") or "openai/zai-org/GLM-4.5-Air",
                    "messages": [
                        {"role": "system", "content": [{"type": "text", "text": "You output ONLY a short title (no JSON)."}]},
                        {"role": "user", "content": [{"type": "text", "text": msg}]},
                    ],
                    "kwargs": {"temperature": 0, "top_p": 1, "timeout": 30}
                })
                index.append((sid, key))

        if prompts:
            out = __import__("asyncio").run(litellm_call(prompts, wrap_json=False, concurrency=min(4, int(os.getenv("STAGE07_CONCURRENCY", "4"))), desc="07c_table_title"))
        else:
            out = []
        for i, (sid, key) in enumerate(index):
            content = out[i].content if i < len(out) and out[i] else ""
            titles.setdefault(sid, {})[key] = (content or "").strip()

    outp = out_dir / "07c_table_title_infer.json"
    outp.write_text(json.dumps({"table_titles": titles}, indent=2, ensure_ascii=False))
    logger.success(f"07c: wrote {outp}")


if __name__ == "__main__":
    app()

