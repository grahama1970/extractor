Here’s what I recommend for this branch, plus small, deterministic patches.

## Answers to your clarifying questions

* **Qwen-VL prompt nits:** keep your current prohibitions and add three tiny guardrails that reduce off-schema drift with Qwen while staying model-agnostic:

  1. explicitly forbid *unquoted* object keys and require **double-quoted** keys/strings;
  2. require **fixed-length rows** (exactly `len(columns)`), filling missing cells with empty strings, never `null`;
  3. state “**no tool/function calls; no explanations** outside the JSON object.”
     (You already enforce strict keys/blocks; these just reduce the last 1–2% of oddities we see with 235B.) 

* **Attempt-1 / final caps:** keep them. Attempt-1 (images) at **1792** and final trimmed text-only at **1536** are good balances for Qwen-VL-235B; the change below wires the image-path cap explicitly and keeps `temperature=0, top_p=0` for stability. 

* **Top-level strictness:** keep the top-level pruned to `{reflowed_json, ocr_corrections, improvements_made, summary}` and allow selected `additionalProperties` only in nested blocks. The diffs ensure `response_format={"type":"json_object"}` is used for OpenAI-compatible providers (your Qwen path) and keep Gemini on `response_mime_type: application/json`. 

* **Stage 03 variance trims (no retries):** add `kwargs` with `temperature=0`, `top_p=0`, `max_tokens=256`, and `cache: {"no-cache": true}` to both the single-item verifier and the batch `prepared` items. This matches your Stage-03 intent (small, strict JSON) and avoids extra retries. 

---

## Unified diffs (minimal, deterministic)

> Files patched:
> • `src/extractor/pipeline/utils/model_params.py` (JSON mode + cold sampling defaults)
> • `src/extractor/pipeline/utils/vision.py` (fix Gemini preflight variable)
> • `src/extractor/pipeline/steps/03_suspicious_headers.py` (strict kwargs, no-cache)
> • `src/extractor/pipeline/steps/07_reflow_section.py` (image-path max tokens env; strict call knobs)

### 1) `src/extractor/pipeline/utils/model_params.py`

```diff
diff --git a/src/extractor/pipeline/utils/model_params.py b/src/extractor/pipeline/utils/model_params.py
--- a/src/extractor/pipeline/utils/model_params.py
+++ b/src/extractor/pipeline/utils/model_params.py
@@
-from __future__ import annotations
-
-import base64
-from pathlib import Path
-from typing import Any, Dict, List
+from __future__ import annotations
+
+import os
+import base64
+from pathlib import Path
+from typing import Any, Dict, List
@@
 def build_chat_extras(model_name: str) -> Dict[str, Any]:
     """Return extra kwargs for litellm.acompletion calls.
 
     We keep this minimal and standardized. Include response_format only for OpenAI models;
     other providers will ignore unsupported params, but we avoid sending it to be safe.
     """
     name = (model_name or "").lower()
     extras: Dict[str, Any] = {}
-    if name.startswith("openai/"):
-        extras["response_format"] = {"type": "json_object"}
+    # OpenAI-compatible providers (incl. Qwen via OpenAI compat):
+    if name.startswith("openai/"):
+        extras["response_format"] = {"type": "json_object"}  # strict JSON
+        # Cold sampling + no stylistic penalties for determinism
+        extras["temperature"] = 0
+        extras["top_p"] = 0
+        extras["presence_penalty"] = 0
+        extras["frequency_penalty"] = 0
     # Gemini: prefer JSON-only responses using response_mime_type
     if "gemini" in name:
         # Provider-specific GenerationConfig for Google Gemini
         extras["generation_config"] = {
             "response_mime_type": "application/json",
             # Allow generous output length for structured blocks
             "max_output_tokens": 2048,
         }
     # No temperature by default, avoid tiny max tokens
     return extras
```

### 2) `src/extractor/pipeline/utils/vision.py`

