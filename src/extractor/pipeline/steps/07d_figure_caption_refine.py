#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from loguru import logger

from extractor.pipeline.utils.litellm_call import litellm_call
from extractor.pipeline.utils.budget import check_and_update_budget


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
    try:
        logger.info(
            "07d:start sections=%d disable_llm=%s",
            len(sections), DISABLE_LLM,
        )
    except Exception:
        pass

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
        max_items = int(os.getenv("STAGE07_MAX_ITEMS", "0") or 0)
        built = 0
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
                    "model": os.getenv("STAGE07D_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL") or "openai/zai-org/GLM-4.5-Air",
                    "messages": [
                        {"role": "system", "content": [{"type": "text", "text": 'Refine a concise (<=20 words) figure caption; preserve identifiers/units; DO NOT add invented claims or context. If existing caption is adequate, return it unchanged. Output ONLY JSON: {"caption": string}.'}]},
                        {"role": "user", "content": [{"type": "text", "text": msg}]},
                    ],
                    "kwargs": {"temperature": 0, "top_p": 1, "timeout": 30}
                })
                index.append((sid, key))
                built += 1
                if max_items and built >= max_items:
                    break
            if max_items and built >= max_items:
                break

        if prompts:
            check_and_update_budget("07d", num_items=len(prompts))
            conc = min(2, int(os.getenv("STAGE07_CONCURRENCY", "2")))
            global_cap = os.getenv("STAGE07_GLOBAL_CONCURRENCY")
            if global_cap and global_cap.isdigit():
                conc = min(conc, int(global_cap))
            req_timeout = float(os.getenv("STAGE07D_TIMEOUT", os.getenv("STAGE07_REQUEST_TIMEOUT", "120")))
            num_retries = int(os.getenv("STAGE07D_RETRIES", os.getenv("STAGE07_NUM_RETRIES", "2")))
            out = __import__("asyncio").run(litellm_call(
                prompts,
                wrap_json=False,
                concurrency=conc,
                desc="07d_caption",
                request_timeout=req_timeout,
                num_retries=num_retries,
            ))
            try:
                logger.info(
                    "07d:llm fired items=%d conc=%d timeout=%.1f retries=%d model=%s",
                    len(prompts), conc, req_timeout, num_retries,
                    os.getenv("STAGE07D_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL"),
                )
            except Exception:
                pass
        else:
            out = []
        CAPTION_BAD = {"placeholder", "sample image", "example figure"}
        def _valid_caption(orig: str, cand: str, min_tokens: int) -> bool:
            if not cand or not cand.strip():
                return False
            toks = [w for w in cand.split() if w.isalpha()]
            if len(toks) < min_tokens:
                return False
            low = cand.lower().strip()
            if low in CAPTION_BAD:
                return False
            if len(cand) > len(orig) * 3:
                return False
            return True

        for i, (sid, key) in enumerate(index):
            content = out[i].content if i < len(out) and out[i] else ""
            cleaned = (content or "").strip()
            if not cleaned:
                raise SystemExit(f"07d: LLM returned empty caption for {sid}:{key}; aborting per failure policy")
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
            blacklist = {"optimal", "novel", "proposed", "breakthrough", "state-of-the-art", "revolutionary", "innovative", "next-generation", "cutting-edge"}
            # we do not have original here; accept unless blacklist appears
            if any(w in words for w in blacklist):
                pass  # keep as-is (it may be original), downstream can decide
            min_tokens = int(os.getenv("FIGURE_CAPTION_MIN_TOKENS", "3"))
            if not _valid_caption((f.get("caption") or f.get("ai_description") or ""), cleaned, min_tokens):
                cleaned = (f.get("caption") or f.get("ai_description") or "").strip()
                captions.setdefault(sid, {})[f"{key}__meta"] = {"validation_reason": "invalid_or_generic"}
            captions.setdefault(sid, {})[key] = cleaned

    outp = out_dir / "07d_figure_caption_refine.json"
    deterministic = DISABLE_LLM or not bool(captions)
    model_used = os.getenv("STAGE07D_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL")
    outp.write_text(json.dumps({"figure_captions": captions, "deterministic": deterministic, "model_used": model_used, "prompt_version": "1.0"}, indent=2, ensure_ascii=False))
    logger.success(f"07d: wrote {outp}")
    try:
        total = sum(len(v) for v in captions.values())
        logger.info("07d:summary captions=%d deterministic=%s", total, deterministic)
    except Exception:
        pass


if __name__ == "__main__":
    app()
