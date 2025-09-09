Awesome—here’s a no-nonsense, production-ready review + refactor plan for **each** pipeline step you shared. I stick to the “sane & simple” rule: keep logic importable for the agent, keep Typer only at execution time, kill import-time side effects, and remove brittle shims/duplication. Each file below has the exact diffs/snippets you need.

---

### File: `src/extractor/pipeline/steps/01_annotation_processor.py`

**Overall Assessment:** Strong, feature-rich stage with robust PDF + LLM flow. However, it has heavy import-time side effects (Typer shim, logger/env work), duplicate Typer guards, and a few correctness landmines around JSON parsing and resource sampling.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                                    |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Double Typer shim & unconditional `_HAS_TYPER=True`:** The nested try/except sets `_HAS_TYPER=True` even when Typer isn’t present, masking missing deps and enabling broken CLI execution. Failure mode: silent CLI “works” but misreports capabilities. |
| **2. Import-time side effects (env/log + Typer app creation):** Creating `app = typer.Typer(...)` and mutating logger/env at import time prevents the agent from importing the module in a dep-free runner and pollutes other steps/tests.                    |
| **3. Unbounded batch size → memory risk:** The code collects all `items` for `litellm_call` before firing. Large PDFs can exhaust RAM and token budgets.                                                                                                      |
| **4. JSON parse fallback path can leak invalid text:** When `clean_json_string` returns a non-JSON string, the next `json.loads` error is caught but raw strings are stuffed into `interpretation`, causing downstream schema drift.                          |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                     |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Image inline base64 building in loop:** For large annotation sets + images, this hot loop spikes CPU/mem; better stream/batch.                                 |
| **2. Resource sampler gating scattered:** `sampler` enablement appears in multiple places; unify in a small helper for consistency.                                 |
| **3. Rule engine is hidden global:** `_load_relevant_rules()` is file-scoped state. Move to `config` or accept explicit injection to make unit tests deterministic. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                        |
| :---------------------------------------------------------------------------------------------------------------------- |
| **1. Replace Typer shim & import-time app with a main-guarded CLI** (agent can import `process_pdf_pipeline` directly). |
| **2. Batch the LLM calls in fixed windows to cap peak memory.**                                                         |
| **3. Tighten JSON parse path with one authoritative function.**                                                         |

**Patch (key parts):**

```diff
@@
-try:
-    try:
-        import typer
-        _HAS_TYPER = True
-    except Exception:
-        _HAS_TYPER = False
-        class _TyperShim:
-            ...
-    _HAS_TYPER = True
-except Exception:
-    _HAS_TYPER = False
-    class _TyperShim:
-        ...
-    ...
-from typing_extensions import Annotated
+from typing_extensions import Annotated
@@
-load_dotenv(find_dotenv())
-app = typer.Typer(help="Annotate → LLM → Clean PDF → ArangoDB", add_completion=False)
+load_dotenv(find_dotenv())
@@
-# ------------------------------------------------------------------
-# CLI
-# ------------------------------------------------------------------
-@app.command()
-def run( ... ):
+def _run_cli( ... ):
     """Processes a PDF ..."""
     ...
@@
-@app.command("debug-bundle")
-def debug_bundle(...):
+def _debug_bundle_cli(...):
     ...
@@
-if __name__ == "__main__":
-    # Run Typer CLI when executed directly
-    app()
+if __name__ == "__main__":
+    # Typer only at runtime; keeps imports clean for agent
+    from typer import Typer
+    from typing_extensions import Annotated
+    app = Typer(help="Annotate → LLM → Clean PDF → ArangoDB", add_completion=False)
+    app.command()( _run_cli )
+    app.command("debug-bundle")( _debug_bundle_cli )
+    app()
```

**Batching & JSON strictness (drop-in snippets):**

```python
# cap concurrency + batch size
BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "64"))

def _iter_batches(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

# instead of building one giant `items`
all_results = []
for chunk in _iter_batches(items, BATCH_SIZE):
    t0 = time.monotonic()
    all_results.extend(await litellm_call(chunk, concurrency=config.llm_concurrency, desc="Interpreting Annotations"))
    t_llm_ms += int((time.monotonic() - t0) * 1000)
results = all_results
```

