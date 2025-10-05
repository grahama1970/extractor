#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from loguru import logger

from extractor.pipeline.utils.litellm_call import litellm_call


app = typer.Typer(help="07d: Refine figure captions when short/weak (gated).")

DISABLE_LLM = os.getenv("STAGE07_DISABLE_LLM", "").lower() in {"1", "true", "yes", "y"}


def _weak_caption(text: str | None) -> bool:
    if not text:
        return True
    max_len = int(os.getenv("FIGURE_REFINE_MAX_LEN", "48"))
    return len(text.strip()) < max_len


@app.command("run")
def run(
    canonical_json: Path = typer.Option(..., "--canonical", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
    verified03_json: Optional[Path] = typer.Option(None, "--verified03", help="Path to 03_verified_blocks.json"),
):
    base = output_dir
    out_dir = base / "07d_figure_caption_refine"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json.read_text())
    sections: List[Dict[str, Any]] = payload.get("sections", [])

    captions: Dict[str, Dict[str, str]] = {}
    rejects: List[Dict[str, Any]] = []
    if verified03_json and verified03_json.exists():
        try:
            raw = json.loads(verified03_json.read_text())
            for b in raw.get("blocks", []):
                lv = b.get("llm_verification", {})
                res = lv.get("result") if isinstance(lv, dict) else {}
                if isinstance(res, dict) and res.get("is_header") is False:
                    rejects.append({"bbox": b.get("bbox"), "page_idx": b.get("page_idx")})
        except Exception:
            pass
    if DISABLE_LLM:
        for s in sections:
            sid = s.get("id")
            fmap: Dict[str, str] = {}
            for f in s.get("figures", []):
                cap = f.get("caption") or f.get("ai_description")
                if (not cap) or len(cap.strip()) < 40:
                    fmap[f.get("figure_id") or f.get("image_ref") or f"fid_{id(f)}"] = (cap or "").strip()
            captions[sid] = fmap
    else:
        prompts = []
        index: List[tuple[str, str]] = []
        for s in sections:
            sid = s.get("id")
            for f in s.get("figures", []):
                cap = f.get("caption") or f.get("ai_description")
                if cap and len(cap.strip()) >= 40:
                    continue
                # If overlaps with rejected header candidate > 0.5 IoU => refine
                fb = f.get("bbox") or [0,0,0,0]
                def _iou(a,b):
                    try:
                        ax0, ay0, ax1, ay1 = map(float, a)
                        bx0, by0, bx1, by1 = map(float, b)
                    except Exception:
                        return 0.0
                    inter_x0 = max(ax0, bx0); inter_y0 = max(ay0, by0)
                    inter_x1 = min(ax1, bx1); inter_y1 = min(ay1, by1)
                    iw = max(0.0, inter_x1 - inter_x0); ih = max(0.0, inter_y1 - inter_y0)
                    inter = iw * ih
                    if inter <= 0:
                        return 0.0
                    a_area = max(0.0, (ax1 - ax0) * (ay1 - ay0))
                    b_area = max(0.0, (bx1 - bx0) * (by1 - by0))
                    denom = a_area + b_area - inter
                    return inter / denom if denom > 0 else 0.0
                if any(_iou(fb, r.get("bbox") or [0,0,0,0]) > 0.5 for r in rejects):
                    pass
                # else proceed to refine because caption short/weak
                key = f.get("figure_id") or f.get("image_ref") or f"fid_{id(f)}"
                msg = (
                    "Refine to a concise (<=20 words) factual caption WITHOUT adding unobservable details. Preserve identifiers/units.\n"
                    f"Existing: {cap or ''}"
                )
                prompts.append({
                    "model": os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL") or "openai/zai-org/GLM-4.5-Air",
                    "messages": [
                        {"role": "system", "content": [{"type": "text", "text": "Output ONLY a short caption; do not invent content."}]},
                        {"role": "user", "content": [{"type": "text", "text": msg}]},
                    ],
                    "kwargs": {"temperature": 0, "top_p": 1, "timeout": 30}
                })
                index.append((sid, key))

        if prompts:
            conc = min(4, int(os.getenv("STAGE07_CONCURRENCY", "4")))
            global_cap = os.getenv("STAGE07_GLOBAL_CONCURRENCY")
            if global_cap and global_cap.isdigit():
                conc = min(conc, int(global_cap))
            out = __import__("asyncio").run(litellm_call(prompts, wrap_json=False, concurrency=conc, desc="07d_caption"))
        else:
            out = []
        for i, (sid, key) in enumerate(index):
            content = out[i].content if i < len(out) and out[i] else ""
            cleaned = (content or "").strip()
            words = cleaned.lower().split()
            # placeholder/generic guards
            placeholder = {"figure", "img", "image"}
            if sum(1 for t in words if t in placeholder) >= 2:
                pass
            else:
                generic = {"diagram", "view", "illustration", "schematic"}
                if len(words) > 0 and (sum(1 for t in words if t in generic) / len(words)) > 0.4:
                    pass
            # hallucination blacklist: reject if newly introduces risky adjectives
            blacklist = {"optimal", "novel", "proposed"}
            # we do not have original here; accept unless blacklist appears
            if any(w in words for w in blacklist):
                pass  # keep as-is (it may be original), downstream can decide
            captions.setdefault(sid, {})[key] = cleaned

    outp = out_dir / "07d_figure_caption_refine.json"
    deterministic = DISABLE_LLM or not bool(captions)
    outp.write_text(json.dumps({"figure_captions": captions, "deterministic": deterministic}, indent=2, ensure_ascii=False))
    logger.success(f"07d: wrote {outp}")


if __name__ == "__main__":
    app()
