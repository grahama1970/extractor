#!/usr/bin/env python3
"""
Build a LiteLLM Router model_list from live Chutes catalog with accurate parameter size:

- Trailing-slash fix to avoid redirect/auth drop
- Criteria filtering (optional; keep permissive by default)
- Rich `meta` per entry:
    - params.total (e.g., 671B) + params.activated (e.g., 37B)
    - params.effective -> activated if present else total
    - prices (ppm + per-token), context, modalities, capabilities
- Prefer PARAM SIZES FROM TAGLINE; careful fallback to README
- Optionally prepend 'openai/' to model id when sending to endpoint
- Demo prints the meta for the **actual model used** in the response
"""

import os
import re
import json
import asyncio
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv, find_dotenv
from litellm import Router

# ---------------- Config / env ----------------

load_dotenv(find_dotenv())

CHUTES_API_KEY = os.getenv("CHUTES_API_KEY")
CATALOG_URL = "https://api.chutes.ai/chutes/"        # trailing slash avoids redirect/token-drop
LLM_API_BASE = os.getenv("CHUTES_API_BASE") or "https://llm.chutes.ai/v1"
REQUEST_TIMEOUT = 20

# Per your note: treat these as OpenAI compatible -> prefix with 'openai/'

# ---------------- Small utils ----------------

