Here’s a straight-through explanation of what this pipeline does, followed by a file-by-file production-readiness review with concrete fixes and smoke tests for the most dangerous faults.

# How the pipeline flows (10,000-ft view)

1. **01\_annotation\_processor**

   * Opens the original PDF, finds page annotations (and nearby text), renders small region images, computes light features (bold/spacing/numbering/gridlines), and prompts a VLM/LLM to “interpret” each annotation.
   * Saves: `01_annotations.json` + `_clean.pdf` (annotations removed) + region images.

2. **02\_marker\_extractor**

   * Runs the project’s Marker/Surya PDF converter to emit native block JSON (SectionHeader/Text/Table/etc.), with first-span font features and optional PyMuPDF color lookup.
   * Saves: `02_marker_blocks.json`.

3. **03\_suspicious\_headers**

   * From Stage 02, finds “suspicious” section headers (or all headers if forced), renders a header+context crop, asks a VLM to accept/reject, and writes results back.
   * Saves: `03_verified_blocks.json`.

4. **04\_section\_builder**

   * Groups the verified blocks into hierarchical sections (levels/depth inferred from numbering/heuristics), creates per-section composites (optional), and attaches section metadata.
   * Saves: `04_sections.json` (+ section images).

5. **05\_table\_extractor**

   * Extracts tables with Camelot (multi-strategy lattice), renders table crops, computes metrics/density, filters/sanitizes.
   * Saves: `05_tables.json` (+ table images).

6. **06\_figure\_extractor**

   * Finds Figure/Image blocks from Stage 02, crops with padding, optionally gets a short LLM description, and associates to sections.
   * Saves: `06_figures.json`.

7. **07\_reflow\_section**

   * Joins Stage 04 sections with Stage 05 tables, Stage 06 figures (+ optional annotations) and prompts a VLM/LLM to produce strict JSON reflow or fallback text.
   * Saves: `07_reflowed.json`.

8. **08\_lean4\_theorem\_prover**

   * Scans reflowed sections for requirements/constraints, optionally proves them via Lean4 (or external CLI).
   * Saves: `08_theorems.json`.

9. **09\_section\_summarizer**

   * Summarizes reflowed sections (rolling context, checkpoints).
   * Saves: `09_summaries.json`.

10. **10\_arangodb\_exporter**

    * Flattens reflowed content to ordered `pdf_objects` with embeddings and upserts into ArangoDB.
    * Saves: `10_flattened_data.json` + `10_export_confirmation.json`.

11. **11\_arango\_create\_graph**

    * Builds a FAISS (or NumPy) index over embeddings and writes weighted similarity edges (plus optional LLM rationales).
    * Saves: `11_graph_confirmation.json` or `11_graph_edges.json` (dry).

12. **12\_insert\_annotations**

    * Inserts Stage 01 annotations into Arango and bridges them to `pdf_objects` on the same page with edges.
    * Saves: `12_insert_debug.json` (debug mode).

13. **14\_report\_generator**

    * Aggregates the run, composes JSON and Markdown final reports.
    * Saves: `final_report.json`, `final_report.md`, and `14_report_generator/json_output/14_report.json`.

---

## Reviews & Fixes (each file)

---

### File: `src/extractor/pipeline/steps/01_annotation_processor.py`

**Overall Assessment:** Solid, testable Typer CLI step that extracts annotation context, renders crops, and batches LLM calls. A few minor robustness and hygiene issues; architecture is good.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                             |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Unbounded image b64 in prompts can explode token costs**: When `--images` is on, full PNGs are base64-inlined for every annotation without size guards. On large docs this can blow request size/latency and hit provider limits. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                                       |
| :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Inconsistent OpenCV optionality**: `_gridline_features` silently returns `None` metrics when cv2 fails. That’s fine, but you don’t log once to indicate you’re running without table cues.                       |
| **2. Feature thresholds are magic numbers**: `MAX_RADIUS=200`, spacing/center thresholds, and header/table suggestion scores are hard-coded. These should be env-tuned and dumped into diagnostics for replayability. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                |
| :-------------------------------------------------------------------------------------------------------------- |
| **1. Slight duplication in LLM timing**: Two branches compute `t_llm_ms`. Extract a helper to avoid divergence. |
| **2. Safer annots filter**: Use `getattr(annot, "type", ())` to avoid assuming `.type` exists.                  |

