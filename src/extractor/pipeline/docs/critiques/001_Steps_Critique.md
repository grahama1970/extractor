Below is a complete, file-by-file review with concrete, minimal fixes. I’ve focused on production breakages first, then longer-term risks, then hygiene, and finally strengths. Patches are small and targeted—no unnecessary abstraction.

---

### File: `src/extractor/pipeline/steps/01_annotation_processor.py`

**Overall Assessment:** Solid POC for page/annotation cropping + multimodal prompting. Main risks are silent exception swallowing and a few duplicated init blocks that can hide failures or waste time.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                                                                                        |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Silent JSON parsing fallthrough can mask provider errors:** On invalid LLM JSON you warn and write `"raw_response"`, but the pipeline continues without incrementing `errors_count` or emitting a diagnostic consistently. This hides model failures and leads downstream to trust `interpretation`.         |
| **2. Excessive blanket `except Exception:` guards around text parsing and bbox union:** A handful of `try/except: pass` blocks (font size extraction, bbox union, gridlines) can produce partially-filled annotations without diagnostics; downstream rules then operate on missing features and can misclassify. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                                                                                                                                         |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicate initialization and repeated `get_run_id()` calls:** `run_id`, `diagnostics`, `errors_count`, `warnings_count` are reset multiple times inside `process_pdf_pipeline`, risking inconsistent counts.                                                                                                       |
| **2. Mixed model defaults across CLI and dataclass:** `Config.llm_model` defaults to `openai/gpt-4o-mini` but CLI default sets `openai/gpt-5-mini`. Differences can be confusing during debugging.                                                                                                                      |
| **3. Potential memory pressure when processing many pages:** You save every pixmap to disk (good), but feature extraction uses new `fitz.open` per pipeline run only—fine—but resource sampler won’t capture per-image memory spikes if `psutil` import is missing (you already handle, but the behavior isn’t logged). |

| 🔵 **REFINEMENT / CODE HYGIENE**                      |
| :---------------------------------------------------- |
| **1. Always log invalid JSON as error and count it:** |

```diff
diff --git a/src/extractor/pipeline/steps/01_annotation_processor.py b/src/extractor/pipeline/steps/01_annotation_processor.py
@@ -420,9 +420,15 @@
             except json.JSONDecodeError:
-                logger.warning(
-                    f"Invalid JSON for {d.get('id')}: {cleaned[:200]}..."
-                )
+                logger.error(f"Invalid JSON for {d.get('id')}: {cleaned[:200]}...")
+                try:
+                    diagnostics.append(make_event(
+                        "01_annotation_processor","error","llm_invalid_json",
+                        "Model returned invalid JSON", {"annotation_id": d.get("id")}
+                    ))
+                    errors_count += 1
+                except Exception:
+                    pass
                 d["interpretation"] = {"error": "Invalid JSON response from LLM", "raw_response": cleaned}
```

\| **2. De-duplicate counters & run\_id init:** |

```diff
@@ async def process_pdf_pipeline(config: Config):
-    run_id = get_run_id()
-    diagnostics: List[Dict[str, Any]] = []
-    errors_count = 0
-    warnings_count = 0
+    run_id = get_run_id()
+    diagnostics: List[Dict[str, Any]] = []
+    errors_count = 0
+    warnings_count = 0
@@
-    run_id = get_run_id()
-    diagnostics = []
-    errors_count = 0
-    warnings_count = 0
+    # (removed duplicate re-initialization)
```

\| **3. Align model default in CLI with dataclass:** Choose one. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                                                                     |
| :--------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Robust PyMuPDF fallbacks:** You handle `annots=False` availability and TypeError fallback correctly.                                            |
| **2. Simple, explainable rules for validator suggestion + stage relevance mapping:** Nice bridge between weak vision features and downstream stages. |

---

### File: `src/extractor/pipeline/steps/02_marker_extractor.py`

