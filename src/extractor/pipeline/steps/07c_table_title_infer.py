#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    verified03_json: Optional[Path] = typer.Option(None, "--verified03", help="Path to 03_verified_blocks.json"),
):
    base = output_dir
    out_dir = base / "07c_table_title_infer"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json.read_text())
    sections: List[Dict[str, Any]] = payload.get("sections", [])

    titles: Dict[str, Dict[str, str]] = {}
    cues = _stage03_label_texts(verified03_json) if verified03_json else set()
    if DISABLE_LLM:
        for s in sections:
            sid = s.get("id")
            tmap: Dict[str, str] = {}
            for t in s.get("tables", []):
                if _weak_title(t.get("title")):
                    key = t.get("raw_table_id") or t.get("normalized_label") or f"tid_{id(t)}"
                    # Mnemonic skip
                    header_tokens = [str(c) for c in ((t.get("pandas_metrics") or {}).get("columns") or [])]
                    norm_tokens = [h.strip().upper() for h in header_tokens if h]
                    skip_mnemonic = os.getenv("TABLE_TITLE_SKIP_MNEMONIC", "1") in ("1","true","yes")
                    mnemonic_ratio = float(os.getenv("TABLE_TITLE_MNEMONIC_RATIO", "0.8"))
                    short_tokens = [tok for tok in norm_tokens if len(tok) <= 4]
                    is_mnemonic = (
                        (len(short_tokens) == len(norm_tokens) and len(norm_tokens) <= 8)
                        or (len(short_tokens)/max(1,len(norm_tokens)) >= mnemonic_ratio)
                    ) if norm_tokens else False
                    if skip_mnemonic and is_mnemonic:
                        tmap[key] = None
                        continue
                    # If Stage 03 cue appears in header, skip inference (treat as externally labeled)
                    if cues and _table_has_label_cue(t, cues):
                        tmap[key] = (t.get("title") or "").strip()
                    else:
                        tmap[key] = (t.get("title") or "").strip()
            titles[sid] = tmap
    else:
        prompts = []
        index: List[tuple[str, str]] = []
        for s in sections:
            sid = s.get("id")
            for t in s.get("tables", []):
                if not _weak_title(t.get("title")):
                    continue
                if cues and _table_has_label_cue(t, cues):
                    continue
                key = t.get("raw_table_id") or t.get("normalized_label") or f"tid_{id(t)}"
                cols = (t.get("pandas_metrics") or {}).get("columns") or []
                rows = (t.get("pandas_df") or [])[:2]
                density = float((t.get("pandas_metrics") or {}).get("data_density", 0) or 0)
                min_density = float(os.getenv("TABLE_INFER_MIN_DENSITY", "0.35"))
                header_tokens = [str(c) for c in ((t.get("pandas_metrics") or {}).get("columns") or [])]
                norm_tokens = [h.strip().upper() for h in header_tokens if h]
                avg_len = sum(len(x) for x in header_tokens) / max(1, len(header_tokens))
                skip_mnemonic = os.getenv("TABLE_TITLE_SKIP_MNEMONIC", "1") in ("1","true","yes")
                mnemonic_ratio = float(os.getenv("TABLE_TITLE_MNEMONIC_RATIO", "0.8"))
                short_tokens = [tok for tok in norm_tokens if len(tok) <= 4]
                is_mnemonic = (
                    (len(short_tokens) == len(norm_tokens) and len(norm_tokens) <= 8)
                    or (len(short_tokens)/max(1,len(norm_tokens)) >= mnemonic_ratio)
                ) if norm_tokens else False
                if density < min_density or avg_len < 3 or (skip_mnemonic and is_mnemonic):
                    continue
                msg = (
                    "Infer a concise (<=12 words) factual title ONLY if obvious from columns/rows; do not invent domains or units.\n"
                    f"Columns: {cols}\nSample rows: {rows}"
                )
                prompts.append({
                    "model": os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL") or "openai/zai-org/GLM-4.5-Air",
                    "messages": [
                        {"role": "system", "content": [{"type": "text", "text": "Output ONLY a short title; if uncertain output an empty string. Never hallucinate measurements or domains."}]},
                        {"role": "user", "content": [{"type": "text", "text": msg}]},
                    ],
                    "kwargs": {"temperature": 0, "top_p": 1, "timeout": 30}
                })
                index.append((sid, key))

        if prompts:
            conc = min(2, int(os.getenv("STAGE07_CONCURRENCY", "2")))
            global_cap = os.getenv("STAGE07_GLOBAL_CONCURRENCY")
            if global_cap and global_cap.isdigit():
                conc = min(conc, int(global_cap))
            req_timeout = float(os.getenv("STAGE07_REQUEST_TIMEOUT", "120"))
            num_retries = int(os.getenv("STAGE07_NUM_RETRIES", "2"))
            out = __import__("asyncio").run(litellm_call(
                prompts,
                wrap_json=False,
                concurrency=conc,
                desc="07c_table_title",
                request_timeout=req_timeout,
                num_retries=num_retries,
            ))
        else:
            out = []
        for i, (sid, key) in enumerate(index):
            content = out[i].content if i < len(out) and out[i] else ""
            cand = (content or "").strip()
            if not cand:
                raise SystemExit(f"07c: LLM returned empty title for {sid}:{key}; aborting per failure policy")
            titles.setdefault(sid, {})[key] = cand

    outp = out_dir / "07c_table_title_infer.json"
    deterministic = DISABLE_LLM or not bool(titles)
    outp.write_text(json.dumps({"table_titles": titles, "deterministic": deterministic}, indent=2, ensure_ascii=False))
    logger.success(f"07c: wrote {outp}")


if __name__ == "__main__":
    app()

def _stage03_label_texts(path: Optional[Path]) -> set[str]:
    out = set()
    try:
        if path and path.exists():
            raw = json.loads(path.read_text())
            for b in raw.get("blocks", []):
                t = (b.get("text") or "").strip().lower()
                if t.startswith("table ") or t.startswith("figure "):
                    out.add(t)
    except Exception:
        pass
    return out


def _table_has_label_cue(t: dict, cues: set[str]) -> bool:
    header = (t.get("pandas_metrics") or {}).get("columns") or []
    if not header:
        return False
    line = " ".join(str(c) for c in header).lower()
    return any(c in line for c in cues if len(c) > 4)
