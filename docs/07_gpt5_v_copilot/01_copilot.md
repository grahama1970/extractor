Here are the answers and the minimal, deterministic unified diffs.

Answers to the clarifying questions

- Qwen‑VL prompt nits to add (beyond your current set): explicitly forbid code fences, tool/function calls, XML/YAML/Markdown, comments, and trailing commas; require exactly one JSON object and nothing else; use only JSON literals true/false/null; forbid NaN/Infinity; no explanations.
- Token caps: keep Attempt‑1 at 1792 (via STAGE07_IMAGE_PROMPT_MAX_TOKENS) and the final retry at 1536. These caps are sufficient and aligned with your current shaping; no change needed.
- Top‑level strictness: keep pruning to {reflowed_json, ocr_corrections, improvements_made, summary}. Maintain selected nested additionalProperties where needed.
- Stage 03 variance reduction (no extra retries): add top_p=0 (now set in provider extras), a conservative context trim (STAGE03_VERIFY_TRIM_CHARS default 800), a stop guard for code fences, and set no‑cache on the tiny JSON verification call.

Unified diffs (minimal changes)

```diff
--- a/src/extractor/pipeline/utils/model_params.py
+++ b/src/extractor/pipeline/utils/model_params.py
@@ -2,8 +2,9 @@
 
 import base64
 from pathlib import Path
 from typing import Any, Dict, List
+import os
 
 
 def image_file_to_data_url(path: Path) -> str:
@@
 def build_chat_extras(model_name: str) -> Dict[str, Any]:
     """Return extra kwargs for litellm.acompletion calls.
 
     Standardize provider knobs so JSON mode is honored across OpenAI-compatible gateways.
     - Set custom_llm_provider to "openai" by default so response_format works when routed.
     - For non-Gemini, request JSON object responses.
-    - For Gemini, prefer response_mime_type JSON.
+    - For Gemini, prefer response_mime_type JSON.
+    - Deterministic knobs for non‑Gemini: top_p=0, presence/frequency penalties=0.
+    - Optional seed via env LITELLM_SEED or STAGE_SEED (ignored if unsupported).
     """
     name = (model_name or "").lower()
     extras: Dict[str, Any] = {}
     # Default to OpenAI-compatible to avoid provider ambiguity and enable response_format
     extras["custom_llm_provider"] = "openai"
     if "gemini" not in name:
-        extras["response_format"] = {"type": "json_object"}
+        extras["response_format"] = {"type": "json_object"}
+        extras["top_p"] = 0
+        extras["presence_penalty"] = 0
+        extras["frequency_penalty"] = 0
     else:
         # Provider-specific GenerationConfig for Google Gemini
         extras["generation_config"] = {
             "response_mime_type": "application/json",
             # Allow generous output length for structured blocks
             "max_output_tokens": 2048,
         }
-    return extras
+    try:
+        seed = os.getenv("LITELLM_SEED") or os.getenv("STAGE_SEED")
+        if seed is not None:
+            extras["seed"] = int(seed)
+    except Exception:
+        pass
+    return extras
```

```diff
--- a/src/extractor/pipeline/utils/json_utils.py
+++ b/src/extractor/pipeline/utils/json_utils.py
@@
 def json_serialize(data, handle_paths=False, **kwargs):
@@
     if handle_paths:
         return json.dumps(data, cls=PathEncoder, **kwargs)
     return json.dumps(data, **kwargs)
 
+def _forbid_constants(x: str):
+    # Disallow NaN, Infinity, -Infinity in strict JSON loads
+    raise ValueError(f"Non-JSON constant: {x}")
+
+
+def strict_json_loads(s: str):
+    # Strict JSON parse: no NaN/Infinity and no trailing junk
+    return json.loads(s, parse_constant=_forbid_constants)
+
+
+def parse_json_strict(content: str, logger=None):
+    """
+    Strict JSON parser for LLM outputs:
+    - Extract first {...} or [...] region if present
+    - Forbid NaN/Infinity
+    - No repair fallback (fail fast)
+    """
+    _log = logger if logger is not None else globals().get("logger")
+    try:
+        m = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
+        if m:
+            content = m.group(1)
+        parsed = strict_json_loads(content)
+        if _log:
+            _log.debug("Strict JSON parsed successfully")
+        return parsed
+    except Exception as e:
+        if _log:
+            _log.error(f"Strict JSON parse failed: {e}")
+        raise
+
@@
 def parse_json(content: str, logger=None) -> Union[dict, list, str]:
```

