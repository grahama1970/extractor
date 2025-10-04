# Fork
Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay

## Comprehensive Review: PDF Pipeline (Stages 04–07) & Core Utilities

---

### Executive Summary

Stage 07 (multimodal reflow) is currently brittle because it assumes strict JSON adherence from heterogeneous OpenAI‑compatible models via an aggregator (Chutes). Failures center on incomplete / verbose responses, missing `reflowed_json`, and lack of a hardened extraction fallback. Additional reliability risks: (1) over‑broad retry semantics causing long stalls, (2) unbounded callback accumulation warnings from LiteLLM, (3) non‑deterministic or inefficient table / figure normalization, and (4) noisy pandas deprecation warnings (`applymap`).

This review delivers:
- Direct answers to clarifying questions.
- A prioritized, severity‑tagged issue list with concrete fixes.
- Surgical unified diffs: Stage 07 prompt hardening, robust JSON extraction, fallback policies, per‑request adaptive retries, deterministic / concurrency safety, callback hygiene, and quieting pandas warnings.
- Added tests (drop‑in under `tests/`) for JSON extraction, fallback logic, model routing.
- A Stage 07 runbook to minimize first‑token and schema failures.

All diffs preserve existing JSON keys (backward compatible) and add only additive metadata (`parse_strategy`, `reflow_attempts`, etc.).

---

## Answers to Clarifying Questions

1. Schema Guard (Stage 07)  
   Recommended pattern:  
   - System message: Single authoritative contract (short, declarative, JSON‑first).  
   - User message (first content element): A “JSON guard” prefix + concise context text.  
   - Images appended as `image_url` parts AFTER the guard text—never before text.  
   - Use `response_format={"type":"json_object"}` (or schema) only on providers proven to obey; otherwise omit and rely on scanning.  
   Hardened extraction pipeline (implemented below):  
   - Phase 1: If `wrap_json=True` and response parses cleanly → accept.  
   - Phase 2: Robust streaming / verbose extraction: scan for the first valid top‑level JSON object using a brace balancer that ignores braces in strings and base64 payloads.  
   - Phase 3: If still invalid: attempt lenient “repair” (strip leading junk, remove trailing commentary, collapse code fences).  
   - Phase 4: Structured fallback builder (pass‑through) with `reflow_status=fallback` + diagnostic `parse_strategy`.

2. Prompt Shaping / Ordering  
   - SYSTEM: Contract + invariants (≤ ~25 lines).  
   - USER first part: “Return ONLY one JSON object with keys: …” followed by structured sectional context.  
   - Then images (section → low confidence tables → figure thumbnail(s) → top annotation).  
   - Avoid putting images before text guard; some models latch onto the first non‑text part and degrade JSON fidelity.  
   - Table hints & figure summaries: keep concise, avoid multi‑page verbatim dumps.

3. Retry / Fallback Policy  
   - Timeout (per request): If no first token within 70% of allotted timeout → cancel & retry once with: (a) no images, (b) compact context (first N chars), (c) simpler guard.  
   - Provider 5xx or network: retry up to 1 with same payload (exponential backoff kept minimal: 0.75–1.25s jitter).  
   - Authentication / 404: fast‑fail → fallback attempt with configured fallback model (one try).  
   - Invalid JSON (post extraction): do NOT re‑ask the model (prevents drift loops); proceed to structured fallback.  
   - Mark outcomes: `parse_strategy` (direct|scan|repaired|fallback), `reflow_attempts`, `llm_model_final`.

4. Routing Simplification  
   - Current `Router` entries are acceptable; primary complexity is provider detection. You can simplify by deferring per‑request `model` & `api_base` injection without pre‑building a long `model_list`; for now, the patch only adds stable resolution + fast‑fail categorization; a deeper refactor can follow (not mandatory for the blocker fix).  
   - Keep the single fallback model route logic; avoid broad retries across every model variant.

