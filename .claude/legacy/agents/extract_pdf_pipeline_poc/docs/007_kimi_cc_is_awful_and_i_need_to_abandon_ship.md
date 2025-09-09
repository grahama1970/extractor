---
### File: `src/extractor/pipeline/poc/poc_01_extract_annotations.py`

**Overall Assessment:**  
A production-grade **single-file prototype** that ambitiously mixes PDF parsing, batch LLM prompting, schema validation, vector search, graph persistence, and clustering.  While it **adds many safety nets** (Pydantic, Tenacity, atomic writes, env-vars), it still **opens the same PDF multiple times**, **ignores missing optional deps silently**, and **hard-codes end-user paths**—all of which will break in a container or CI environment.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |
| :--- |
| **1. Missing-dependency failures:**<br>`arango`, `sentence-transformers`, `faiss`, `sklearn`, `loguru`, `tenacity`, `pydantic` are **imported without graceful fallback**.  In a minimal container these will raise `ModuleNotFoundError` and crash the script before `main()` even starts. |
| **2. Still opens the PDF twice:**<br>`extract_annotations_enhanced` and `capture_annotation_screenshot` accept an optional `pdf_doc` parameter, but the **main flow ignores it**, causing the PDF to be opened once for extraction and again for every screenshot—exhausting FDs on large files. |
| **3. `ENABLE_ARANGO="false"` only disables insertion, not imports:**<br>Even when the feature flag is off, **all Arango-related modules are imported at top-level**; if the packages are missing the script cannot be imported at all (e.g., in unit tests). |
| **4. `client.db(...)` without auth fallback:**<br>If `ARANGO_USER`/`ARANGO_PASSWORD` env vars are absent or incorrect, the connection raises `ArangoError` and the **entire run aborts** instead of gracefully skipping the DB step. |
| **5. Hard-coded fallback PDF path:**<br>`sys.argv[1] or "/home/graham/.../BHT_CV32A65X_marked.pdf"` is **user-specific** and guaranteed to be absent in any other workstation or Docker image. |

| 🟡 **MEDIUM / WILL BITE LATER** |
| :--- |
| **1. Faiss index kept in global mutable variable:**<br>`faiss_index = None` is shared across multiple PDF runs; concurrent executions (e.g., in a web service) will **overwrite each other’s index** and return stale nearest-neighbor results. |
| **2. Prompt token bloat still possible:**<br>Although `MAX_TEXT_SPANS` is configurable, the prompt still concatenates styling metadata inline; a single very large annotation can still exceed Claude’s context window. |
| **3. Non-configurable clustering algorithm:**<br>DBSCAN parameters (`eps`, `min_samples`) are hard-coded in `Config`; switching to HDBSCAN or K-Means requires code change. |
| **4. `ensure_arango_collections` uses overwrite=True:**<br>Repeated runs will **delete existing data** if the schema changes, making incremental updates impossible. |
| **5. Screenshot zoom is global:**<br>`SCREENSHOT_ZOOM` is a single float for all pages; different page sizes or DPIs will yield inconsistent image resolutions. |

| 🔵 **REFINEMENT / CODE HYGIENE** |
| :--- |
| **1. Replace top-level Arango imports with lazy loading:**<br>```diff
- from arango import ArangoClient
+ def _lazy_import(name):
+     import importlib
+     return importlib.import_module(name)
``` |
| **2. Move `main()` PDF path to env var with validation:**<br>```diff
- pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/home/graham/..."
+ pdf_path = os.getenv("PDF_PATH") or (sys.argv[1] if len(sys.argv) > 1 else None)
+ if not pdf_path:
+     raise ValueError("PDF_PATH env var or CLI argument required")
``` |
| **3. Open the PDF once and share the handle for both extraction and screenshots:**<br>```diff
- annotations = extract_annotations_enhanced(pdf_path, pdf_doc)
- screenshot = capture_annotation_screenshot(pdf_path, annot, output_dir, pdf_doc)
+ # Already done via pdf_doc parameter - just ensure main() passes it consistently
``` |
| **4. Atomic PNG writes (mirror JSON fix):**<br>```diff
- pix.save(str(img_path))
+ tmp_img = img_path.with_suffix('.tmp.png')
+ pix.save(str(tmp_img))
+ tmp_img.replace(img_path)
``` |
| **5. Use `logger.exception` instead of bare `logger.error` in exception handlers:**<br>```diff
- logger.error(f"Failed to insert annotation ...: {e}")
+ logger.exception(f"Failed to insert annotation {annot['id']}")
``` |

| ✅ **STRENGTHS / GOOD PRACTICES** |
| :--- |
| **1. Pydantic schema for LLM outputs:**<br>`AnalysisResult` enforces field types and ranges, preventing downstream deserialization bugs. |
| **2. Tenacity retry with exponential back-off:**<br>`@retry` around `call_claude` provides resilience to transient network or rate-limit errors. |
| **3. Atomic file writes:**<br>`.tmp` → `.replace()` pattern eliminates JSON and PNG corruption on interruption. |
| **4. Config class with env-var overrides:**<br>`Config.*` variables allow runtime tuning without code changes. |
| **5. Comprehensive logging:**<br>`loguru` provides structured, level-filtered logs that integrate well with container orchestrators.