```diff
diff --git a/src/extractor/pipeline/utils/vision.py b/src/extractor/pipeline/utils/vision.py
--- a/src/extractor/pipeline/utils/vision.py
+++ b/src/extractor/pipeline/utils/vision.py
@@
 _VISION_CACHE: Dict[str, bool] = {}
 
 def _norm_model(model: Optional[str]) -> str:
     return (model or "").strip().lower()
 
+def _is_gemini_model(model: Optional[str]) -> bool:
+    return "gemini" in _norm_model(model)
+
@@
 async def preflight_vision_support(model: str, timeout_sec: int = 10) -> bool:
@@
-        # Gemini expects input_text/input_image parts; others accept text/image_url
-        content_parts = [
-            (
-                {"type": "input_text", "text": "preflight vision capability"}
-                if is_gemini
-                else {"type": "text", "text": "preflight vision capability"}
-            ),
-            (
-                {"type": "input_image", "image_url": image_part["image_url"]}
-                if is_gemini
-                else image_part
-            ),
-        ]
+        # Gemini expects input_text/input_image parts; others accept text/image_url
+        is_gemini = _is_gemini_model(model)
+        content_parts = [
+            {"type": ("input_text" if is_gemini else "text"), "text": "preflight vision capability"},
+            ({"type": "input_image", "image_url": image_part["image_url"]} if is_gemini else image_part),
+        ]
```

### 3) `src/extractor/pipeline/steps/03_suspicious_headers.py`

```diff
diff --git a/src/extractor/pipeline/steps/03_suspicious_headers.py b/src/extractor/pipeline/steps/03_suspicious_headers.py
--- a/src/extractor/pipeline/steps/03_suspicious_headers.py
+++ b/src/extractor/pipeline/steps/03_suspicious_headers.py
@@
 async def verify_header_with_llm(image_b64: str, context_text: str, model: str, *, item_timeout: int = 90) -> Dict[str, Any]:
@@
-    results = await litellm_call(
-        prompts=[{"model": model, "messages": messages, "kwargs": {"timeout": item_timeout}}],
-        wrap_json=True,
-        concurrency=1,
-        desc="verify header",
-        session_id=sid,
-        export="results",
-    )
+    results = await litellm_call(
+        prompts=[{
+            "model": model,
+            "messages": messages,
+            "kwargs": {
+                "timeout": item_timeout,
+                "temperature": 0,
+                "top_p": 0,
+                "max_tokens": 256,
+                "cache": {"no-cache": True},
+            },
+        }],
+        wrap_json=True,
+        concurrency=1,
+        desc="verify header",
+        session_id=sid,
+        export="results",
+    )
@@
-            prepared.append(
-                {
-                    "model": config.llm_model,
-                    "messages": messages,
-                    "response_format": {"type": "json_object"},
-                }
-            )
+            prepared.append(
+                {
+                    "model": config.llm_model,
+                    "messages": messages,
+                    "response_format": {"type": "json_object"},
+                    "kwargs": {
+                        "temperature": 0,
+                        "top_p": 0,
+                        "max_tokens": 256,
+                        "cache": {"no-cache": True},
+                    },
+                }
+            )
```

### 4) `src/extractor/pipeline/steps/07_reflow_section.py`

```diff
diff --git a/src/extractor/pipeline/steps/07_reflow_section.py b/src/extractor/pipeline/steps/07_reflow_section.py
--- a/src/extractor/pipeline/steps/07_reflow_section.py
+++ b/src/extractor/pipeline/steps/07_reflow_section.py
@@
 STAGE07_MAX_TOKENS = int(os.getenv("STAGE07_MAX_TOKENS", "2048"))
+STAGE07_IMAGE_PROMPT_MAX_TOKENS = int(os.getenv("STAGE07_IMAGE_PROMPT_MAX_TOKENS", "1792"))
@@
-        messages = [
+        messages = [
             {"role": "system", "content": system_prompt},
             {"role": "user", "content": user_content},
         ]
@@
-        # LLM call: Chat Completions via litellm_call
+        # LLM call: Chat Completions via litellm_call (strict JSON + cold sampling)
         sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
@@
-        if _force_minimal:
+        if _force_minimal:
             try:
                 logs_dir = results_base_dir / "07_reflow_section" / "logs"
                 logs_dir.mkdir(parents=True, exist_ok=True)
@@
                 if isinstance(content_min, str) and content_min.strip():
                     content = content_min
                     # Parse immediately and build output for schema mode
                     try:
                         parsed = clean_json_string(content, return_dict=True)
                     except Exception:
                         parsed = {}
@@
                 if isinstance(parsed, (dict, list)):
                     parsed = {"reflowed_text": json.dumps(parsed, ensure_ascii=False)}
                 elif isinstance(parsed, str):
                     parsed = {"reflowed_text": parsed}
                 else:
                     parsed = {"reflowed_text": content}
                 # ...
 
         # === Normal strict call path ===
-        # (existing call below)
+        extras = build_chat_extras(LLM_MODEL)
+        out_max_tokens = STAGE07_IMAGE_PROMPT_MAX_TOKENS if (supports_vision and include_images) else STAGE07_MAX_TOKENS
+        call_params = {
+            "model": LLM_MODEL,
+            "messages": messages,
+            **extras,
+            "timeout": llm_timeout,
+            "temperature": 0,
+            "top_p": 0,
+            "max_tokens": out_max_tokens,
+            "cache": {"no-cache": True},
+        }
+        results = await litellm_call(
+            [call_params],
+            wrap_json=True,
+            concurrency=1,
+            desc="Reflow Section",
+            session_id=sid,
+            export="results",
+        )
+        r = results[0] if results else None
+        content = r.content if r else {}
+        try:
+            parsed = content if isinstance(content, (dict, list)) else clean_json_string(content, return_dict=True)
+        except Exception:
+            parsed = {}
```