**Overall Assessment:** Practical “Marker internals” adapter that pulls richer block metadata. The structure is good; risks center on subprocess timeout handling and brittle attribute probing.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                   |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Hard failure if `extractor.core.converters/pdf` not installed:** You raise a `RuntimeError` (good), but the CLI exits with generic error text. This is okay functionally; no hard crash paths observed. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                                     |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. PyMuPDF color enrichment may do expensive `get_text('dict')` per block:** You cache per page (good), but still scan spans repeatedly. Consider early `bbox` rejection before scanning lines (small speed win). |
| **2. Logging reset (`logger.remove()`) inside CLI can conflict with other stages:** You already wrapped in try/except; still consider scoping to a local logger alias consistently across steps.                    |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                      |
| :-------------------------------------------------------------------------------------------------------------------- |
| **1. Normalize `suspicious_header` tagging:** You compute it twice (flag and reasons). Consider a helper for clarity. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                     |
| :----------------------------------------------------------------------------------- |
| **1. Cross-platform MP worker at top-level:** Enables Windows/macOS spawn semantics. |
| **2. Timeouts with hard terminate/kill path:** Good defensive subprocess discipline. |

---

### File: `src/extractor/pipeline/steps/03_suspicious_headers.py`

**Overall Assessment:** The verifier is well-structured (task objects, preflight, batch litellm). One missing function will crash by default.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                 |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `_retrieve_prior_decisions` is referenced but not defined:** With `use_prior=True` (default), this raises `NameError` during preparation.                             |
| \*\*2. `verify_all_headers` preflight uses actual candidate (good) but an empty candidate list returns early without recording diagnostics; not a break, just a minor gap. |

**Fix (add a tiny no-op prior retrieval and guard):**

```diff
diff --git a/src/extractor/pipeline/steps/03_suspicious_headers.py b/src/extractor/pipeline/steps/03_suspicious_headers.py
@@
 RELEVANT_RULES = _load_relevant_rules()
@@
+def _retrieve_prior_decisions(header_text_norm: str, font_sig: str, limit: int = 5) -> list[dict]:
+    """
+    Stubbed retrieval: returns [] until DB-backed prior store is implemented.
+    Keeps Stage 03 offline and prevents NameError when --use-prior is enabled.
+    """
+    return []
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                          |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Heavy reliance on `page_blocks` ordering for context neighbors:** If upstream order changes, your ±5 scan may skip true textual neighbors. Consider bbox-based nearest-neighbor as a backup.        |
| **2. Reasonable defaults, but error handling can over-accept headers:** On LLM errors you set `is_header=True`. This choice trades FP/FN; consider flipping under `--strict` to prefer demotion instead. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                       |
| :------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Make preflight duration explicit in timings:** You compute it; ensure it’s always present. (You already use `locals().get`—fine.) |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                |
| :---------------------------------------------------------------------------------------------- |
| **1. Clear task struct + image saving per candidate:** Debuggability is excellent.              |
| **2. Optional human cues blending with rules:** Good use of Stage 01 evidence without coupling. |

---

### File: `src/extractor/pipeline/steps/04_section_builder.py`

**Overall Assessment:** Sensible hierarchy build from verified blocks with practical numbering/keyword heuristics and optional visuals.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **None observed.**                         |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                                                                             |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Visual extraction assumes bbox carries across multi-page spans:** The bbox per section is derived from block union; multi-page handling is heuristic (fine), but cropping may be too generous or clipped. Add a clamp with min height and safe margin. |
| **2. Hashing title text for `section_hash`:** If title changes slightly after reflow, links break. Consider hashing based on (page\_start, level, normalized\_numbering) as fallback.                                                                       |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                  |
| :-------------------------------------------------------------------------------- |
| **1. Remove unused variables and ensure `ImageDraw` import is local where used.** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                       |
| :----------------------------------------------------------------------------------------------------- |
| **1. Clean split of acceptance order (Stage 03 first, then heuristics):** Keeps stage contracts clear. |
| **2. Helpful per-section diagnostics (`_append_diag`):** Great for audits.                             |

---

### File: `src/extractor/pipeline/steps/05_table_extractor.py`

**Overall Assessment:** Thoughtful multi-strategy Camelot approach with stitching and density filters. One indentation bug neuters strategy caching; some duplication in timings logic.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                        |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `last_good_strategy` never updates unless an exception occurs (indentation bug):** The assignment sits under an `except` block, so it’s skipped in the non-error path. This degrades performance and recall. |

**Fix (move assignment out of `except`):**

```diff
diff --git a/src/extractor/pipeline/steps/05_table_extractor.py b/src/extractor/pipeline/steps/05_table_extractor.py
@@ def extract_all_tables(pdf_path: Path, output_dir: Path, diagnostics: Optional[list] = None) -> List[Dict[str, Any]]:
-            except Exception:
-                pass
-                if best_strategy:
-                    last_good_strategy = best_strategy
+            except Exception:
+                pass
+            if best_strategy:
+                last_good_strategy = best_strategy
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                               |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicated sampler/timings code inside `run()` (twice):** Increases maintenance risk and can skew metrics.                                                               |
| **2. `strategy_summary` is built locally in `extract_all_tables` but never returned; `run()` attaches an empty summary.** Return it to make timing analytics actually useful. |