```python
def _parse_llm_json(s: str) -> Dict[str, Any]:
    cleaned = clean_json_string(s)
    if isinstance(cleaned, dict): return cleaned
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else {"data": obj}
    except Exception:
        return {"error": "invalid_json", "raw": (cleaned[:1000] if isinstance(cleaned, str) else str(cleaned))}
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                           |
| :----------------------------------------------------------------------------------------- |
| **1. Defensive PyMuPDF usage** (annots kw fallback) avoids version pinning landmines.      |
| **2. Solid diagnostics pattern** (make\_event, resource sampling) that can be centralized. |
| **3. Explicit config dataclass** keeps stage inputs stable and testable.                   |

---

### File: `src/extractor/pipeline/steps/02_marker_extractor.py`

**Overall Assessment:** Clear separation of extraction and CLI; good CPU-only guard. A few correctness & UX nits: duplicated Typer shim, mixed console/log usage, and fragile multiprocess return handling.

| 🔴 **CRITICAL**                                                                                                                                                                                           |
| :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicate Typer shim / import-time `app` creation:** Same breakage mode as 01.                                                                                                                       |
| **2. `q.empty()` after `join()` race:** Queue can be empty even on success if the process errored before enqueue; then we call `result = q.get()` unconditionally. Failure mode: `queue.Empty` exception. |
| **3. `initialize_litellm_cache()` at import:** Side effect on import; causes surprising cache IO in agent runs.                                                                                           |

| 🟡 **MEDIUM**                                                                          |
| :------------------------------------------------------------------------------------- |
| **1. Recomputed diagnostics/time blocks twice in `run()`** (duplicated variables).     |
| **2. Inline `console.print` + `logger` intermixing** → inconsistent logs.              |
| \*\*3. Page bbox/color extraction best-effort path can be hot—guard with feature flag. |

| 🔵 **REFINEMENT**                                                         |
| :------------------------------------------------------------------------ |
| **1. Main-guard Typer; keep `run()` importable.**                         |
| **2. Harden MP handoff:** Use sentinel dict and `q.get_nowait()` guarded. |

**Patch:**

```diff
@@
-    p.join(timeout)
+    p.join(timeout)
@@
-    if p.is_alive():
+    if p.is_alive():
         ...