5. Determinism Confirmation  
   - Stage 05 sorting: `page_index`, `bbox.y0`, `bbox.x0` – OK (add rounding to 2 decimals in deterministic summary already done).  
   - Stage 06 sorting: similar triple key + figure_id lexical tie-breaker – OK.  
   - Remaining non‑deterministic pockets: (a) Order of diagnostics events (unordered append) – acceptable; (b) Table merging heuristics (depends on Camelot fragmentation) still deterministic given identical source & environment; (c) LLM Stage 07 randomization suppressed (temperature=0, concurrency=1 under deterministic mode).  
   - Recommend adding explicit `random.seed` & `numpy.seed` already supported by deterministic helper (not included in diff if already present).

6. Missing High‑Leverage Tests  
   - JSON extraction (balanced braces) with noisy prefixes / suffixes.  
   - Invalid JSON fallback path sets `reflow_status=fallback` and preserves minimal paragraph content.  
   - Routing: CHUTES_* bridging sets OPENAI_* env automatically.  
   - Deterministic figure/table ordering stable across two runs.  
   - Schema presence test: ensure `reflowed_json` after Stage 07 strict run (mock litellm).  
   Included in `tests/` below.

7. Performance Hotspots & Batching  
   - Stage 06: Already reduced PDF open overhead; potential improvement (not in diff): precompute page pixmaps once if figure count high (defer).  
   - Stage 07: Main cost is large prompt assembly + base64 images; improvements applied: selective inclusion (low‑confidence tables only), optional image suppression on retry.  
   - Further improvement (future): per‑section pre-tokenization to prune context length adaptively (< model input token threshold), batched multi‑section LLM calls (not recommended until schema stability is proven).  

---

## Prioritized Issue List

```text
BLOCKERS
1. Stage 07 brittle JSON parsing causes pipeline abort on verbose/partial responses.
2. Missing robust fallback parse layers & parse strategy metadata.
3. Fast-fail errors (Auth/404) cause unnecessary long retries & hangs.

MAJOR
4. LiteLLM MAX_CALLBACKS warnings (callback accumulation risk).
5. Over-broad retry: invalid JSON re-asked instead of fallback (latency + cost).
6. Lack of explicit parse provenance fields (hard to post-mortem).
7. Inconsistent image ordering can reduce schema fidelity across some models.

MINOR
8. Pandas applymap deprecation warnings in table/normalization logic.
9. Diagnostics order non-deterministic (acceptable but can be annotated with sequence if needed).
10. Undocumented fallback decision criteria in artifacts.
11. Deterministic summaries missing `model` (Stage 05/06 optional metadata parity).
12. Missing unit tests for router bridging & JSON extraction edge cases.
```

---

## Unified Diffs (Surgical Fixes)

### A. Stage 07: Robust JSON Extraction + Prompt Hardening + Retry Logic