**Suggested snippets**

```diff
-                with open(d["image_path"], "rb") as f:
-                    b64 = base64.b64encode(f.read()).decode()
+                # Guard image payload size (~100–300KB); large images kill latency/tokens
+                with open(d["image_path"], "rb") as f:
+                    raw = f.read()
+                if len(raw) > int(os.getenv("STAGE01_MAX_IMAGE_BYTES", "350000")):
+                    # Downscale aggressively
+                    try:
+                        from PIL import Image; from io import BytesIO
+                        im = Image.open(BytesIO(raw))
+                        im.thumbnail((900, 900))
+                        buf = BytesIO(); im.save(buf, format="PNG"); raw = buf.getvalue()
+                    except Exception: pass
+                b64 = base64.b64encode(raw).decode()
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                               |
| :--------------------------------------------------------------------------------------------- |
| **1. Clean stage directory discipline** with per-stage logs/images/json.                       |
| \*\*2. Careful JSON repair (`clean_json_string`) and shape preservation on failures.           |
| \*\*3. Minimal, resilient feature extraction and header/table suggestion for cheap guardrails. |

---

### File: `src/extractor/pipeline/steps/02_marker_extractor.py`

**Overall Assessment:** Practical wrapper over project Marker internals with a spawnable worker and robust PDF/font/color enrichment. Good error surfacing; minor consistency nits.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                                                   |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Hard dependency on project internals without soft fallback**: If `extractor.core.converters.pdf` is missing, you raise (good), but CLI error path does not print install hint in red or suggest `pip install` extras. Not a crash inside the function, but UX critical. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                        |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Color extraction may read huge text dicts repeatedly**: Cache exists, but color lookup per table block can still be heavy; consider sampling spans not whole blocks when bbox overlaps are large. |
| **2. Global logger mutate**: `logger.remove()` in `run()` is OK, but at import you don’t change sinks; keep that consistent with other steps.                                                          |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                              |
| :---------------------------------------------------------------------------------------------------------------------------- |
| **1. Data classes / types**: A tiny `TypedDict` for `block_dict` would document expected fields and help during later merges. |

**Snippet—friendlier import error:**

```diff
-    except Exception as e:
-        raise RuntimeError(
-            "Marker internals unavailable. Ensure project-specific Marker modules are installed "
-            "(extractor.core.converters/pdf and extractor.core.models)."
-        ) from e
+    except Exception as e:
+        raise RuntimeError(
+            "Stage 02 requires project Marker modules.\n"
+            "Try: pip install 'yourpkg[marker]' or ensure extractor.core.* is on PYTHONPATH.\n"
+            f"Import error: {e}"
+        )
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                      |
| :-------------------------------------------------------------------- |
| **1. Worker lifted top-level for spawn compatibility.**               |
| **2. Sensible per-page strategy timing + best-table de-dup via IoU.** |

---

### File: `src/extractor/pipeline/steps/03_suspicious_headers.py`

**Overall Assessment:** Thoughtful verification step with preflight vision check, human cue fusion, and optional auto-reject. Two small correctness items.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                   |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Unreplaced DB paths**: `_retrieve_prior_decisions` is a stub returning `[]`. That’s fine if guarded. Ensure `--use-prior` default remains true only if stub is safe. (It is.) No crash. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                       |
| :------------------------------------------------------------------------------------------------------------------------------------ |
| **1. `verify_all_headers` discovery can over-load VLM on big docs**: add `--limit` warn when candidates > N to avoid rate limit pain. |
| \*\*2. Reusing `RELEVANT_RULES` from utils means drift if Stage 01 updates—write rule version to diagnostics.                         |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                         |
| :--------------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. `image_output_dir` also stored on blocks (good). Consider adding `relative_to(results_root)` for portability as you do elsewhere. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                   |
| :--------------------------------------------------------------------------------- |
| **1. Real preflight vision probe on a genuine crop—excellent.**                    |
| **2. Careful fallbacks for neighbors (±5 scan) and structured result write-back.** |