-    extract_duration_ms = int((time.monotonic()-t_ex0)*1000)
-    if q.empty():
-        console.print("[red]Stage 02 failed: no data returned from extractor process[/red]")
-        raise typer.Exit(1)
-
-    result = q.get()
+    extract_duration_ms = int((time.monotonic()-t_ex0)*1000)
+    try:
+        result = q.get_nowait()
+    except Exception:
+        console.print("[red]Stage 02 failed: no data returned from extractor process[/red]")
+        raise typer.Exit(1)
```

```diff
@@
-if __name__ == "__main__":
-    if DEBUG:
-        ...
-    else:
-        app()
+if __name__ == "__main__":
+    from typer import Typer
+    app = Typer(help="Stage-02: native JSON block extractor")
+    app.command()(run)
+    app.command()(test)
+    app.command("debug-bundle")(debug_bundle)
+    app()
```

| ✅ **STRENGTHS**                                                           |
| :------------------------------------------------------------------------ |
| **1. Spawn/timeout path** makes the step robust against converter stalls. |
| **2. Font/color enrichment** is valuable for 03 heuristics.               |

---

### File: `src/extractor/pipeline/steps/03_suspicious_headers.py`

**Overall Assessment:** Thoughtful verification pipeline with robust preflight, context rendering, and advisory cues. Complexity is justified but import-time Typer + globals remain.

| 🔴 **CRITICAL**                                                                                                                                                                                 |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Import-time Typer shim + `app`** again; agent import pain.                                                                                                                                 |
| \*\*2. FAISS/global negatives comments mid-function indicate previously moved code; ensure none of it runs at import (now OK) but keep it consistent.                                           |
| \*\*3. Preflight assigns `preflight_duration_ms` but later reads via `locals().get(...)`—if exception path is taken, timings contain 0; acceptable, but misleading. Prefer explicit defaulting. |

| 🟡 **MEDIUM**                                                                                                           |
| :---------------------------------------------------------------------------------------------------------------------- |
| \*\*1. `verify_all_headers` and suspicious fallback can multiply candidates; add `task_limit` guard earlier to cap RAM. |
| \*\*2. Context neighbor scan logic uses magic number 5; make constant configurable.                                     |
| \*\*3. `payload["is_header"]` default True hides negative/noisy answers; track “model\_error” separately to avoid bias. |

| 🔵 **REFINEMENT**                                                   |
| :------------------------------------------------------------------ |
| **1. Main-guard Typer.**                                            |
| **2. Extract constants: `MAX_NEIGHBOR_SCAN`, `PREFLIGHT_TIMEOUT`.** |
| **3. Replace `locals().get()` with explicit variables.**            |

**Patch (CLI main-guard & preflight timing):**

```diff
@@
-    try:
-        sample_image_b64 = tasks[0].render_context_image_b64()
-        t_pf0 = time.monotonic()
-        _ = await verify_header_with_llm(sample_image_b64, "Preflight vision capability check.", config.llm_model)
-        preflight_duration_ms = int((time.monotonic()-t_pf0)*1000)
+    preflight_duration_ms = 0
+    try:
+        sample_image_b64 = tasks[0].render_context_image_b64()
+        t_pf0 = time.monotonic()
+        _ = await verify_header_with_llm(sample_image_b64, "Preflight vision capability check.", config.llm_model)
+        preflight_duration_ms = int((time.monotonic()-t_pf0)*1000)
@@
-if __name__ == "__main__":
-    import sys
-    if len(sys.argv) > 1 and sys.argv[1] == "debug":
-        debug_test()
-    else:
-        app()
+if __name__ == "__main__":
+    from typer import Typer
+    app = Typer(help="Verify suspicious headers using a multimodal LLM.", add_completion=False)
+    app.command()(run)
+    app.command("debug-bundle")(debug_bundle)
+    app()
```

| ✅ **STRENGTHS**                                                                  |
| :------------------------------------------------------------------------------- |
| **1. Real vision preflight** prevents wasting batch budget on non-vision models. |
| \*\*2. Context image capture + textual neighbor summaries are spot-on.           |

---

### File: `src/extractor/pipeline/steps/04_section_builder.py`

**Overall Assessment:** Rich header detection & sectionization. Too much logic at import time (Typer shim), and visual composition carries extra deps. Good structure overall.

| 🔴 **CRITICAL**                                                                                                                                      |
| :--------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Typer shim & `app` at import.**                                                                                                                 |
| \*\*2. `detect_header_level` defaults to 2 even for junk; can inflate hierarchy. Failure: misplaced parents.                                         |
| \*\*3. Reuse of `bbox` across multi-page sections may include wrong areas; last/first page bbox logic is heuristic—flagged as such but can mis-crop. |

| 🟡 **MEDIUM**                                                                         |
| :------------------------------------------------------------------------------------ |
| \*\*1. Multiple regex passes for numbering; consolidate for performance.              |
| \*\*2. Visual capture loops import PIL per iteration; move import up (still runtime). |
| \*\*3. Logging configured in CLI but not in bundle path consistently.                 |

| 🔵 **REFINEMENT**                                                  |
| :----------------------------------------------------------------- |
| **1. Main-guard Typer.**                                           |
| **2. Make `detect_header_level` safer: return 0 when no signals.** |

**Patch (header level fallback):**

```diff
 def detect_header_level(text: str) -> int:
@@
-    # Default to level 2
-    return 2
+    # Default: unknown (0) to avoid inventing hierarchy
+    return 0
```

**Patch (main-guard):** same pattern as earlier—wrap Typer under `if __name__ == "__main__":`.

| ✅ **STRENGTHS**                                                                |
| :----------------------------------------------------------------------------- |
| **1. Numbering analysis & depth derivation** enable proper hierarchy creation. |
| **2. Visual composites with page breaks** greatly help QA.                     |

---

### File: `src/extractor/pipeline/steps/05_table_extractor.py`

**Overall Assessment:** Practical Camelot pipeline with multiple strategies, stitching, and metrics. A few duplicated blocks and minor coordinate pitfalls handled.

| 🔴 **CRITICAL**                                                                                                                            |
| :----------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicate initialization blocks in `run()`** (timings/resources twice). Real risk of wrong metrics and wasted CPU.                    |
| **2. Typer shim & import-time `app`.**                                                                                                     |
| \*\*3. `strategy_summary` not consistently updated; `last_good_strategy` assignment is inside an `except` block path—likely a logic error. |

| 🟡 **MEDIUM**                                                                                                                                                                                |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. `extract_table_image` relies on Camelot bbox; fallback for cells is good, but horizontal/vertical padding ratios from env can overrun page for small tables—clamp already done; keep. |
| \*\*2. Data density thresholds are static; expose to CLI.                                                                                                                                    |
| \*\*3. Header dedup heuristic uses column name equality only; acceptable MVP, note in docs.                                                                                                  |

| 🔵 **REFINEMENT**                                              |
| :------------------------------------------------------------- |
| **1. Remove repeated init code; unify once.**                  |
| **2. Main-guard Typer.**                                       |
| **3. Move strategy durations into timings deterministically.** |

**Patch (duplicate init removal & last\_good fix):**

```diff
@@ def run(...):
-    run_id = get_run_id()
-    diagnostics = []
-    errors_count = 0
-    warnings_count = 0
-    import time
-    t0 = time.monotonic()
-    stage_start_ts = iso_now()
-    resources = snapshot_resources("start")
-    import os
-    sampler = start_resource_sampler(...)
-    ...
-    # --- Directory Setup ---
+    # --- Directory Setup & single init block ---
     stage_output_dir = output_dir / "05_table_extractor"
     ...
-    run_id = get_run_id()
-    diagnostics = []
-    errors_count = 0
-    warnings_count = 0
-    import time
-    t0 = time.monotonic()
-    stage_start_ts = iso_now()
-    resources = snapshot_resources("start")
-    import os
-    sampler = start_resource_sampler(...)
+    run_id = get_run_id()
+    diagnostics, errors_count, warnings_count = [], 0, 0
+    import time; t0 = time.monotonic()
+    stage_start_ts = iso_now(); resources = snapshot_resources("start")
+    sampler = start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2"))) if os.getenv("ENABLE_RESOURCE_SAMPLING","0").lower() in ("1","true","yes","y") else None
@@
-                pass
-                if best_strategy:
-                    last_good_strategy = best_strategy
+                pass
+            if best_strategy:
+                last_good_strategy = best_strategy
```

| ✅ **STRENGTHS**                                              |
| :----------------------------------------------------------- |
| **1. Multi-strategy Camelot** substantially improves recall. |
| **2. Header stitching + dedup** are pragmatic and useful.    |

---

### File: `src/extractor/pipeline/steps/06_figure_extractor.py`

**Overall Assessment:** Solid figure extraction with retrying VLM call and padding. Good fallbacks. Needs the same CLI/main-guard and minor hygiene.

| 🔴 **CRITICAL**                                                                                           |
| :-------------------------------------------------------------------------------------------------------- |
| **1. Typer shim & import-time `app`.**                                                                    |
| **2. Logger reconfiguration at import:** `logger.remove()` globally at import affects other stages/tests. |

| 🟡 **MEDIUM**                                                                                                                                        |
| :--------------------------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. Mixed relative path logic for `image_path` can break if results root differs; you already attempt to relativize—guard with try/except (done). |
| \*\*2. `figure_md_diags` built conditionally inside exception; ensure it exists.                                                                     |

| 🔵 **REFINEMENT**                            |
| :------------------------------------------- |
| **1. Move logger config to CLI entry only.** |
| **2. Ensure `figure_md_diags` initialized.** |

**Patch:**

```diff
-logger.remove()
-logger.add(sys.stderr, level="INFO")
+# Configure logger in CLI entry; avoid import-time global mutation