_UNITS = {"M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}

def _safe_get(d: Dict[str, Any], path: List[str], default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return default if cur is None else cur

def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def _param_value(num: str, unit: str) -> Optional[int]:
    try:
        return int(float(num) * _UNITS[unit.upper()])
    except Exception:
        return None

def _strip_openai_prefix(model: str) -> str:
    return re.sub(r"^openai/", "", model, flags=re.IGNORECASE)

# ------------- Parameter size parsing -------------

_ACTIVATED_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([MBT])\s*(?:activated)", re.IGNORECASE)
_TOTAL_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([MBT])\s*(?:param|params|parameter|parameters)\b", re.IGNORECASE)

def _parse_params_from_tagline(tagline: str) -> Dict[str, Any]:
    """
    Prefer tagline, e.g.:
      "DeepSeek-R1 is a 671B parameter (37B activated) ..."
    Returns dict with total/activated/effective if found.
    """
    if not tagline:
        return {}
    out: Dict[str, Any] = {}

    act = _ACTIVATED_RE.search(tagline)
    if act:
        n, u = act.groups()
        out["activated"] = {"str": f"{n}{u.upper()}", "value": _param_value(n, u)}

    tot = _TOTAL_PARAM_RE.search(tagline)
    if tot:
        n, u = tot.groups()
        out["total"] = {"str": f"{n}{u.upper()}", "value": _param_value(n, u)}

    if out:
        out["effective"] = out.get("activated") or out.get("total")
        out["source"] = "tagline"
    return out

def _parse_params_from_readme(readme: str) -> Dict[str, Any]:
    """
    Careful fallback: look near 'parameter(s)' or 'activated' terms,
    not a greedy 'find all B/M/T' across the whole doc.
    """
    if not readme:
        return {}
    # Limit scan to early section to avoid cross-model noise
    head = readme[:4000]

    # Activated first
    act = _ACTIVATED_RE.search(head)
    tot = _TOTAL_PARAM_RE.search(head)

    out: Dict[str, Any] = {}
    if act:
        n, u = act.groups()
        out["activated"] = {"str": f"{n}{u.upper()}", "value": _param_value(n, u)}
    if tot:
        n, u = tot.groups()
        out["total"] = {"str": f"{n}{u.upper()}", "value": _param_value(n, u)}

    if out:
        out["effective"] = out.get("activated") or out.get("total")
        out["source"] = "readme"
    return out

def _param_block_for_model(m: Dict[str, Any]) -> Dict[str, Any]:
    # 1) Tagline (per-model, reliable)
    block = _parse_params_from_tagline(m.get("tagline") or "")
    if block:
        return block
    # 2) README (fallback, cautious)
    return _parse_params_from_readme(m.get("readme") or "")

# ---------------- Catalog fetch ----------------

def get_active_chutes(api_key: str, include_public: bool = True, limit: int = 10000) -> List[Dict[str, Any]]:
    if not api_key:
        raise RuntimeError("CHUTES_API_KEY missing")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    params = {
        "include_public": "true" if include_public else "false",
        "include_schemas": "false",
        "limit": str(limit),
    }
    with requests.Session() as s:
        s.headers.update(headers)
        r = s.get(CATALOG_URL, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    return payload.get("items", [])

# ---------------- Filtering (optional) ----------------

@dataclass
class Criteria:
    max_input_ppm: Optional[float] = None
    max_output_ppm: Optional[float] = None
    min_context_tokens: Optional[int] = None
    provider_allowlist: List[str] = field(default_factory=list)
    provider_blocklist: List[str] = field(default_factory=list)
    name_allow_regex: Optional[str] = None
    name_block_regex: Optional[str] = None
    require_modalities: List[str] = field(default_factory=list)
    require_capability_keys: List[str] = field(default_factory=list)

def filter_chutes(chutes: List[Dict[str, Any]], c: Criteria) -> List[Dict[str, Any]]:
    out = []
    for m in chutes:
        name = m.get("name", "")
        provider = name.split("/", 1)[0] if "/" in name else ""

        if c.provider_allowlist and provider not in c.provider_allowlist:
            continue
        if c.provider_blocklist and provider in c.provider_blocklist:
            continue
        if c.name_allow_regex and not re.search(c.name_allow_regex, name, re.IGNORECASE):
            continue
        if c.name_block_regex and re.search(c.name_block_regex, name, re.IGNORECASE):
            continue

        price_in = _safe_get(m, ["current_estimated_price", "per_million_tokens", "input", "usd"])
        price_out = _safe_get(m, ["current_estimated_price", "per_million_tokens", "output", "usd"])
        fin = _to_float(price_in)
        fout = _to_float(price_out)
        if c.max_input_ppm is not None and (fin is None or fin > c.max_input_ppm):
            continue
        if c.max_output_ppm is not None and (fout is None or fout > c.max_output_ppm):
            continue

        context = m.get("max_input_tokens") or m.get("context_length") or _safe_get(m, ["limits", "max_input_tokens"])
        if c.min_context_tokens is not None and (context is None or int(context) < c.min_context_tokens):
            continue

        modalities = set(m.get("modalities") or [])
        if c.require_modalities and not set(c.require_modalities).issubset(modalities):
            continue

        if c.require_capability_keys:
            caps = m.get("capabilities") or {}
            if not all(k in caps for k in c.require_capability_keys):
                continue

        out.append(m)
    return out

# ------------- Router build (+ rich meta) -------------

def make_model_list_with_meta(chutes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Convert chutes → Router entries with a `meta` block.
    Returns (model_list, index_by_catalog_id)
    """
    model_list = []
    index_by_catalog_id: Dict[str, Dict[str, Any]] = {}

    for m in chutes:
        name = m.get("name")
        if not name:
            continue

        provider = name.split("/", 1)[0] if "/" in name else "unknown"
        alias = _slug(name)

        # Pricing
        in_ppm  = _safe_get(m, ["current_estimated_price", "per_million_tokens", "input", "usd"])
        out_ppm = _safe_get(m, ["current_estimated_price", "per_million_tokens", "output", "usd"])
        in_tok  = float(in_ppm)  / 1_000_000 if _to_float(in_ppm)  is not None else None
        out_tok = float(out_ppm) / 1_000_000 if _to_float(out_ppm) is not None else None

        # Context
        ctx = m.get("max_input_tokens") or m.get("context_length") or _safe_get(m, ["limits", "max_input_tokens"])

        # Param sizes (prefer tagline; fallback readme)
        params_block = _param_block_for_model(m)

        # Other hints
        modalities = m.get("modalities") or []
        capabilities = m.get("capabilities") or {}

        # Model id to send (force OpenAI-compatible prefix)
        send_model = f"openai/{name}"

        meta = {
            "catalog_id": name,
            "provider": provider,
            "context_tokens": ctx,
            "params": params_block,   # {'total':..., 'activated':..., 'effective':..., 'source':...}
            "pricing": {
                "usd_per_million": {"input": in_ppm, "output": out_ppm},
                "usd_per_token":   {"input": in_tok, "output": out_tok},
            },
            "modalities": modalities,
            "capabilities": capabilities,
            # convenience numeric for sorting (effective params)
            "effective_params_value": _safe_get(params_block, ["effective", "value"]),
        }

        entry = {
            "model_name": alias,
            "litellm_params": {
                "model": send_model,
                "api_key": CHUTES_API_KEY,
                "api_base": LLM_API_BASE,
                "custom_llm_provider": "openai",
            },
            "meta": meta,
        }
        model_list.append(entry)
        index_by_catalog_id[name] = entry

    return model_list, index_by_catalog_id

# ---- Optional: register costs with LiteLLM's internal cost map ----

def register_costs_with_litellm(model_list: List[Dict[str, Any]]):
    try:
        from litellm import add_model_to_model_cost_map
    except Exception:
        add_model_to_model_cost_map = None

    if not add_model_to_model_cost_map:
        return

    for e in model_list:
        model_id = e["litellm_params"]["model"]
        meta = e.get("meta", {})
        usd_in  = _safe_get(meta, ["pricing", "usd_per_token", "input"])
        usd_out = _safe_get(meta, ["pricing", "usd_per_token", "output"])
        if usd_in is None and usd_out is None:
            continue
        try:
            add_model_to_model_cost_map(
                model=model_id,
                input_cost_per_token=usd_in,
                output_cost_per_token=usd_out,
            )
        except Exception:
            pass  # non-fatal

# ---------------- Demo: call exact model & report ----------------

async def call_and_report(router: Router, alias: str, index_by_catalog_id: Dict[str, Dict[str, Any]]):
    """
    Calls the exact alias (no group fallback), then prints the meta for the
    actual model used as reported by the API response.
    """
    msg = [{"role": "user", "content": "In one short sentence, say hello and your model family."}]
    resp = await router.acompletion(model=alias, messages=msg)

    # The OpenAI-compatible response usually includes the resolved 'model'
    used = resp.get("model") or _safe_get(resp, ["choices", 0, "model"])
    used_clean = _strip_openai_prefix(used or "")
    print(f"\n[Demo] Alias called: {alias}")
    print(f"[Demo] Model reported by API: {used}")

    # Find its meta by matching catalog id
    # (Chutes should return the same catalog id we sent, minus any 'openai/' prefix)
    meta_entry = index_by_catalog_id.get(used_clean)
    if meta_entry:
        print("[Demo] Meta for used model:")
        print(json.dumps(meta_entry["meta"], indent=2))
    else:
        # If the server returns a variant (e.g., snapshot name), show closest hints
        print("[Demo] Could not map response model to catalog exactly. Showing alias meta instead.")
        # Show the alias we used
        for e in router.model_list:
            if e["model_name"] == alias:
                print(json.dumps(e["meta"], indent=2))
                break

# ---------------- Main ----------------

async def main():
    chutes = get_active_chutes(CHUTES_API_KEY, include_public=True, limit=10000)

    # Optional: filtering (kept permissive)
    criteria = Criteria(
        # Example caps (uncomment as needed)
        # max_input_ppm=3.0,
        # max_output_ppm=15.0,
        # min_context_tokens=16000,
        # provider_allowlist=["deepseek-ai", "unsloth", "zai-org", "NousResearch", "tngtech"],
        # name_block_regex=r"(preview|terminus)",
        require_modalities=[],  # e.g., ["text"]
    )
    selected = filter_chutes(chutes, criteria)
    if not selected:
        print("No models passed the filter criteria.")
        return

    model_list, index_by_catalog_id = make_model_list_with_meta(selected)
    # Optional: align LiteLLM's internal cost tracker with Chutes pricing
    # register_costs_with_litellm(model_list)

    router = Router(model_list=model_list)

    # Print concise summary with EFFECTIVE param size (activated preferred)
    print(f"\nSelected {len(selected)} models for Router:\n" + "-" * 60)
    for m in selected:
        name = m["name"]
        alias = _slug(name)
        fin = _safe_get(m, ["current_estimated_price", "per_million_tokens", "input", "usd"])
        fout = _safe_get(m, ["current_estimated_price", "per_million_tokens", "output", "usd"])
        ctx = m.get("max_input_tokens") or m.get("context_length") or _safe_get(m, ["limits", "max_input_tokens"])
        params = _param_block_for_model(m)
        eff = _safe_get(params, ["effective", "str"]) or "?"
        src = _safe_get(params, ["source"]) or "-"
        print(f"{alias:<40} -> {name}")
        print(f"    price_in:{fin} USD/1M, price_out:{fout} USD/1M, ctx:{ctx}, params_effective:{eff} (source:{src})")

    # Pasteable Router model_list (with meta)
    print("\nPasteable Router model_list (with meta):")
    print(json.dumps(model_list, indent=2))

    # Demo: call EXACT alias (no group fallback) and show meta of the model actually used
    if os.getenv("RUN_TEST_COMPLETION") == "1":
        # Choose a specific alias (example: deepseek R1)
        target_alias = next((e["model_name"] for e in model_list if "deepseek-ai-deepseek-r1" in e["model_name"]), model_list[0]["model_name"])
        await call_and_report(router, target_alias, index_by_catalog_id)

if __name__ == "__main__":
    asyncio.run(main())