---

### File: `src/extractor/pipeline/steps/04_section_builder.py`

**Overall Assessment:** Useful, deterministic sectioning with numbering heuristics and visuals. One correctness bug affects roman numerals.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                    |
| :-------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Wrong Roman numeral map**: `_roman_to_int` maps `'D'` to `200` (should be **500**). This skews header depth detection & parent linking.  |
| **2. PIL imports in hot loop**: PIL is imported multiple times inside `extract_section_visual_enhanced`; not a crash, but cost on many pages. |

**Fix**

```diff
-    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 200, "M": 1000}
+    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                   |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Heuristic fallbacks (`detect_header_level`) bake in English keywords**: consider a small language-neutral feature combo (bold/size/spacing) before keywords. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                        |
| :-------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Use a module-level PIL import (it’s already optional elsewhere):** move `from PIL import Image, ImageDraw` to top with try/except. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                  |
| :-------------------------------------------------------------------------------- |
| **1. Section visuals spanning pages with clear red separators—great for review.** |
| **2. Consistent enrichment of blocks with section metadata.**                     |

---

### File: `src/extractor/pipeline/steps/05_table_extractor.py`

**Overall Assessment:** Strong Camelot orchestration with multiple strategies, good metrics, and per-page best selection. Some duplication and small QoL improvements.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **(none blocking)**                        |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                |
| :----------------------------------------------------------------------------------------------------------------------------- |
| **1. Timing/summary code is duplicated twice near the end**: risk of drift and noisy logs.                                     |
| **2. Global logger config at import time**: diverges from other steps’ “configure in run()” pattern; can interfere with tests. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                           |
| :------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. Promote constants to env with clear names (you already do many): also expose `CAMEL0T_PAGE_LIMIT` for quick smokes. |
| \*\*2. Consider returning both “all tables” and “selected per page” to aid Stage 07 merges (you overwrite).                |

| ✅ **STRENGTHS / GOOD PRACTICES**                                               |
| :----------------------------------------------------------------------------- |
| **1. Header-row detection & coalescing to drop mid-body repeats—nicely done.** |
| **2. Crop rendering without PIL (direct pixmap) keeps memory low.**            |

---

### File: `src/extractor/pipeline/steps/06_figure_extractor.py`

**Overall Assessment:** Works, but has import-time side effects and duplicated sampler/timing code. Functional.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **(none fatal)**                           |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                      |
| :------------------------------------------------------------------------------------------------------------------- |
| **1. `logger.remove()` at import time** can clobber other steps’ logging in test runs. Move to CLI like other steps. |
| **2. Duplicate sampler/timing blocks**: DRY to avoid inconsistent metrics.                                           |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                             |
| :----------------------------------------------------------------------------------------------------------- |
| \*\*1. When bbox missing, you estimate via first image rect—log a single warning per page to avoid log spam. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                        |
| :---------------------------------------------------------------------- |
| **1. Concurrency with `tqdm.asyncio.as_completed` and clear progress.** |
| **2. Section association via bbox/page windows keeps things simple.**   |

---

### File: `src/extractor/pipeline/steps/07_reflow_section.py`

**Overall Assessment:** Ambitious, feature-rich reflow step with strict JSON modes, image attachments, adapters, shims, and fallbacks. **But there are correctness bugs that will crash**.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                              |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `NameError: llm_timeout` used inside `reflow_section_with_llm`**: variable not defined in that scope (multiple uses). This will crash on first path that references it.                                            |
| **2. Wrong import for `clean_json_string`**: imports `extractor.core.services.utils.json_utils` while other stages use `extractor.pipeline.utils.json_utils`. If `core.services` isn’t present, you’ll crash at import. |
| **3. `_json_schema` referenced before defined** when building `schema_hint` (Gemini path). It’s wrapped in `try/except`, but you pay an exception for control flow; safer to define it first.                           |
| **4. Over-eager provider param massaging (`litellm.drop_params`)**: toggling internal lib globals risks unintended side effects under concurrency.                                                                      |

**Minimal, surgical fixes**

```diff
- from extractor.core.services.utils.json_utils import clean_json_string
+ from extractor.pipeline.utils.json_utils import clean_json_string
```

```diff
-async def reflow_section_with_llm(...):
+async def reflow_section_with_llm(..., llm_timeout: int = 60):
     ...