---

### Why these patches (in short)

* **JSON enforcement for Qwen-VL**: adds provider-appropriate JSON output knobs and cold sampling (`temperature=0, top_p=0`) through a single, reusable helper (`build_chat_extras`) and threads them into Stage 07/03 calls. That’s the highest-leverage way to cut non-JSON drift without retries.

* **Image preflight bug**: `vision.py` referenced an undefined `is_gemini`; the fix makes Gemini preflight use the correct content parts, reducing false “vision unsupported” negatives. 

* **Image-path cap**: Stage 07 now **honors a separate image-path cap** (`STAGE07_IMAGE_PROMPT_MAX_TOKENS`, default 1792) while keeping the general cap at 2048; this matches your intent and keeps first calls stable. 

If you want, I can also splice in a tiny overlay to draw **Step 07 “knowledge chunk”** spans in your `scripts/tools/pdf_annotate_from_pipeline.py` (orange tags) alongside the existing Stage 07 table overlays; right now it draws reflowed tables but not knowledge-chunk boxes. 

**Referenced files:** Stage 07 core and constants, prompt/contract:  • Stage 03 verifier skeleton:  • Extras helper:  • Vision preflight: 

```diff
diff --git a/src/extractor/pipeline/utils/model_params.py b/src/extractor/pipeline/utils/model_params.py
--- a/src/extractor/pipeline/utils/model_params.py
+++ b/src/extractor/pipeline/utils/model_params.py
@@
 def build_chat_extras(model_name: str) -> Dict[str, Any]:
     """Return extra kwargs for litellm.acompletion calls.
 
     We keep this minimal and standardized. Include response_format only for OpenAI models;
     other providers will ignore unsupported params, but we avoid sending it to be safe.
     """
     name = (model_name or "").lower()
     extras: Dict[str, Any] = {}
-    if name.startswith("openai/"):
-        extras["response_format"] = {"type": "json_object"}
+    if name.startswith("openai/"):
+        # Strict JSON and cold sampling for determinism (Qwen via OpenAI compat path)
+        extras["response_format"] = {"type": "json_object"}
+        extras["temperature"] = 0
+        extras["top_p"] = 0
+        extras["presence_penalty"] = 0
+        extras["frequency_penalty"] = 0
     # Gemini: prefer JSON-only responses using response_mime_type
     if "gemini" in name:
         # Provider-specific GenerationConfig for Google Gemini
         extras["generation_config"] = {
             "response_mime_type": "application/json",
             # Allow generous output length for structured blocks
             "max_output_tokens": 2048,
         }
     # No temperature by default, avoid tiny max tokens
     return extras
```

```diff
diff --git a/src/extractor/pipeline/utils/vision.py b/src/extractor/pipeline/utils/vision.py
--- a/src/extractor/pipeline/utils/vision.py
+++ b/src/extractor/pipeline/utils/vision.py
@@
 _VISION_CACHE: Dict[str, bool] = {}
 
 def _norm_model(model: Optional[str]) -> str:
     return (model or "").strip().lower()
 
+def _is_gemini_model(model: Optional[str]) -> bool:
+    return "gemini" in _norm_model(model)
+
@@
 async def preflight_vision_support(model: str, timeout_sec: int = 10) -> bool:
@@
-        # Gemini expects input_text/input_image parts; others accept text/image_url
-        content_parts = [
-            (
-                {"type": "input_text", "text": "preflight vision capability"}
-                if is_gemini
-                else {"type": "text", "text": "preflight vision capability"}
-            ),
-            (
-                {"type": "input_image", "image_url": image_part["image_url"]}
-                if is_gemini
-                else image_part
-            ),
-        ]
+        # Gemini expects input_text/input_image parts; others accept text/image_url
+        is_gemini = _is_gemini_model(model)
+        content_parts = [
+            {"type": ("input_text" if is_gemini else "text"), "text": "preflight vision capability"},
+            ({"type": "input_image", "image_url": image_part["image_url"]} if is_gemini else image_part),
+        ]
```