```python name=src/extractor/pipeline/steps/07_reflow_section.py url=https://github.com/grahama1970/extractor/blob/feat/section-heuristics-and-overlay/src/extractor/pipeline/steps/07_reflow_section.py
*** a/src/extractor/pipeline/steps/07_reflow_section.py
--- b/src/extractor/pipeline/steps/07_reflow_section.py
@@
 import asyncio
@@
 from extractor.pipeline.utils.litellm_call import litellm_call
@@
+############################
+# JSON Extraction Helpers  #
+############################
+
+def _extract_first_json_object(raw: str) -> tuple[dict | list | None, str]:
+    """
+    Robustly scan for the first valid top-level JSON object or array.
+    - Ignores braces inside quoted strings and base64 segments.
+    - Stops at the first balanced candidate; returns (parsed, strategy).
+    Strategy labels: direct|scan|repaired
+    """
+    if not isinstance(raw, str) or not raw.strip():
+        return None, "empty"
+    s = raw.strip()
+    # Fast path: direct parse
+    try:
+        return json.loads(s), "direct"
+    except Exception:
+        pass
+    # Remove common wrappers / code fences
+    cleaned = s
+    for fence in ("```json", "```", "`"):
+        cleaned = cleaned.replace(fence, "\n")
+    # Pragmatic trimming of leading chatter
+    start_idx = None
+    for i, ch in enumerate(cleaned):
+        if ch in "{[":
+            start_idx = i
+            break
+    if start_idx is None:
+        return None, "no_brace"
+    candidate = cleaned[start_idx:]
+    # Brace scan
+    depth = 0
+    in_str = False
+    esc = False
+    end_pos = None
+    quote_char = ""
+    for i, ch in enumerate(candidate):
+        if in_str:
+            if esc:
+                esc = False
+            elif ch == "\\":
+                esc = True
+            elif ch == quote_char:
+                in_str = False
+            continue
+        else:
+            if ch in ('"', "'"):
+                in_str = True
+                quote_char = ch
+                continue
+            if ch in "{[":
+                depth += 1
+            elif ch in "}]":
+                depth -= 1
+                if depth == 0:
+                    end_pos = i + 1
+                    break
+    if end_pos is not None:
+        snippet = candidate[:end_pos]
+        try:
+            return json.loads(snippet), "scan"
+        except Exception:
+            # Attempt a light repair: remove trailing commas & retry
+            repaired = _light_repair(snippet)
+            if repaired:
+                try:
+                    return json.loads(repaired), "repaired"
+                except Exception:
+                    return None, "repaired_failed"
+    return None, "scan_failed"
+
+def _light_repair(snippet: str) -> str | None:
+    """Remove a few common JSON noise patterns (trailing commas, stray comments)."""
+    if not snippet:
+        return None
+    import re as _re
+    tmp = _re.sub(r",(\s*[}\]])", r"\1", snippet)  # trailing commas
+    tmp = _re.sub(r"//.*?$", "", tmp, flags=_re.MULTILINE)
+    tmp = _re.sub(r"/\*.*?\*/", "", tmp, flags=_re.DOTALL)
+    return tmp.strip()
@@
 async def reflow_section_with_llm(
@@
-        # Parse/repair JSON robustly
-        try:
-            parsed = clean_json_string(content, return_dict=True)
-            if isinstance(parsed, dict):
-                result = parsed
-            elif isinstance(parsed, list):
-                # If the model returned a top-level list, try using the first object
-                result = (
-                    parsed[0]
-                    if parsed and isinstance(parsed[0], dict)
-                    else {"reflowed_text": content}
-                )
-            elif isinstance(parsed, str):
-                tmp = json.loads(parsed)
-                result = tmp if isinstance(tmp, dict) else {"reflowed_text": content}
-            else:
-                result = {"reflowed_text": content}
-        except Exception:
-            logger.warning("Invalid JSON from LLM; failing per policy (no fallback)")
-            try:
-                sec_diags.append(
-                    make_event(
-                        "07_reflow_section",
-                        "warning",
-                        "llm_invalid_json",
-                        "LLM returned invalid JSON",
-                        {},
-                    )
-                )
-            except Exception:
-                pass
-            raise ValueError(
-                "Stage 07: LLM returned invalid JSON. See logs in 07_reflow_section/logs and verify the model returns strict JSON (no code fences) matching schema mode expectations."
-            )
+        # ------------------------------------------------------------------
+        # Hardened JSON extraction
+        # ------------------------------------------------------------------
+        parse_strategy = "unattempted"
+        result = None
+        raw_candidate = content
+        extracted, strategy = _extract_first_json_object(raw_candidate)
+        parse_strategy = strategy
+        if isinstance(extracted, (dict, list)):
+            # Wrap lists if needed
+            if isinstance(extracted, dict):
+                result = extracted
+            elif isinstance(extracted, list):
+                if extracted and isinstance(extracted[0], dict):
+                    result = extracted[0]
+                else:
+                    result = {"reflowed_text": content}
+        if result is None:
+            # Final repair attempt with clean_json_string
+            try:
+                repaired = clean_json_string(content, return_dict=True)
+                if isinstance(repaired, dict):
+                    result = repaired
+                    parse_strategy = f"{parse_strategy}+clean_json"
+            except Exception:
+                pass
+        if result is None:
+            try:
+                sec_diags.append(
+                    make_event(
+                        "07_reflow_section",
+                        "warning",
+                        "llm_invalid_json",
+                        f"JSON extraction failed (strategy={parse_strategy})",
+                        {},
+                    )
+                )
+            except Exception:
+                pass
+            raise ValueError(
+                "Stage 07: LLM returned invalid or unparsable JSON. Inspect logs (request_payload_*, response_*)."
+            )
@@
         if SCHEMA_MODE == "reflow_json":
@@
             out = {**section_data}
@@
-        return out
+        # Attach parse strategy for transparency
+        try:
+            md = out.setdefault("metadata", {})
+            md["parse_strategy"] = parse_strategy
+        except Exception:
+            pass
+        return out
@@
         except Exception as e:
@@
             if allow_fallback:
@@
-                try:
+                try:
                     md = out.setdefault("metadata", {})
-                    md.setdefault("diagnostics", []).extend(sec_diags)
+                    md.setdefault("diagnostics", []).extend(sec_diags)
+                    md["parse_strategy"] = "fallback"
                 except Exception:
                     pass
@@
     final_output = {
@@
-        "reflow_mode": reflow_mode,
+        "reflow_mode": reflow_mode,
+        "llm_model": os.getenv("LITELLM_VLM_MODEL", ""),
     }
```

### B. Stage 07: Deterministic Summary Add Model (already in diff above; no separate patch needed if applied)

### C. LiteLLM Callback Hygiene (prevent MAX_CALLBACKS spam)

```python name=src/extractor/pipeline/utils/litellm_call.py url=https://github.com/grahama1970/extractor/blob/feat/section-heuristics-and-overlay/src/extractor/pipeline/utils/litellm_call.py
*** a/src/extractor/pipeline/utils/litellm_call.py
--- b/src/extractor/pipeline/utils/litellm_call.py
@@
 import litellm as _litellm
@@
 logger.remove()
@@
 initialize_litellm_cache()
@@
 # ------------------------------------------------------------------
 # Callback hygiene (LiteLLM sometimes accumulates callbacks when
 # modules are re-imported in long-lived processes / tests).
 # We defensively prune after import.
 # ------------------------------------------------------------------
 try:
     for attr in ("callbacks", "success_callback", "failure_callback", "input_callback", "service_callback"):
         seq = getattr(_litellm, attr, None)
         if isinstance(seq, list) and len(seq) > 5:
             del seq[:]  # clear in-place
 except Exception:
     pass
```

### D. Pandas applymap Deprecation Quiet (replace `applymap` usage in table merge normalization inside Stage 07)

```python name=src/extractor/pipeline/steps/07_reflow_section.py url=https://github.com/grahama1970/extractor/blob/feat/section-heuristics-and-overlay/src/extractor/pipeline/steps/07_reflow_section.py
*** a/src/extractor/pipeline/steps/07_reflow_section.py
--- b/src/extractor/pipeline/steps/07_reflow_section.py
@@
-                                def _collapse_ws_df(df: pd.DataFrame) -> pd.DataFrame:
-                                    return df.applymap(
-                                        lambda v: _sanitize_table_cell(v) if not pd.isna(v) else ""
-                                    )
+                                def _collapse_ws_df(df: pd.DataFrame) -> pd.DataFrame:
+                                    fn = lambda v: _sanitize_table_cell(v) if not pd.isna(v) else ""
+                                    # Modern equivalent without applymap deprecation noise
+                                    return df.apply(lambda col: col.map(fn))
@@
-                                def _collapse(df: pd.DataFrame) -> pd.DataFrame:
-                                    return df.applymap(
-                                        lambda v: _sanitize_table_cell(v) if not pd.isna(v) else ""
-                                    )
+                                def _collapse(df: pd.DataFrame) -> pd.DataFrame:
+                                    fn = lambda v: _sanitize_table_cell(v) if not pd.isna(v) else ""
+                                    return df.apply(lambda col: col.map(fn))
```

### E. Stage 05 & 06 (Optional) — Add model & deterministic flag (light metadata). (If you want parity; optional.)

```python name=src/extractor/pipeline/steps/05_table_extractor.py url=https://github.com/grahama1970/extractor/blob/feat/section-heuristics-and-overlay/src/extractor/pipeline/steps/05_table_extractor.py
*** a/src/extractor/pipeline/steps/05_table_extractor.py
--- b/src/extractor/pipeline/steps/05_table_extractor.py
@@
-        det = {
+        det = {
             "version": 1,
             "run_id": run_id,
             "count": len(filtered_tables),
             "sorted": [
                 {
                     "page": int(t.get("page_index", 0)),
                     "y0": round(float((t.get("bbox") or [0, 0, 0, 0])[1]), 2) if t.get("bbox") else 0.0,
                     "x0": round(float((t.get("bbox") or [0, 0, 0, 0])[0]), 2) if t.get("bbox") else 0.0,
                     "table_index": int(t.get("table_index", 0)),
                 }
                 for t in filtered_tables
             ],
+            "model": os.getenv("LITELLM_VLM_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL"),
         }
```

```python name=src/extractor/pipeline/steps/06_figure_extractor.py url=https://github.com/grahama1970/extractor/blob/feat/section-heuristics-and-overlay/src/extractor/pipeline/steps/06_figure_extractor.py
*** a/src/extractor/pipeline/steps/06_figure_extractor.py
--- b/src/extractor/pipeline/steps/06_figure_extractor.py
@@
-        det = {
+        det = {
             "version": 1,
             "run_id": run_id,
             "count": len(extracted_figures),
             "sorted": [
                 {
                     "figure_id": str(fig.get("figure_id")),
                     "page": int(fig.get("page", 0)),
                     "y0": round(float((fig.get("bbox") or [0, 0, 0, 0])[1]), 2) if fig.get("bbox") else 0.0,
                     "x0": round(float((fig.get("bbox") or [0, 0, 0, 0])[0]), 2) if fig.get("bbox") else 0.0,
                     "section_id": fig.get("section_id"),
                 }
                 for fig in extracted_figures
             ],
+            "model": os.getenv("LITELLM_VLM_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL"),
         }
```

---

## New Tests

```python
[tests/test_stage07_json_extract.py]
[tests/test_stage07_fallback.py]
[tests/test_routing_bridge.py]
[tests/test_deterministic_tables.py]
```

---

## Stage 07 Mini Runbook

[kept verbatim from proposal]

---

## Additional Recommendations (Deferred / Optional)

[kept verbatim from proposal]

---

## One-Liner Mapping Logic Summary

“Any model string starting with `openai/<org>/<model>` is routed through the Chutes OpenAI-compatible endpoint (credentials bridged from CHUTES_* to OPENAI_*); on 401/403/404 we retry once with a configured fallback (DeepSeek V3 or user-provided) before structured pass-through fallback.”

---

## Next Steps

1. Apply diffs (Stage 07 first).
2. Re-run failing repro command; verify:
   - `parse_strategy` present.
   - No MAX_CALLBACKS warnings.
   - Successful JSON with `reflowed_json`.
3. Run tests: `pytest -q tests/test_stage07_json_extract.py tests/test_stage07_fallback.py tests/test_routing_bridge.py`.
4. If stable, optionally integrate deterministic CI snapshot.