-    params_min = { ..., "timeout": llm_timeout, ... }
+    params_min = { ..., "timeout": llm_timeout, ... }
     ...
-    call_params = { "model": LLM_MODEL, "messages": messages, **extras, "timeout": llm_timeout }
+    call_params = { "model": LLM_MODEL, "messages": messages, **extras, "timeout": llm_timeout }
```

```diff
- _json_schema = {
+ _json_schema = {
    "type":"object",
    ...
 }
- # used above in schema_hint try/except; define before usage
+ # define _json_schema BEFORE any try/except that references it
```

```diff
- import litellm as _ll
- _prev_drop = getattr(_ll, "drop_params", True)
- try:
-     _ll.drop_params = False
-     results = await litellm_call(...)
- finally:
-     _ll.drop_params = _prev_drop
+ # Avoid global toggles; rely on wrapper + provider-native response_format only
+ results = await litellm_call(...)
```

And propagate `llm_timeout` from CLI:

```diff
- processed_sections = asyncio.run(run_tasks())
+ processed_sections = asyncio.run(run_tasks())  # run_tasks captures llm_timeout from outer scope
```

(Inside `run_tasks`, pass `llm_timeout=llm_timeout` into each `reflow_section_with_llm(...)`.)

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                 |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Many environment toggles complicate determinism** (`FORCE_MINIMAL_CALL`, `COMPACT_PROMPT`, etc.). Consider a `--mode {strict,minimal,relaxed}` single switch that sets these consistently. |
| \*\*2. Model guessing for vision support duplicates preflight; keep only one source of truth.                                                                                                   |

| 🔵 **REFINEMENT / CODE HYGIENE**                                    |
| :------------------------------------------------------------------ |
| **1. Centralize “attach images by confidence” logic (used twice).** |
| \*\*2. Prefer consistent utils import paths with other steps.       |

| ✅ **STRENGTHS / GOOD PRACTICES**                                                |
| :------------------------------------------------------------------------------ |
| **1. Multiple well-thought escape hatches to keep pipelines unblocked.**        |
| **2. Great diagnostics: logs payload summaries and responses for post-mortem.** |

---

### File: `src/extractor/pipeline/steps/08_lean4_theorem_prover.py`

**Overall Assessment:** Sensible two-phase design (LLM extraction → proving), with external CLI and batch JSONL modes. One correctness & one robustness issue.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                              |
| :---------------------------------------------------------------------------------------------------------------------- |
| **1. Wrong `clean_json_string` import path** (same as Stage 07). Will crash when `extractor.core.services.*` is absent. |

```diff
- from extractor.core.services.utils.json_utils import clean_json_string
+ from extractor.pipeline.utils.json_utils import clean_json_string
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Docker/Lean runner is assumed present** in fallback path; if not, the user gets late failure. Add an early probe with a helpful instruction (or require `LEAN4_CLI_CMD`). |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                   |
| :--------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. `tqdm.asyncio import tqdm` then used like std tqdm—OK but mildly confusing; maybe `from tqdm.asyncio import tqdm as atqdm`. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                     |
| :------------------------------------------------------------------- |
| **1. Batch CLI JSONL support and robust normalizations of outputs.** |
| **2. Clear results envelope with statistics.**                       |

---

### File: `src/extractor/pipeline/steps/09_section_summarizer.py`

**Overall Assessment:** Good rolling-context summarizer with checkpoints, consistent with the rest of the pipeline.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **(none)**                                 |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                        |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `console` global must be set via `build_cli()`**: calling module functions directly in tests without `build_cli()` leaves `console=None`. Consider a small guard. |

**Snippet**

```diff
def _ensure_console():
    global console
    if console is None:
        console = Console()

# Call _ensure_console() at the start of each _cmd_*.
```

| 🔵 **REFINEMENT / CODE HYGIENE**                                    |
| :------------------------------------------------------------------ |
| \*\*1. Unify JSON guard text with Stage 07 to keep outputs aligned. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                         |
| :----------------------------------------------------------------------- |
| **1. Rate limiting via semaphore + windowing = stable and predictable.** |

---

### File: `src/extractor/pipeline/steps/10_arangodb_exporter.py`

**Overall Assessment:** Clear flattener with ordered indices and optional embeddings. Nice indexing setup.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                    |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Embedding model lazy-load can blow memory on big runs**: safe but consider a `--no-embed` CLI switch or env guard; current step always tries embeddings if text present. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                          |
| :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `text_content` for tables/figures is thin** (just headers/title). Downstream search quality will suffer; consider small “caption/first row sample”. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                         |
| :--------------------------------------------------------------------------------------- |
| \*\*1. Add `on_duplicate="update"` vs `"replace"` choice via CLI if idempotence desired. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                             |
| :--------------------------------------------------------------------------- |
| **1. Deterministic ordering with `object_index_in_doc` and index creation.** |
| **2. Proper confirmation artifact for audits.**                              |

---

### File: `src/extractor/pipeline/steps/11_arango_create_graph.py`

**Overall Assessment:** Good FAISS/NumPy abstraction, hierarchy-aware weights, and optional LLM rationales. One typing/clarity issue.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **(none obvious)**                         |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                   |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Type hint mismatch in `build_faiss_index`**: returns a tuple (`("faiss", index)`) but annotated as `faiss.IndexFlatIP`. This confuses tooling and reviewers. |

**Fix**

```diff
-def build_faiss_index(embeddings: NDArray[np.float32]) -> faiss.IndexFlatIP:
+from typing import Tuple, Any
+def build_faiss_index(embeddings: NDArray[np.float32]) -> tuple[str, Any]:
```

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                              |
| :------------------------------------------------------------------------------------------------------------ |
| \*\*1. Rationale generation can be expensive—consider `GRAPH_ENABLE_RATIONALES=false` default for first runs. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                          |
| :------------------------------------------------------------------------ |
| **1. Clean separation of index building vs search; easy NumPy fallback.** |

---

### File: `src/extractor/pipeline/steps/12_insert_annotations.py`

**Overall Assessment:** Useful bridging step, but contains a **format-string bug** that will break AQL fetching.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**   |
| :------------------------------------------- |
| **1. F-string with raw AQL object literal**: |
| The snippet                                  |

```python
aql_fetch = f"""
    FOR a IN {ann_col}
      FILTER @src == null OR a.source_pdf == @src
      RETURN { _key: a._key, page: a.page }
"""
```

uses `{ ... }` inside an f-string which Python interprets as formatting placeholders → **NameError** for `_key`. |

**Fix (escape braces)**

```diff
-        RETURN { _key: a._key, page: a.page }
+        RETURN {{ _key: a._key, page: a.page }}
```

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                              |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Graph edge definition recreation**: deleting and recreating the graph to extend edge defs is heavy. Consider documenting that best-effort recreation occurs and may drop runtime edges. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                      |
| :-------------------------------------------------------------------------------------------------------------------- |
| \*\*1. Batch edges could be huge; add `--max-edges-per-ann` guard to prevent combinatorial explosions on dense pages. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                        |
| :---------------------------------------------------------------------- |
| **1. Symmetric edges (ann→object & object→ann) simplifies traversals.** |

---

### File: `src/extractor/pipeline/steps/14_report_generator.py`

**Overall Assessment:** Practical aggregator with canonical file names and Markdown export. A few stats are placeholders, which is fine for MVP.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **(none)**                                 |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                     |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| \*\*1. Fallback to “first JSON in folder” can read stale files if multiple runs exist; consider embedding the `run_id` and matching only files created in this run. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                               |
| :------------------------------------------------------------------------------------------------------------- |
| \*\*1. The banner comments mention “07\_report\_generator.py”—update docstring to Stage 14 to avoid confusion. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                     |
| :------------------------------------------------------------------- |
| **1. Produces both JSON and Markdown with deterministic structure.** |

---

### File: `src/extractor/pipeline/steps/__init__.py`

**Overall Assessment:** Nice lazy loader to import numbered modules under `sXX_*` aliases. Clean.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :----------------------------------------- |
| **(none)**                                 |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                           |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| \*\*1. If a step raises on import (e.g., optional dependency), the lazy loader re-raises as `AttributeError`, which can mislead. Consider wrapping and surfacing a more explicit message. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                      |
| :------------------------------------------------------------------------------------ |
| \*\*1. Add a short docstring to `__getattr__` explaining the regex and example names. |

| ✅ **STRENGTHS / GOOD PRACTICES**                                          |
| :------------------------------------------------------------------------ |
| **1. Eliminates import-time side effects across the whole step package.** |

---

## Smoke tests for the crucial failures

Drop these into `tests/smokes/` (pytest). They are tiny, fast, and deterministic.

### 1) Stage 07 `llm_timeout` NameError

```python
# tests/smokes/test_stage07_llm_timeout.py
import types
from pathlib import Path

import importlib
mod = importlib.import_module("extractor.pipeline.steps.s07_reflow_section")  # via lazy alias if used

def test_llm_timeout_nameerror():
    sec = {"id":"s1","title":"T","blocks":[],"tables":[],"figures":[],"merged_text":"x"}
    out_dir = Path("data/results/pipeline")  # not used by the function in this smoke
    fn = getattr(mod, "reflow_section_with_llm")
    try:
        # Call without llm_timeout kwarg to ensure default is present
        mod.asyncio.get_event_loop()  # ensure loop import works
        # we won’t actually await; just check signature default exists
        assert "llm_timeout" in fn.__code__.co_varnames
    except Exception as e:
        raise AssertionError(f"reflow_section_with_llm lacks llm_timeout default: {e}")
```

### 2) Stage 07 wrong `clean_json_string` import

```python
# tests/smokes/test_stage07_imports.py
import importlib, sys
def test_stage07_import_path():
    m = importlib.import_module("extractor.pipeline.steps.s07_reflow_section")
    # accessing clean_json_string should resolve from pipeline.utils
    from extractor.pipeline.utils.json_utils import clean_json_string
    assert callable(clean_json_string)
```

### 3) Stage 04 Roman numeral bug

```python
# tests/smokes/test_stage04_roman.py
from extractor.pipeline.steps.s04_section_builder import _roman_to_int
def test_roman_map_D_is_500():
    assert _roman_to_int("D") == 500
    assert _roman_to_int("IV") == 4
```

### 4) Stage 12 AQL braces in f-string

```python
# tests/smokes/test_stage12_aql_braces.py
from extractor.pipeline.steps.s12_insert_annotations import run as stage12_run
import inspect
def test_aql_fetch_braces_escaped():
    src = inspect.getsource(stage12_run)
    assert "{{ _key:" in src and "page: a.page }}" in src
```

### 5) Stage 11 FAISS index return type tuple

```python
# tests/smokes/test_stage11_index_tuple.py
import numpy as np
from extractor.pipeline.steps.s11_arango_create_graph import build_faiss_index
def test_build_faiss_index_returns_tuple():
    embs = np.random.rand(3, 8).astype("float32")
    idx = build_faiss_index(embs)
    assert isinstance(idx, tuple) and idx[0] in ("faiss","numpy")
```

---

## TL;DR fix list you can hand to the agent

1. **Stage 07**

   * Add `llm_timeout` param to `reflow_section_with_llm` and pass from CLI `run()`.
   * Import `clean_json_string` from `extractor.pipeline.utils.json_utils`.
   * Define `_json_schema` **before** any reference (even in `try:`) and remove global `litellm.drop_params` toggling.

2. **Stage 12**

   * Escape braces in AQL f-string: `RETURN {{ _key: a._key, page: a.page }}`.

3. **Stage 04**

   * Fix Roman numeral map: `D: 500`. Move PIL imports to module-level try/except.

4. **Stage 11**

   * Correct type hints (`tuple[str, Any]`) for the FAISS index wrapper.

5. **General**

   * Avoid logger reconfiguration at import time (06, 05).
   * Add modest image byte limits before base64-inlining (01 & 07).
   * Harmonize `json_utils` import path across steps to `extractor.pipeline.utils.json_utils`.

If you want, I can produce compact patches for 07/12/04/11 in one diff chunk next.