```diff
--- a/src/extractor/pipeline/steps/07_reflow_section.py
+++ b/src/extractor/pipeline/steps/07_reflow_section.py
@@
-from extractor.pipeline.utils.json_utils import clean_json_string, restrict_top_level_keys
+from extractor.pipeline.utils.json_utils import clean_json_string, restrict_top_level_keys, parse_json_strict
@@
 STAGE07_MAX_TOKENS = int(os.getenv("STAGE07_MAX_TOKENS", "2048"))
+STAGE07_IMAGE_PROMPT_MAX_TOKENS = int(os.getenv("STAGE07_IMAGE_PROMPT_MAX_TOKENS", "1792"))
@@
             if _compact:
-                system_text = (
-                    "You output ONLY valid JSON. No prose, no markdown, no code fences."
-                    f"\n{PROMPT_STRICT_REQUIREMENTS}"
-                )
+                system_text = (
+                    "You output ONLY valid JSON. Exactly one JSON object. No prose, no markdown, no code fences, no comments, no explanations, no trailing commas. No NaN/Infinity."
+                    f"\n{PROMPT_STRICT_REQUIREMENTS}"
+                )
             else:
-                system_text = (
-                    "You are a strict JSON generator. You respond with exactly one JSON object conforming to the schema."
-                    " Do not include any explanations, prose, code fences, or extra keys."
-                    f"\n{PROMPT_STRICT_REQUIREMENTS}"
-                )
+                system_text = (
+                    "You are a strict JSON generator. Return exactly one JSON object and nothing else."
+                    " No markdown, no code fences, no comments, no explanations, no extra keys, no trailing commas."
+                    " Use only JSON literals true/false/null. Do not emit NaN or Infinity."
+                    f"\n{PROMPT_STRICT_REQUIREMENTS}"
+                )
@@
             call_params = {
                 "model": LLM_MODEL,
                 "messages": messages,
                 **extras,
                 "timeout": llm_timeout,
             }
             # Reduce variability
             call_params["temperature"] = 0
+            # Prevent accidental markdown/code fences in output
+            call_params["stop"] = ["```"]
             # Important: Do NOT set max_output_tokens for Gemini (can cause empty responses)
             try:
-                if "gemini" not in (LLM_MODEL or "").lower():
-                    call_params["max_tokens"] = STAGE07_MAX_TOKENS
+                if "gemini" not in (LLM_MODEL or "").lower():
+                    token_cap = min(STAGE07_MAX_TOKENS, STAGE07_IMAGE_PROMPT_MAX_TOKENS)
+                    call_params["max_tokens"] = token_cap
             except Exception:
                 pass
             # Disable cache for strict JSON passes to avoid stale empties
             call_params["cache"] = {"no-cache": True}
@@
                 call_params2 = {"model": LLM_MODEL, "messages": messages2, "timeout": llm_timeout, **extras}
-                call_params2["temperature"] = 0
+                call_params2["temperature"] = 0
+                call_params2["stop"] = ["```"]
                 # Important: Do NOT set max_output_tokens for Gemini (can cause empty responses)
                 try:
                     if "gemini" not in (LLM_MODEL or "").lower():
                         call_params2["max_tokens"] = STAGE07_MAX_TOKENS
                 except Exception:
                     pass
                 call_params2["cache"] = {"no-cache": True}
@@
-        try:
-            parsed = clean_json_string(content, return_dict=True)
+        try:
+            parsed = parse_json_strict(content)
             # Optional: prune unexpected top-level keys for strictness (default ON)
             try:
                 if os.getenv("STAGE07_PRUNE_TOPLEVEL_KEYS", "1").lower() in ("1", "true", "yes", "y"):
                     _allowed = {"reflowed_json", "ocr_corrections", "improvements_made", "summary"}
                     parsed = restrict_top_level_keys(parsed, _allowed)
             except Exception:
                 pass
```

```diff
--- a/src/extractor/pipeline/steps/03_suspicious_headers.py
+++ b/src/extractor/pipeline/steps/03_suspicious_headers.py
@@
 async def verify_header_with_llm(image_b64: str, context_text: str, model: str, *, item_timeout: int = 90) -> Dict[str, Any]:
     """Verify header using litellm_call (vision required) with strict JSON intent.
 
     Always sends an image; provider error will be raised to the caller.
     """
-    user_content: Any = [
-        {"type": "text", "text": context_text},
+    # Conservative trim for context to reduce variance
+    try:
+        _trim = int(os.getenv("STAGE03_VERIFY_TRIM_CHARS", "800"))
+    except Exception:
+        _trim = 800
+    ctx = (context_text or "")[:_trim]
+    user_content: Any = [
+        {"type": "text", "text": ctx},
         {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
     ]
@@
     results = await litellm_call(
-        prompts=[{"model": model_norm, "messages": messages, "kwargs": {**extras, "timeout": item_timeout, "max_tokens": _verify_cap}}],
+        prompts=[{"model": model_norm, "messages": messages, "kwargs": {**extras, "timeout": item_timeout, "max_tokens": _verify_cap, "cache": {"no-cache": True}, "stop": ["```"]}}],
         wrap_json=True,
         concurrency=1,
         desc="verify header",
         session_id=sid,
         export="results",
     )
```