**Refactor snippet (return summary):**

```diff
-    return all_tables
+    return all_tables, strategy_summary
@@ def run(...):
-    all_tables = extract_all_tables(pdf_path, image_output_dir, diagnostics)
+    all_tables, strategy_summary = extract_all_tables(pdf_path, image_output_dir, diagnostics)
```

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                     |
| :----------------------------------------------------------------------------------------------------------------------------------- |
| **1. Consolidate repeated `stop_resource_sampler` & `build_stage_timings` blocks.**                                                  |
| **2. Safer `_bbox` fallback:** you already compute from `cells` (good). Consider skipping tables without bbox & df jointly (you do). |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                            |
| :------------------------------------------------------------------------------------------ |
| **1. Header coalesce + dedup heuristics:** This fixes frequent Camelot artifacts elegantly. |
| **2. Table→Section association via bbox on page ranges:** Practical and efficient.          |

---

### File: `src/extractor/pipeline/steps/06_figure_extractor.py`

**Overall Assessment:** Straightforward figure extraction + concise descriptions with retry and graceful fallback.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                     |
| :--------------------------------------------------------------------------------------------- |
| **None observed.** (LLM failures fall back with diagnostics; bbox estimation path is guarded.) |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                          |
| :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicate logger setup and samplers (like other stages):** Not harmful, but makes logs inconsistent across stages.                                  |
| **2. Vision support heuristic based on model name string:** Acceptable for MVP, but consider a single preflight util (you already have one in Stage 07). |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                         |
| :--------------------------------------------------------------------------------------- |
| **1. Small tidy of error diagnostics assembly path (set `figure_md_diags=[]` upfront).** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                          |
| :------------------------------------------------------------------------ |
| **1. Good context capture with nearby text to help description quality.** |
| **2. Tenacity retries with exponential backoff on VLM calls.**            |

---

### File: `src/extractor/pipeline/steps/07_reflow_section.py`

**Overall Assessment:** Ambitious offline reflow that fuses images/tables/annotations. A few copy/paste mistakes and shadowed imports cause runtime breakage in debug mode.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                  |
| :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `debug-bundle` references undefined vars** (`sampler`, `stage_start_ts`, `t0`, `diagnostics`, `resources`, `run_id`), causing `NameError`.                                                                             |
| **2. Shadowing imported helpers (`get_section_image_b64`, etc.) with local functions:** If the import stays, Python replaces the import with your definitions (OK), but it’s confusing and risks recursion if names change. |
| \*\*3. Duplicate `if __name__ == "__main__": app()` blocks later in file (two of them in total with variations in other steps) can lead to unexpected main-time behavior.                                                   |

**Fix (initialize debug variables + remove import shadowing; keep local helpers):**