```diff
diff --git a/src/extractor/pipeline/steps/03_suspicious_headers.py b/src/extractor/pipeline/steps/03_suspicious_headers.py
--- a/src/extractor/pipeline/steps/03_suspicious_headers.py
+++ b/src/extractor/pipeline/steps/03_suspicious_headers.py
@@
 async def verify_header_with_llm(image_b64: str, context_text: str, model: str, *, item_timeout: int = 90) -> Dict[str, Any]:
@@
-    results = await litellm_call(
-        prompts=[{"model": model, "messages": messages, "kwargs": {"timeout": item_timeout}}],
-        wrap_json=True,
-        concurrency=1,
-        desc="verify header",
-        session_id=sid,
-        export="results",
-    )
+    results = await litellm_call(
+        prompts=[{
+            "model": model,
+            "messages": messages,
+            "kwargs": {
+                "timeout": item_timeout,
+                "temperature": 0,
+                "top_p": 0,
+                "max_tokens": 256,
+                "cache": {"no-cache": True},
+            },
+        }],
+        wrap_json=True,
+        concurrency=1,
+        desc="verify header",
+        session_id=sid,
+        export="results",
+    )
@@
-            prepared.append(
-                {
-                    "model": config.llm_model,
-                    "messages": messages,
-                    "response_format": {"type": "json_object"},
-                }
-            )
+            prepared.append(
+                {
+                    "model": config.llm_model,
+                    "messages": messages,
+                    "response_format": {"type": "json_object"},
+                    "kwargs": {
+                        "temperature": 0,
+                        "top_p": 0,
+                        "max_tokens": 256,
+                        "cache": {"no-cache": True},
+                    },
+                }
+            )
```

```diff
diff --git a/src/extractor/pipeline/steps/07_reflow_section.py b/src/extractor/pipeline/steps/07_reflow_section.py
--- a/src/extractor/pipeline/steps/07_reflow_section.py
+++ b/src/extractor/pipeline/steps/07_reflow_section.py
@@
 import os
@@
 from ..utils.json_utils import clean_json_string
+from ..utils.model_params import build_chat_extras
@@
-STAGE07_MAX_TOKENS = int(os.getenv("STAGE07_MAX_TOKENS", "2048"))
+STAGE07_MAX_TOKENS = int(os.getenv("STAGE07_MAX_TOKENS", "2048"))
+STAGE07_IMAGE_PROMPT_MAX_TOKENS = int(os.getenv("STAGE07_IMAGE_PROMPT_MAX_TOKENS", "1792"))
@@
-        # LLM call: Chat Completions via litellm_call
+        # LLM call: Chat Completions via litellm_call (strict JSON + cold sampling)
         sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
@@
-        # === Normal strict call path ===
-        # (existing call below)
+        # === Normal strict call path ===
+        extras = build_chat_extras(LLM_MODEL)
+        out_max_tokens = STAGE07_IMAGE_PROMPT_MAX_TOKENS if (supports_vision and include_images) else STAGE07_MAX_TOKENS
+        call_params = {
+            "model": LLM_MODEL,
+            "messages": messages,
+            **extras,
+            "timeout": llm_timeout,
+            "temperature": 0,
+            "top_p": 0,
+            "max_tokens": out_max_tokens,
+            "cache": {"no-cache": True},
+        }
+        results = await litellm_call(
+            [call_params],
+            wrap_json=True,
+            concurrency=1,
+            desc="Reflow Section",
+            session_id=sid,
+            export="results",
+        )
+        r = results[0] if results else None
+        content = r.content if r else {}
+        try:
+            parsed = content if isinstance(content, (dict, list)) else clean_json_string(content, return_dict=True)
+        except Exception:
+            parsed = {}
```