@@
-        return {
+        figure_md_diags = locals().get("figure_md_diags", [])
+        return {
             "figure_id": figure_id,
@@
-            "metadata": {"diagnostics": figure_md_diags} if isinstance(locals().get("figure_md_diags"), list) else {} ,
+            "metadata": {"diagnostics": figure_md_diags} if isinstance(figure_md_diags, list) else {},
```

**Main-guard Typer:** follow the pattern used above.

| ✅ **STRENGTHS**                                                                      |
| :----------------------------------------------------------------------------------- |
| **1. Tenacity retries** on LLM calls; reliable.                                      |
| **2. Context-aware descriptions** (nearby text) aid quality when vision unavailable. |

---

### File: `src/extractor/pipeline/steps/07_reflow_section.py`

**Overall Assessment:** Feature-dense, offline reflow with images + ANN advisory; good fallbacks. Same CLI import pattern issue and some duplication.

| 🔴 **CRITICAL**                                                                                                                                                                                               |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Logger config at import with `logger.add(...)` (global).**                                                                                                                                               |
| **2. Re-declared helper names (get\_\*\_image\_b64 twice)**—ensure no shadowing (you stubbed wrappers that call utility versions; OK but keep names unique if both exist).                                    |
| \*\*3. `asyncio.run` nested via Typer `run()` calling inner `asyncio.run` wrappers—safe, but be careful if any parent loop exists (VS Code debug can inject a loop). Prefer `anyio` or create a private loop. |

| 🟡 **MEDIUM**                                                                               |
| :------------------------------------------------------------------------------------------ |
| \*\*1. `LLM_MODEL` read once; CLI lets you toggle via env only—consider param to `run`.     |
| \*\*2. ANN index build in memory can be big; you already conditionally load from disk—good. |
| \*\*3. Responses API stubbed path—clean up now or hide behind flag.                         |

| 🔵 **REFINEMENT**                                                      |
| :--------------------------------------------------------------------- |
| **1. Main-guard Typer; logger config in CLI.**                         |
| **2. Gate “responses API” dead code behind env flag and default off.** |

**Patch (safe loop helper):**

```python
def _run_async(coro):
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return asyncio.ensure_future(coro)  # for debug contexts
        return asyncio.run(coro)
    except Exception:
        return asyncio.run(coro)
```

Use `_run_async(...)` in CLI.

| ✅ **STRENGTHS**                                                  |
| :--------------------------------------------------------------- |
| **1. Thoughtful fallback design** (pass-through when LLM fails). |
| \*\*2. Clear, testable composition of section context.           |

---

### File: `src/extractor/pipeline/steps/08_lean4_theorem_prover.py`

**Overall Assessment:** Nicely layered extraction → proving, with batch CLI support and fallbacks. Dockerside Lean runner is opinionated; keep optional. CLI/main-guard again.

| 🔴 **CRITICAL**                                                                                                                                                                                                                                                  |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Typer shim & import-time `app`.**                                                                                                                                                                                                                           |
| **2. Hardcoded `docker exec ... lean` path in `execute_lean_code`:** If container isn’t there, returns confusing errors. Must soft-fail with actionable guidance.                                                                                                |
| \*\*3. `get_validation_strategy` optional import; in error case we define a minimal class but still call `await get_validation_strategy(...)` in `prove_with_feedback` (first try block). Failure mode: `ImportError` handled, but ensure we don’t await `None`. |

| 🟡 **MEDIUM**                                                                                               |
| :---------------------------------------------------------------------------------------------------------- |
| \*\*1. Batch CLI contracts complex; validate placeholders early.                                            |
| \*\*2. `tqdm(asyncio.as_completed(...))` displays but order is arbitrary—fine, but make it obvious in logs. |
| \*\*3. Extraction prompt includes full tables; cap size.                                                    |

| 🔵 **REFINEMENT**                                                                  |
| :--------------------------------------------------------------------------------- |
| **1. Add early validation for `LEAN4_CLI_CMD` placeholders.**                      |
| **2. Soft-fail docker path:** detect and switch to extraction-only if not present. |

**Patch (docker presence):**

```diff
 async def execute_lean_code(lean_code: str):
-    try:
+    try:
+        # quick availability check
+        import shutil
+        if not shutil.which("docker"):
+            return ProofResult(False, lean_code, "", "docker not found", 1, "<stdin>", ["docker not found"])
         proc = await asyncio.create_subprocess_exec(
             'docker', 'exec', '-i', 'lean_runner', 
```

**Main-guard Typer:** same pattern.

| ✅ **STRENGTHS**                                           |
| :-------------------------------------------------------- |
| **1. External CLI batches** → portable, faster iteration. |
| \*\*2. Clear statistics and fallbacks.                    |

---

### File: `src/extractor/pipeline/steps/09_section_summarizer.py`

**Overall Assessment:** Clean concurrent summarizer with rolling context and checkpoints. Good JSON-guard pattern. Needs same CLI main-guard and logger/env cleanup.

| 🔴 **CRITICAL**                                                                     |
| :---------------------------------------------------------------------------------- |
| **1. `.env` enforced at import with `sys.exit(1)` if missing**—breaks agent/import. |
| **2. Typer shim & import-time `app`.**                                              |

| 🟡 **MEDIUM**                                                                                                                      |
| :--------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. Rolling window uses previous successes only; if early failures, later summaries have no context. Graceful, but document it. |
| \*\*2. `strict_json` default true—some providers choke; consider retry w/ relaxed parse.                                           |

| 🔵 **REFINEMENT**                                                                                           |
| :---------------------------------------------------------------------------------------------------------- |
| **1. Move `.env` validation into CLI; agent can still import and call `batch_summarize_sections_rolling`.** |
| **2. Add “relaxed JSON retry” once per section.**                                                           |

**Patch (.env move):**

```diff
-if not load_dotenv(find_dotenv()):
-    logger.error("No .env file found - check .env exists")
-    sys.exit(1)
+load_dotenv(find_dotenv())  # optional at import; CLI enforces if needed
```

| ✅ **STRENGTHS**                                                     |
| :------------------------------------------------------------------ |
| **1. Checkpoint summaries** are a great scaling tactic.             |
| **2. JSON guard + `clean_json_string`** keeps outputs machine-safe. |

---

### File: `src/extractor/pipeline/steps/10_arangodb_exporter.py`

**Overall Assessment:** Clear, well-scoped export stage; good index creation and flattening logic. Tighten embedding/DB handling.

| 🔴 **CRITICAL**                                                                                               |
| :------------------------------------------------------------------------------------------------------------ |
| **1. `.env` enforced at import with `sys.exit(1)`**—breaks agent/import.                                      |
| **2. Typer shim & import-time `app`.**                                                                        |
| **3. Embedding generation inside flatten loop w/o batching:** large docs can blow VRAM/RAM; add feature flag. |

| 🟡 **MEDIUM**                                                                                                                                          |
| :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. `generate_breadcrumbs` walks by title text only; parent mapping by ID is fine, but ensure all parents included before children—current code ok. |
| \*\*2. On duplicate ‘replace’ is good, but consider idempotent `_key` hashing carefully (you do: nice).                                                |

| 🔵 **REFINEMENT**                                                 |
| :---------------------------------------------------------------- |
| **1. Make embeddings optional via `--no-embeddings` / env flag.** |
| **2. Move `.env` enforcement to CLI only.**                       |

**Patch (optional embeddings):**

```diff
-EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
+EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
+EMBEDDINGS_ENABLED = os.getenv("EXPORT_EMBEDDINGS", "true").lower() in ("1","true","yes","y")
@@
-        if text_content and _ensure_embedder() is not None:
+        if EMBEDDINGS_ENABLED and text_content and _ensure_embedder() is not None:
```

**Main-guard Typer & env:** follow previous pattern.

| ✅ **STRENGTHS**                                                                |
| :----------------------------------------------------------------------------- |
| **1. Collection/index bootstrapping** avoids “works on my machine” failures.   |
| **2. Order-preserving `object_index_in_doc`** is excellent for reconstruction. |

---

### File: `src/extractor/pipeline/steps/11_arango_create_graph.py`

**Overall Assessment:** Good FAISS + hierarchy weighting; clear edges. Needs non-import `.env`, Typer guard, and optional rationale gating because it calls LLM.

| 🔴 **CRITICAL**                                                                                                                    |
| :--------------------------------------------------------------------------------------------------------------------------------- |
| **1. `.env` enforced at import**; same issue.                                                                                      |
| **2. Typer shim & import-time `app`.**                                                                                             |
| **3. Optional FAISS availability not enforced:** if `_HAS_FAISS=False`, later functions still type-reference `faiss`; guard early. |

| 🟡 **MEDIUM**                                                                          |
| :------------------------------------------------------------------------------------- |
| \*\*1. Rationale generation uses LLM for every edge; add cap (`GRAPH_MAX_RATIONALES`). |
| \*\*2. Cosine normalize in place; safe, but document embeddings must be non-zero.      |

| 🔵 **REFINEMENT**                                               |
| :-------------------------------------------------------------- |
| **1. Early exit if FAISS not present with actionable message.** |
| **2. Cap rationales & gate behind flag.**                       |

**Patch (faiss guard + rationale cap):**

```diff
-if not load_dotenv(find_dotenv(), override=True):
-    raise ValueError("No .env file found - check .env exists")
+load_dotenv(find_dotenv(), override=True)
@@
 if not _HAS_FAISS:
-    # later functions will break; fail early in CLI
+    logger.warning("FAISS not available; graph building requires embeddings+FAISS.")
@@
 async def enrich_edges_with_rationales(edges: List[Dict[str, Any]], doc_text_map: Dict[str, str]) -> None:
+    max_r = int(os.getenv("GRAPH_MAX_RATIONALES", "500"))
+    if len(edges) > max_r:
+        subset = edges[:max_r]
+    else:
+        subset = edges
```

**Main-guard Typer:** as before.

| ✅ **STRENGTHS**                                                       |
| :-------------------------------------------------------------------- |
| **1. Combined semantic + hierarchy weight** is a great ranking proxy. |
| **2. Optional rationales** add explainability.                        |

---

### File: `src/extractor/pipeline/steps/12_insert_annotations.py`

**Overall Assessment:** Focused utility to load annotations and bridge with pdf\_objects. Good graph checks. Needs the usual CLI guard and optional `.env`.

| 🔴 **CRITICAL**                               |
| :-------------------------------------------- |
| **1. Typer shim & import-time `app`.**        |
| **2. `.env` must not be required at import.** |

| 🟡 **MEDIUM**                                                                                                    |
| :--------------------------------------------------------------------------------------------------------------- |
| \*\*1. Graph recreation if vertices differ can drop edges briefly; acceptable for util, but log loudly (you do). |
| \*\*2. AQL string constructed inline; safe params used—good.                                                     |

| 🔵 **REFINEMENT**                                                               |
| :------------------------------------------------------------------------------ |
| **1. Add `--source-pdf` override to scope bridging when `source_pdf` missing.** |
| **2. Batch edges in chunks of 5–10k for faster import.**                        |

**Patch (batch insert):**

```python
def _chunks(xs, n=5000):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

...
if edge_docs:
    ecol = db.collection(edge_col)
    created = 0
    for chunk in _chunks(edge_docs):
        edres = ecol.import_bulk(chunk, on_duplicate='ignore')
        created += int(edres.get('created', 0) or 0)
    logger.info(f"Edges inserted: created={created}, total_docs={len(edge_docs)}")
```

| ✅ **STRENGTHS**                                   |
| :------------------------------------------------ |
| **1. Bidirectional edges** make traversal simple. |
| **2. Page-based bridging** is pragmatic and fast. |

---

## Cross-cutting “Sanest Approach” changes (apply to **all** steps)

1. **Stop import-time Typer and global mutations.**

   * Move all `app = Typer(...)` and logger configuration into `if __name__ == "__main__":` blocks.
   * Expose importable functions (`process_*`, `run`, etc.) for the agent.

2. **Delete all Typer shims.**

   * They hide errors and complicate imports. If Typer isn’t installed in the agent, the agent **doesn’t call CLI**; it imports and calls functions.

3. **Env & logging only in CLI.**

   * `load_dotenv(...)` may remain optional at import; enforce presence only when the CLI starts.

4. **Add safe async runner helper** (07 shows `_run_async`) wherever you currently call `asyncio.run` under Typer, so the VS Code debug loop won’t conflict.

5. **Batch any potentially large LLM or PDF operations** (01, 07) and guard with env flags (`LLM_BATCH_SIZE`, `EXPORT_EMBEDDINGS`, `GRAPH_MAX_RATIONALES`).

6. **Document one rule in README** (single source of truth):

   * “**Humans** run Typer CLIs. **Agent** imports and calls the stage functions directly. No deps at import.”

---

## What you’ll end up with

* **One-file-per-step** (unchanged), with **logic importable** and **Typer only at runtime**.
* The agent can **import every stage** and call `process_*` / `run(...)` functions directly.
* No shims, no import-time side effects, and predictable logging/diagnostics.

If you want, I can generate a single patchset that applies the **main-guard Typer conversion + env/log fixes** across all 12 files in one sweep.