```diff
diff --git a/src/extractor/pipeline/steps/07_reflow_section.py b/src/extractor/pipeline/steps/07_reflow_section.py
@@
-from extractor.pipeline.utils.image_io import (
-    get_section_image_b64,
-    get_table_image_b64,
-    get_figure_image_b64,
-    get_annotation_image_b64,
-)
+# Use local minimal image readers below to avoid external coupling in Stage 07.
@@ def debug_bundle(...):
-    async def run_tasks():
+    # initialize minimal diagnostics/timing like run()
+    run_id = get_run_id()
+    diagnostics = []
+    errors_count = 0
+    warnings_count = 0
+    import time as _t
+    stage_start_ts = iso_now()
+    t0 = _t.monotonic()
+    resources = snapshot_resources("start")
+    sampler = None
+
+    async def run_tasks():
         tasks = [reflow_section_with_llm(s, output_dir, include_images=include_images, allow_fallback=allow_fallback) for s in sections_to_process]
         return await tqdm_asyncio.gather(*tasks, desc="Reflowing Sections (debug)")
@@
-    processed_sections = asyncio.run(run_tasks())
+    processed_sections = asyncio.run(run_tasks())
@@
-    try:
-        samples = stop_resource_sampler(sampler) if sampler else []
-        if samples:
-            resources.setdefault("resource_samples", samples)
-    except Exception:
-        pass
-    timings = build_stage_timings(stage_start_ts, t0)
+    timings = build_stage_timings(stage_start_ts, t0)
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                             |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Two parallel “Responses API” code paths are defined but `_aresponses=None`; dead path makes code harder to follow.**                                   |
| **2. Double inclusion of images (you build both Chat Completions style and “responses\_user\_content” list):** You overwrite the latter; consider one path. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                    |
| :-------------------------------------------------------------------------------------------------- |
| **1. Don’t redefine helpers with same names as imports (keep local names like `_load_image_b64`).** |
| **2. Factor common diags creation to a tiny helper to avoid repeated `try/except`.**                |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                          |
| :---------------------------------------------------------------------------------------- |
| **1. Thoughtful combination of section, tables, figures, annotations to ground the VLM.** |
| **2. Clean fallback plan when model returns empty or invalid JSON.**                      |

---

### File: `src/extractor/pipeline/steps/08_lean4_theorem_prover.py`

**Overall Assessment:** Flexible design (LLM extraction → Lean proving via CLI or Docker). A couple of “main” blocks collide and will throw at runtime; also, Docker runner is aspirational.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                      |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicate `__main__` blocks and an undefined `_HAS_TYPER`:** The second block references `_HAS_TYPER` which is not defined, causing `NameError` when the module is executed directly.                                                      |
| **2. Aspirational Docker exec (`docker exec lean_runner ...`) without environment detection:** If Docker container isn’t running, proving path throws. You do catch in `prove_requirement` fallback, but `execute_lean_code` itself will raise. |

**Fix (remove the duplicate/undefined main guard and make Docker execution opt-in behind env):**

```diff
diff --git a/src/extractor/pipeline/steps/08_lean4_theorem_prover.py b/src/extractor/pipeline/steps/08_lean4_theorem_prover.py
@@
-if __name__ == "__main__":
-    app()
-
-
-# Fallback argparse runner when Typer is unavailable
-
-if __name__ == "__main__":
-    try:
-        if _HAS_TYPER:
-            app()
-        else:
-            raise ImportError
-    except Exception:
-        import argparse
-        ...
+if __name__ == "__main__":
+    app()
```

**Optional hardening for Docker path:**

```diff
@@ async def execute_lean_code(lean_code: str):
-    proc = await asyncio.create_subprocess_exec(
+    if os.getenv("LEAN_DOCKER_ENABLED","").lower() not in ("1","true","yes","y"):
+        raise RuntimeError("Docker proving disabled; set LEAN_DOCKER_ENABLED=1 to enable")
+    proc = await asyncio.create_subprocess_exec(
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                               |
| :---------------------------------------------------------------------------------------------------------------------------- |
| **1. Timeout control missing for Lean proving subprocess:** Large proofs can hang. Add `asyncio.wait_for` or process timeout. |
| \*\*2. Strategy selection path depends on optional package; you provide a stub (good), but log clearly when stubbing.         |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                 |
| :----------------------------------------------------------------------------------------------- |
| **1. Consolidate tqdm import style (you import `tqdm` from `tqdm.asyncio` and use it wrapped).** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                              |
| :---------------------------------------------------------------------------- |
| **1. Batch JSONL CLI support with three contract shapes:** Great portability. |
| **2. Clean statistics aggregation for success/failure counts.**               |

---

### File: `src/extractor/pipeline/steps/09_section_summarizer.py`

**Overall Assessment:** Good rolling-window summaries with optional “checkpoint” aggregation. A duplicated main block will throw.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                 |
| :----------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Duplicate `__main__` fallback with `_HAS_TYPER` (undefined):** Same issue as Stage 08; will raise `NameError` when executed directly. |

**Fix (remove fallback block):**

```diff
diff --git a/src/extractor/pipeline/steps/09_section_summarizer.py b/src/extractor/pipeline/steps/09_section_summarizer.py
@@
-if __name__ == "__main__":
-    try:
-        if _HAS_TYPER:
-            app()
-        else:
-            raise ImportError
-    except Exception:
-        import argparse
-        ...
+if __name__ == "__main__":
+    app()
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Reliance on provider JSON mode without strict validation:** You already fall back to naive text; consider counting and emitting diagnostics for invalid JSON per section. |
| \*\*2. `aresponses` path is dead in most configs; either remove or gate behind env to reduce confusion.                                                                        |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                          |
| :---------------------------------------------------------------------------------------- |
| **1. Parameterize model name once (env → single function) to avoid drift across stages.** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                  |
| :-------------------------------------------------------------------------------- |
| **1. Rolling context + periodic checkpoint summaries scales well to large docs.** |
| **2. Test command with a self-contained section is handy for smoke tests.**       |

---

### File: `src/extractor/pipeline/steps/10_arangodb_exporter.py`

**Overall Assessment:** Clean, centralized export with ordering, indexes, and flattening. Well-designed for downstream graph stages.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **None observed.**                         |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                     |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Embedding model as a hard dependency:** You lazy-load and fall back (good). Consider environment flag to skip embeddings entirely for low-RAM containers.      |
| **2. `text_content` for Tables/Figures is a stub string; downstream semantic edges may be weaker. If embedding present, consider adding small caption/first rows.** |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                                                            |
| :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Hash key composition:** Using `source_pdf + section_id + type + index` is fine. Consider including `object_index_in_doc` in the `_key` source string for auditability. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                  |
| :-------------------------------------------------------------------------------- |
| **1. Preserves document reading order via `object_index_in_doc` and indexes it.** |
| **2. Good index set (persistent + fulltext) for common queries.**                 |

---

### File: `src/extractor/pipeline/steps/11_arango_create_graph.py`

**Overall Assessment:** Sensible FAISS-backed similarity edges with hierarchy weighting and optional rationales.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**       |
| :----------------------------------------------- |
| **None observed (assuming FAISS is installed).** |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                       |
| :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Rationale LLM calls can get expensive:** You batch per edge; consider gating by weight threshold or cap per node. You have concurrency control; good.            |
| **2. Normalization assumes cosine after L2 normalize (correct). Ensure embeddings are non-zero; if some are zero vectors, FAISS normalize will error.** Add a filter. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                               |
| :--------------------------------------------------------------------------------------------- |
| **1. Make `GRAPH_RELATIONSHIPS_ENABLED` short-circuit earlier to skip FAISS builds entirely.** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                |
| :------------------------------------------------------------------------------ |
| **1. Hierarchy distance blended with semantic similarity gives durable edges.** |
| **2. Debug-bundle path outputs edges JSON without DB dependency.**              |

---

### File: `src/extractor/pipeline/steps/12_insert_annotations.py`

**Overall Assessment:** Useful graph bridge between annotations and `pdf_objects`. There’s a serious indentation error that will run the bridging loop unconditionally and append edges only on exceptions.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                     |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Indentation bug: bridging loop runs outside `if mode in {"bridge","both"}` and edges append occurs inside the `except` block only.** This yields `NameError` (undefined `docs_for_bridge`/`edge_docs`) or zero edges on the success path. |

**Fix (wrap loop and move edge creation outside `except`):**

```diff
diff --git a/src/extractor/pipeline/steps/12_insert_annotations.py b/src/extractor/pipeline/steps/12_insert_annotations.py
@@ def run(...):
-    if mode_l in {"bridge", "both"}:
+    if mode_l in {"bridge", "both"}:
         ...
-        edge_docs: List[Dict[str, Any]] = []
-    for d in docs_for_bridge:
-        page = d.get('page')
-        if page is None:
-            continue
-        aql = f"""
-            FOR o IN {vertex_col}
-              FILTER o.page_num == @p
-                AND (@src == null OR o.source_pdf == @src)
-              RETURN o._id
-            """
-        try:
-            ids = list(db.aql.execute(aql, bind_vars={'p': int(page), 'src': source_pdf}))
-        except Exception:
-            ids = []
-            aid = f"{ann_col}/{d['_key']}"
-            for oid in ids:
-                edge_docs.append({
-                    '_from': aid,
-                    '_to': oid,
-                    'relationship_type': 'ann_to_object',
-                    'weight': 0.2,
-                    'created_at': datetime.now(timezone.utc).isoformat(),
-                })
-                edge_docs.append({
-                    '_from': oid,
-                    '_to': aid,
-                    'relationship_type': 'object_to_ann',
-                    'weight': 0.2,
-                    'created_at': datetime.now(timezone.utc).isoformat(),
-                })
-        if edge_docs:
-            ecol = db.collection(edge_col)
-            edres = ecol.import_bulk(edge_docs, on_duplicate='ignore')
-            logger.info(f"Edges inserted: created={edres.get('created',0)}, errors={edres.get('errors',0)}")
+        edge_docs: List[Dict[str, Any]] = []
+        for d in docs_for_bridge:
+            page = d.get('page')
+            if page is None:
+                continue
+            aql = f"""
+                FOR o IN {vertex_col}
+                  FILTER o.page_num == @p
+                    AND (@src == null OR o.source_pdf == @src)
+                  RETURN o._id
+            """
+            try:
+                ids = list(db.aql.execute(aql, bind_vars={'p': int(page), 'src': source_pdf}))
+            except Exception:
+                ids = []
+            aid = f"{ann_col}/{d['_key']}"
+            for oid in ids:
+                edge_docs.append({
+                    '_from': aid, '_to': oid,
+                    'relationship_type': 'ann_to_object',
+                    'weight': 0.2, 'created_at': datetime.now(timezone.utc).isoformat(),
+                })
+                edge_docs.append({
+                    '_from': oid, '_to': aid,
+                    'relationship_type': 'object_to_ann',
+                    'weight': 0.2, 'created_at': datetime.now(timezone.utc).isoformat(),
+                })
+        if edge_docs:
+            ecol = db.collection(edge_col)
+            edres = ecol.import_bulk(edge_docs, on_duplicate='ignore')
+            logger.info(f"Edges inserted: created={edres.get('created',0)}, errors={edres.get('errors',0)}")
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                            |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `ensure_graph` may drop and recreate graph if edge defs differ:** That’s disruptive in multi-tenant DBs. Consider updating edge def or just log/warn. |

| 🔵 **REFINEMENT / CODE HYGIENE**                               |
| :------------------------------------------------------------- |
| **1. Factor page-join query into a small function and reuse.** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                         |
| :----------------------------------------------------------------------- |
| **1. Two-way edges (annotation↔object) aid traversal from either side.** |
| **2. Graceful creation of DB/collections when missing.**                 |

---

### File: `src/extractor/pipeline/steps/14_report_generator.py`

**Overall Assessment:** Handy aggregator; good for end-to-end validation. The logic is conservative; errors surface as missing sections rather than crashes.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **None observed.**                         |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                                                       |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Content summary assumes `merged_tables`, `reflowed`, `text_chunks` keys:** Stage 07 output names differ; summary renders zeros—harmless but misleading. Gate with `get()` or adapt names (`tables`, `figures`, `reflow_status`). |

**Small adjustment example:**

```diff
- "reflowed": section.get("reflowed", False),
- "text_chunks": len(section.get("text_chunks", [])),
- "tables": len(section.get("merged_tables", [])),
+ "reflowed": section.get("reflow_status") in ("success","success_placeholder","fallback"),
+ "text_chunks": len((section.get("blocks") or [])),
+ "tables": len(section.get("tables", [])),
```

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                   |
| :--------------------------------------------------------------------------------------------------------------------------------- |
| **1. Print the canonical file actually loaded per stage in the report to spot stale artifacts (you already log this to console).** |

| ✅ **STRENGTHS / GOOD PRACTICES**                                   |
| :----------------------------------------------------------------- |
| **1. Dual output (JSON + Markdown) with stable paths.**            |
| **2. Overall quality score composed from stage-specific signals.** |

---

## Cross-Cutting Recommendations (kept minimal)

1. **Kill duplicate `__main__` blocks and undefined guards** (Stages 08 and 09): already patched above.
2. **Centralize model selection/env**: a tiny util (e.g., `get_default_model(kind="vlm"|"small")`) to avoid drift between stages.
3. **Emit consistent diagnostics**: when you catch and continue, append a `make_event` with severity; you already have great helpers—use them instead of silent `pass`.

---

## Summary of “Halucinated/Aspirational/Stubbed” Spots and Working Paths

* **Stage 03 prior retrieval**: **Stubbed** `_retrieve_prior_decisions` implemented as no-op to prevent crashes. Replace later with DB read.
* **Stage 08 Docker Lean runner**: **Aspirational**—now guarded by env flag; CLI proving path remains the primary, working solution.
* **Stage 12 bridging**: **Buggy indentation** fixed; edges now created on the happy path.

If you want, I can produce a single PR branch that contains the exact patches above and a smoke-test script to exercise `run --help` for all stages and `debug-bundle` for the stages with debug modes.
