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
    verified03_json: Optional[Path] = typer.Option(None, "--verified03", help="Path to 03_verified_blocks.json"),
):
    base = output_dir
    out_dir = base / "07b_paragraph_polish"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json.read_text())
    sections: List[Dict[str, Any]] = payload.get("sections", [])

    results: Dict[str, Dict[str, str]] = {}
    headers = _load_stage03_headers(verified03_json) if verified03_json else []
    if DISABLE_LLM:
        for s in sections:
            sid = s.get("id")
            m: Dict[str, str] = {}
            for p in s.get("paragraphs", []):
                txt = p.get("text", "")
                if _suppress_due_to_header(p, headers):
                    m[p.get("pid")] = txt
                elif _noise_score(txt) >= PARA_NOISE_THRESHOLD:
                    m[p.get("pid")] = txt  # identity polish under offline
            results[sid] = m
    else:
        prompts = []
        index: List[tuple[str, str]] = []  # (sid, pid)
        orig_len: Dict[tuple[str, str], int] = {}
        for s in sections:
            sid = s.get("id")
            for p in s.get("paragraphs", []):
                txt = p.get("text", "")
                if _suppress_due_to_header(p, headers):
                    continue
                if _noise_score(txt) < PARA_NOISE_THRESHOLD:
                    continue
                pid = p.get("pid")
                index.append((sid, pid))
                orig_len[(sid, pid)] = len(txt)
                prompts.append({
                    "model": os.getenv("STAGE07B_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL") or "openai/zai-org/GLM-4.5-Air",
                    "messages": [
                        {"role": "system", "content": [{"type": "text", "text": "Normalize formatting ONLY (hyphen splits, spacing, trivial casing). Do NOT invent, paraphrase, merge, reorder, or drop technical tokens. If no fix needed, output original unchanged. Output ONLY JSON: {\\\"text\\\": string}."}]},
                        {"role": "user", "content": [{"type": "text", "text": f"Input paragraph (fix spacing/hyphenation only; preserve wording):\n\n{txt}"}]},
                    ],
                    "kwargs": {"temperature": 0, "top_p": 1, "timeout": 30}
                })
        if prompts:
            # budget gate estimate before firing LLM
            check_and_update_budget("07b", num_items=len(prompts))
            conc = min(2, int(os.getenv("STAGE07_CONCURRENCY", "2")))
            global_cap = os.getenv("STAGE07_GLOBAL_CONCURRENCY")
            if global_cap and global_cap.isdigit():
                conc = min(conc, int(global_cap))
            # Per-stage override then global
            req_timeout = float(os.getenv("STAGE07B_TIMEOUT", os.getenv("STAGE07_REQUEST_TIMEOUT", "120")))
            num_retries = int(os.getenv("STAGE07B_RETRIES", os.getenv("STAGE07_NUM_RETRIES", "2")))
            out = __import__("asyncio").run(litellm_call(
                prompts,
                wrap_json=False,
                concurrency=conc,
                desc="07b_polish",
                request_timeout=req_timeout,
                num_retries=num_retries,
            ))
        else:
            out = []
        results = {}
        max_new_ratio = float(os.getenv("PARA_NEW_TOKEN_RATIO_MAX", "0.15"))
        max_shrink_ratio = float(os.getenv("PARA_TOKEN_SHRINK_RATIO_MAX", "0.40"))
        # Simple acceptance validator
        PLACEHOLDER_BAD = {"placeholder", "lorem", "dummy", "sample", "example"}
        STOPWORDS = {"the", "a", "an", "of", "and", "or", "to", "in"}
        def _valid_polish(original: str, candidate: str, min_tokens: int) -> bool:
            if not candidate or not candidate.strip():
                return False
            toks = [t for t in candidate.split() if t.lower() not in STOPWORDS]
            if len(toks) < min_tokens:
                return False
            if candidate.strip().upper() == candidate.strip() and len(candidate.split()) == 1:
                return False
            low = candidate.lower()
            if any(b in low for b in PLACEHOLDER_BAD):
                return False
            if len(candidate) > len(original) * 3:
                return False
            return True

        min_tokens = int(os.getenv("PARA_MIN_TOKENS", "3"))
        for i, (sid, pid) in enumerate(index):
            content = out[i].content if i < len(out) and out[i] else ""
            candidate = (content or "").strip()
            if not candidate:
                raise SystemExit(f"07b: LLM returned empty content for {sid}:{pid}; aborting per failure policy")
            try:
                cap = int(float(os.getenv("PARA_LEN_INFLATION_CAP", "1.5")) * float(orig_len.get((sid, pid), len(candidate)) or 1))
                if len(candidate) > cap:
                    candidate = candidate[:cap]
            except Exception:
                pass
            # token delta guards
            # Find original text from canonical payload (requires lookup)
            orig_text = None
            for s in sections:
                if s.get("id") == sid:
                    for p in s.get("paragraphs", []):
                        if p.get("pid") == pid:
                            orig_text = p.get("text", "")
                            break
                    break
            if orig_text is None:
                orig_text = candidate
            orig_toks = (orig_text or "").split()
            cand_toks = (candidate or "").split()
            cleaned = candidate
            if orig_toks:
                added = max(0, len(cand_toks) - len(orig_toks))
                removed = max(0, len(orig_toks) - len(cand_toks))
                if (added / len(orig_toks)) > max_new_ratio or (removed / len(orig_toks)) > max_shrink_ratio:
                    cleaned = orig_text
                elif not _valid_polish(orig_text, candidate, min_tokens):
                    cleaned = orig_text
            results.setdefault(sid, {})[pid] = cleaned

    outp = out_dir / "07b_paragraph_polish.json"
    deterministic = DISABLE_LLM or not bool(results and any(results.get(s.get("id"), {}) for s in sections))
    model_used = os.getenv("STAGE07B_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_VLM_MODEL")
    outp.write_text(json.dumps({"polish": results, "deterministic": deterministic, "model_used": model_used, "prompt_version": "1.0"}, indent=2, ensure_ascii=False))
    logger.success(f"07b: wrote {outp}")


if __name__ == "__main__":
    app()

# Helpers added for header suppression
def _suppress_due_to_header(paragraph: Dict[str, Any], headers: List[Dict[str, Any]]) -> bool:
    bb = paragraph.get("bbox")
    if not bb:
        return False
    try:
        py_mid = (float(bb[1]) + float(bb[3])) / 2
        page_idx = paragraph.get("page_idx")
    except Exception:
        return False
    mult = float(os.getenv("PARA_SUPPRESS_RADIUS_MULT", "1.0"))
    base_radius = 60.0 * mult
    for h in headers:
        if h.get("page_idx") != page_idx:
            continue
        hb = h.get("bbox") or [0, 0, 0, 0]
        try:
            hy_mid = (float(hb[1]) + float(hb[3])) / 2
        except Exception:
            continue
        if abs(hy_mid - py_mid) <= base_radius:
            return True
    # Header-like heuristic: very short Title Case line
    txt = paragraph.get("text") or ""
    words = txt.split()
    if 0 < len(words) <= 5 and all(w[:1].isupper() for w in words if w):
        return True
    return False


def _load_stage03_headers(path: Optional[Path]) -> List[Dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        out = []
        for b in raw.get("blocks", []):
            lv = b.get("llm_verification", {})
            res = lv.get("result") if isinstance(lv, dict) else {}
            if isinstance(res, dict):
                out.append({
                    "object_id": b.get("object_id"),
                    "bbox": b.get("bbox"),
                    "page_idx": b.get("page_idx"),
                    "is_header": bool(res.get("is_header", True)),
                })
        return out
    except Exception:
        return []
