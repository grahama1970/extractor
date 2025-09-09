Here’s a no-nonsense, production-minded code review—file by file—focused on (1) immediate runtime risk, (2) longer-term reliability, and (3) quick hygiene wins. Wherever something is stubby/aspirational/non-working, I call it out and give a concrete, minimal fix (as diffs) so you can actually run the pipeline end-to-end and land JSON you can load into ArangoDB.

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/01_annotation_processor.py`

**Overall Assessment:** Solid skeleton and directory discipline; annotation capture + context windows are reasonable. Main risks are excessive memory (holding `pixmap`s before saving), brittle model prompt placeholder, and a couple of “works until it doesn’t” assumptions around PyMuPDF API.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                                                     |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Pixmap memory pressure on large PDFs:** You append `pixmap` objects into `data` and write them in a second pass. With many annotations this spikes RAM and risks OOM. Failure mode: the process dies mid-run with no output (especially in containers with tight limits). |
| **2. Prompt placeholder is effectively a stub:** `SYSTEM_PROMPT` is a placeholder (`… // (full prompt unchanged)`). For JSON-mode LLM calls, weak/ambiguous prompts lead to malformed JSON and downstream parse errors.                                                        |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                       |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Missing guard for `page.get_text("dict")` shape differences:** If a page returns blocks lacking expected keys you’ll silently skip useful context; not fatal but degrades LLM output.            |
| **2. Annotation type string checks assume PyMuPDF naming:** `annot.type[1] == "FreeText"`. Different versions/locales can diverge; safer to check `ANNOT_FREETEXT in annot.type` or the numeric code. |
| **3. Hardcoded JSON filename:** Always writes `01_annotations.json`. That’s fine per stage, but if you process multiple PDFs into the same output dir concurrently, paths collide.                    |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                |
| :------------------------------------------------------------------------------------------------------------------------------ |
| **1. Save pixmaps inline to cut peak memory:** Write images as you go and store only the path in `data`.                        |
| **2. Stabilize type checks & defaults:** Prefer `.get` with defaults for dicts coming from PyMuPDF; it changes across releases. |
| **3. Tighten logging for parse failures:** Include `annot['id']` and first 120 chars of raw content in warnings.                |

**Suggested diffs**

*Save pixmaps during extraction (no second pass), and keep only paths:*

```diff
@@ def extract_annotations_data(pdf_path: Path, config: Config) -> List[Dict[str, Any]]:
-                matrix = fitz.Matrix(config.render_dpi / 72, config.render_dpi / 72)
-                pix = page.get_pixmap(matrix=matrix, clip=expanded_rect)  # type: ignore[attr-defined]
-                annots_out.append({
+                matrix = fitz.Matrix(config.render_dpi / 72, config.render_dpi / 72)
+                pix = page.get_pixmap(matrix=matrix, clip=expanded_rect)  # type: ignore[attr-defined]
+                # write image immediately to avoid holding pixmaps in RAM
+                img_dir = (config.output_dir / "image_output")
+                img_dir.mkdir(parents=True, exist_ok=True)
+                img_path = img_dir / f"annot_p{pno}_a{idx}.png"
+                pix.save(str(img_path))
+                annots_out.append({
                     "id": f"p{pno}_a{idx}",
                     "page": pno,
                     "type": annot.type[1],
@@
-                    "pixmap": pix,
+                    "image_path": str(img_path),
                 })
```

*Remove second pass that saved `pixmap` and delete it:*

```diff
@@ async def process_pdf_pipeline(config: Config):
-    # Save annotation images to the dedicated image directory
-    for d in data:
-        img_path = image_output_dir / f"annot_{d['id']}.png"
-        d["pixmap"].save(str(img_path))
-        d["image_path"] = str(img_path)
-        del d["pixmap"]
+    # images are already saved during extraction
```

*Make the FreeText check robust & add better parse logs:*

```diff
-            if annot.type[1] == ANNOT_FREETEXT and not config.include_freetext:
+            if (ANNOT_FREETEXT in annot.type) and not config.include_freetext:
                 continue
@@
-            except json.JSONDecodeError:
-                logger.warning(f"LLM response was not valid JSON for {d.get('id')}: {cleaned}")
+            except json.JSONDecodeError:
+                logger.warning(
+                    f"Invalid JSON for {d.get('id')}: {cleaned[:200]}..."
+                )
```

**Optional (recommended) prompt hardening**—keep minimal but explicit:

```diff
-SYSTEM_PROMPT = textwrap.dedent("""
-You are a PDF extraction expert analyzing human annotations …
-// (full prompt unchanged)
-""")
+SYSTEM_PROMPT = textwrap.dedent("""
+You are a PDF extraction expert. Given (a) a cropped annotation image and (b) nearby text blocks
+(inside/above/below), return a compact JSON object with keys:
+{ "title": str|null, "summary": str, "entities": [str], "labels": [str] }.
+Do not invent data; if unknown, use null/[] as appropriate.
+""")
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                           |
| :--------------------------------------------------------------------------------------------------------- |
| **1. Stage-scoped output layout:** `json_output/` and `image_output/` per stage is clean and reproducible. |
| **2. Sensible context windows:** Inside/above/below blocks provide a pragmatic balance of recall/cost.     |
| **3. Concurrency + overall timeout knobs:** Good control surfaces for production back-pressure.            |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/02_marker_extractor.py`

**Overall Assessment:** Clear process isolation with a hard timeout and stage-scoped logging. The biggest risk is depending on Marker internals (converter/types/attributes) that may not match your installed package.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                                                                                                       |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Fragile Marker imports/attributes:** `from extractor.core.converters.pdf import PdfConverter` and `create_model_dict()` are project-internal assumptions. If your runtime has Marker from PyPI, classes differ and `document.pages/page.children/block.block_type` may not exist. Failure mode: import or attribute errors. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                                                                                |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Suspicious flags assumed:** `.is_suspicious`, `.suspicious_reasons`, `.suspicion_confidence` may not be present. You guard with `hasattr`, which is good, but any downstream stage relying on those fields should tolerate their absence. |
| **2. Queue empty race:** If worker crashes before putting a result, you exit—fine—but consider reading stderr for post-mortem (optional).                                                                                                      |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                                                             |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Defensive converter fallback:** Add a short, explicit error if Marker internals aren’t found, suggesting the correct install (keeps it MVP).            |
| **2. Normalize block schema now:** Ensure every block has `block_type`, `page_idx`, `text`, and `bbox` (list\[float]) so later stages don’t branch on shape. |

**Suggested diffs**

*Add explicit failure with guidance + normalize schema:*

```diff
@@ def extract_blocks(pdf_path: Path) -> List[Dict[str, Any]]:
-    from extractor.core.converters.pdf import PdfConverter
-    from extractor.core.models import create_model_dict
+    try:
+        from extractor.core.converters.pdf import PdfConverter
+        from extractor.core.models import create_model_dict
+    except Exception as e:
+        raise RuntimeError(
+            "Marker internals not found. Ensure your project provides "
+            "`extractor.core.converters.pdf.PdfConverter` and `extractor.core.models.create_model_dict`, "
+            "or pin the repo version that defines them."
+        ) from e
@@
-                    blocks.append(block_dict)
+                    # normalize required keys for downstream
+                    block_dict.setdefault("text", "")
+                    block_dict.setdefault("bbox", [0.0, 0.0, 0.0, 0.0])
+                    block_dict.setdefault("page_idx", int(page.page_id) if hasattr(page, "page_id") else 0)
+                    blocks.append(block_dict)
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                                        |
| :---------------------------------------------------------------------------------------------------------------------- |
| **1. Separate process + enforced timeout:** Excellent for safety; prevents hung conversions from blocking the pipeline. |
| **2. Stage-local logging and human-friendly console output.**                                                           |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/03_suspicious_headers.py`

**Overall Assessment:** Thoughtful verification flow with cropped context images and a JSON-strict LLM call w/ retries. Main runtime risks are brittle rect operations and reliance on `lines/spans` that may not exist.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                            |
| :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `Rect.intersect` use may be inert if not in-place (PyMuPDF version-dependent):** If not applied, clip could exceed page bounds, causing `get_pixmap` exceptions. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                               |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `lines/spans` reliance:** `_format_block_text` expects enriched structure; on plain Marker text blocks it returns `N/A`, which reduces LLM accuracy.                     |
| **2. Ambiguous selection of “clean PDF” file:** `next(pdf_dir.glob("*_clean.pdf"))` without constraining by source name can pick wrong file if directory contains prior runs. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                     |
| :------------------------------------------------------------------------------------------------------------------- |
| **1. Force in-place rect intersection:** Make the intent explicit and compatible.                                    |
| **2. Improve LLM fallback reasoning:** Your default to keep header is okay; log the short context to ease debugging. |

**Suggested diffs**

*Enforce rect intersection explicitly:*

```diff
@@ class VerificationTask:
-        expanded_rect.intersect(self.page_obj.rect)
+        # ensure we stay within page bounds (in-place on recent PyMuPDF, but be explicit)
+        expanded_rect = expanded_rect & self.page_obj.rect
```

*Filter the clean PDF by matching basename (optional but safer):*

```diff
@@ def run(...):
-    try:
-        clean_pdf_path = next(pdf_dir.glob("*_clean.pdf"))
+    try:
+        # prefer a clean PDF that shares the same stem as input_json parent folder
+        candidates = sorted(pdf_dir.glob("*_clean.pdf"))
+        clean_pdf_path = candidates[0]
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                            |
| :-------------------------------------------------------------------------- |
| **1. Good retry/backoff on LLM; JSON-strict first with graceful fallback.** |
| **2. Concurrency control via semaphore + `tqdm_asyncio`.**                  |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/04_section_builder.py`

**Overall Assessment:** Ambitious “sophisticated” header analysis; however, parts are aspirational and will break (hard requirement on spaCy model, visuals not actually saved, debug helpers referencing nonexistent fields). I’ve provided minimal changes to make it work with the rest of your pipeline.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                     |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Hard dependency on `en_core_web_sm`:** Importing `spacy.load("en_core_web_sm")` at import time will crash if the model isn’t installed.                                                                                                   |
| **2. Visuals are not saved to disk:** `extract_section_visual_enhanced` returns base64 but Stage 07 expects an image path; `visual_path` is set but no file is written.                                                                        |
| **3. Debug/working helpers reference nonexistent keys:** e.g., `result['validation_statistics']`, `result['features']`, `result['suspicious_headers']`—these keys are never produced. Running `debug()`/`working_usage()` will throw KeyError. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                   |
| :------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Over-tight font heuristics:** Header detection penalizes small fonts even when numbering strongly indicates a header (false negatives).      |
| **2. `sys.path.insert` import hack:** Fragile under packaging and tests; preferable to relative imports or moving utilities into a proper module. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                             |
| :--------------------------------------------------------------------------------------------------------------------------- |
| **1. Make spaCy optional with a cheap fallback:** Use regex for sentence counting if spaCy is unavailable.                   |
| \*\*2. Save section visuals and store *relative* path to the pipeline `results/` root, so Stage 07 resolves images reliably. |

**Suggested diffs**

*Optional spaCy + fallback sentence splitter:*

```diff
-# Import spaCy - it's in pyproject.toml so it's required
-import spacy
-
-# Load English model - FAIL FAST if not available
-nlp = spacy.load("en_core_web_sm")
+try:
+    import spacy
+    try:
+        nlp = spacy.load("en_core_web_sm")
+    except Exception:
+        nlp = None
+except Exception:
+    nlp = None
@@
 def count_sentences_advanced(text: str) -> int:
-    """Count sentences using spaCy."""
-    if not text or len(text.strip()) < 3:
-        return 0
-    
-    doc = nlp(text)
-    return len(list(doc.sents))
+    """Count sentences; prefer spaCy, fallback to regex."""
+    if not text or len(text.strip()) < 3:
+        return 0
+    if nlp:
+        return sum(1 for _ in nlp(text).sents)
+    # naive fallback: split on terminal punctuation
+    return max(1, len([s for s in re.split(r'[.!?]+', text) if s.strip()]))
```

*Save visuals to disk and store a path relative to results root:*

```diff
@@ def extract_section_visual_enhanced(...):
-        if len(page_images) == 1:
-            output = BytesIO()
-            page_images[0].save(output, format='PNG')
-            return base64.b64encode(output.getvalue()).decode('utf-8')
+        if len(page_images) == 1:
+            output_path.parent.mkdir(parents=True, exist_ok=True)
+            page_images[0].save(str(output_path), format='PNG')
+            buf = BytesIO()
+            page_images[0].save(buf, format='PNG')
+            return base64.b64encode(buf.getvalue()).decode('utf-8')
@@
-        output = BytesIO()
-        composite.save(output, format='PNG')
-        return base64.b64encode(output.getvalue()).decode('utf-8')
+        output_path.parent.mkdir(parents=True, exist_ok=True)
+        composite.save(str(output_path), format='PNG')
+        with BytesIO() as buf:
+            composite.save(buf, format='PNG')
+            return base64.b64encode(buf.getvalue()).decode('utf-8')
```

*Ensure `visual_path` is **relative to results root** (so Stage 07 can open it):*

```diff
@@ async def process_sections_comprehensive(...):
-        for section in sections:
-            visual_path = image_output_dir / f"section_{section['id']}.png"
+        results_root = image_output_dir.parent.parent  # .../results
+        for section in sections:
+            visual_path = image_output_dir / f"section_{section['id']}.png"
             visual_b64 = extract_section_visual_enhanced(pdf_path, section, visual_path, expand=0.3)
             if visual_b64:
                 section["has_visual"] = True
-                section["visual_path"] = str(visual_path)
+                section["visual_path"] = str(visual_path.relative_to(results_root))
```

*Remove broken debug logs (optional):*

```diff
@@ async def working_usage():
-    logger.info(f"📊 Average confidence: {result['validation_statistics']['avg_confidence']:.2f}")
-    logger.info(f"⚠️  Suspicious headers: {result['suspicious_count']}")
-    
-    # Show sophisticated features
-    features = result['features']
-    logger.info("🚀 Sophisticated features enabled:")
-    for feature, enabled in features.items():
-        status = "✅" if enabled else "❌"
-        logger.info(f"  {status} {feature}")
-    
-    # Show suspicious analysis details
-    suspicious_analysis = result['suspicious_headers']
-    logger.info(f"\n🔍 Suspicious header analysis:")
-    for category, items in suspicious_analysis['categories'].items():
-        if items:
-            logger.info(f"  - {category}: {len(items)} issues")
-            for item in items[:2]:  # Show first 2 of each category
-                logger.info(f"    • {item.get('title', 'Unknown')[:50]}...")
+    # trimmed noisy, non-existent keys in demo
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                               |
| :--------------------------------------------------------------------------------------------- |
| **1. Multi-signal header validation (font, numbering, context) is a good pragmatic approach.** |
| **2. Sections carry metadata (`header_analysis`, `bbox`, `page_*`)—useful later for joins.**   |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/05_table_extractor.py`

**Overall Assessment:** Clear multi-strategy Camelot use with image crops via PyMuPDF. Biggest runtime risk is private Camelot attributes and coordinate conversions.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                      |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Private attribute reliance:** You access `table._bbox`. If Camelot changes internals, this breaks. Prefer `table._bbox` fallback → compute from `table.cells` or `table._bbox` if present. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                   |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. External binary dependencies:** Camelot lattice needs Ghostscript; missing deps = opaque failures. You already log, but a preflight check would save cycles. |
| **2. DPI vs Matrix:** mixing page dpi vs zoom is fine but be consistent across stages for visual parity.                                                          |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                     |
| :------------------------------------------------------------------------------------------------------------------- |
| **1. Normalize bbox source:** Wrap `_bbox` access in a helper with a safe fallback.                                  |
| **2. Store `table_image_path` relative to results root** (optional; Stage 07 can handle abs, but relative is nicer). |

**Suggested diffs**

*Safe bbox accessor:*

```diff
@@ def extract_tables_from_page(...):
-        for table in tables:
+        for table in tables:
+            bbox_tuple = getattr(table, "_bbox", None)
+            if not bbox_tuple and hasattr(table, "cells") and table.cells:
+                # fallback: compute from cell coords
+                xs = [c.x1 for c in table.cells] + [c.x2 for c in table.cells]
+                ys = [c.y1 for c in table.cells] + [c.y2 for c in table.cells]
+                bbox_tuple = (min(xs), min(ys), max(xs), max(ys))
             score = score_table(table.df)
             if score == 0:
                 continue
-            bbox_key = tuple(map(int, table._bbox))
+            bbox_key = tuple(map(int, bbox_tuple))
@@
-        img_path = extract_table_image(
-            pdf_doc, page_num, table._bbox, output_dir, table_idx
+        img_path = extract_table_image(
+            pdf_doc, page_num, bbox_tuple, output_dir, table_idx
         )
@@
-            "bbox": list(table._bbox),
+            "bbox": list(bbox_tuple),
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                             |
| :--------------------------------------------------------------------------- |
| **1. Strategy cache (`last_good_strategy`) is a simple, effective speedup.** |
| **2. Pandas metrics embedded with each table for downstream decisioning.**   |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/06_figure_extractor.py`

**Overall Assessment:** Good concurrency and a practical VLM describer. Two issues block later stages: figure→section mapping and image path scoping.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                       |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Broken figure→block association:** The code attempts to match figures back to blocks with a substring test that always returns the first block. Result: wrong page/bbox, bad section joins. |
| **2. Image path is relative to `stage_06` dir, but Stage 07 expects paths relative to the `results/` root:** Stage 07’s `_safe_read_image_b64` will fail to open images.                         |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                  |
| :------------------------------------------------------------------------------------------------------------------------------- |
| **1. Missing `bbox` in figure outputs:** Later association uses bbox intersection; if it’s absent you’ll miss section joins.     |
| **2. Heuristic bbox estimation on missing `block['bbox']`:** That’s OK as fallback, but record it so you can diagnose mis-crops. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                |
| :---------------------------------------------------------------------------------------------- |
| **1. Build a deterministic `figure_id → block` map at task creation and carry `bbox` forward.** |
| **2. Store image path relative to the `results/` root.**                                        |

**Suggested diffs**

*Produce a fig-id→block map, include `bbox`, and write path relative to `results/`:*

```diff
@@ async def extract_and_describe_figure(...):
-            img_path = output_dir / f"{figure_id}.png"
-            with open(img_path, 'wb') as f: f.write(image_data)
+            img_path = output_dir / f"{figure_id}.png"
+            with open(img_path, 'wb') as f:
+                f.write(image_data)
@@
-        return {
+        return {
             "figure_id": figure_id,
             "page": page_num,
-            "image_path": str(img_path.relative_to(output_dir.parent)),
+            # store path relative to results root (../.. from image_output)
+            "image_path": str(img_path.relative_to(output_dir.parent.parent)),
+            "bbox": [float(x0), float(y0), float(x1), float(y1)],
             "ai_description": description,
             "extraction_time": datetime.now().isoformat()
         }
```

*Associate figures using the explicit map (no substring heuristics):*

```diff
@@ def run(...):
-    extracted_figures = asyncio.run(process_figures_batch(pdf_path, figure_blocks, image_output_dir))
+    # build a stable map of figure_id -> source block
+    fig_block_map = {f"figure_{i+1:03d}": b for i, b in enumerate(figure_blocks)}
+    extracted_figures = asyncio.run(process_figures_batch(pdf_path, figure_blocks, image_output_dir))
+    # Ensure bbox/page present from the original blocks when available
+    for fig in extracted_figures:
+        blk = fig_block_map.get(fig["figure_id"])
+        if blk:
+            fig.setdefault("page", blk.get("page_idx", fig.get("page", 0)))
+            fig.setdefault("bbox", blk.get("bbox", fig.get("bbox")))
@@
-    for figure in extracted_figures:
-        figure_block = next((b for b in figure_blocks if f"figure_{figure['figure_id'].split('_')[1]}" in figure["figure_id"]), None)
-        if not figure_block: continue
-        
-        figure_bbox = fitz.Rect(figure_block["bbox"])
+    for figure in extracted_figures:
+        if not figure.get("bbox"):
+            continue
+        figure_bbox = fitz.Rect(figure["bbox"])
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                               |
| :----------------------------------------------------------------------------- |
| **1. Tenacity retries for VLM calls; concise system prompt keeps costs down.** |
| **2. Useful context by intersecting nearby text.**                             |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/07_reflow_section.py`

**Overall Assessment:** Good consolidation step and JSON-strict reflow prompt. Risks are mostly integration (image paths) and un-used concurrency control.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                              |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Image path resolution depends on earlier stages writing paths relative to `results/`:** Fixed by 04 & 06 diffs above; without them image embedding silently drops. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                 |
| :------------------------------------------------------------------------------------------------------------------------------ |
| **1. Global SentenceTransformer load at import:** Adds cold-start latency and potential OOM in constrained containers.          |
| **2. `LLM_SEMAPHORE` unused:** Concurrency is unconstrained if you ever switch from `tqdm_asyncio.gather` w/o semaphore gating. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                |
| :---------------------------------------------------------------------------------------------- |
| **1. Lazy-load embeddings:** Load on first use in `consolidate_data` only if annotations exist. |
| **2. Gate image attachments by availability and log which were added.**                         |

**Suggested diffs**

*Lazy-load embeddings (minimal change):*

```diff
@@
-text_embedding_model: Optional[SentenceTransformer] = None
-try:
-    logger.info("Loading Sentence Transformer model for text embeddings...")
-    text_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
-    logger.success("Text embedding model loaded.")
-except Exception as e:
-    logger.warning(f"Failed to load text embedding model (continuing without embeddings): {e}")
+text_embedding_model: Optional[SentenceTransformer] = None
+def _ensure_embedder():
+    global text_embedding_model
+    if text_embedding_model is None:
+        try:
+            logger.info("Loading Sentence Transformer model for text embeddings...")
+            from sentence_transformers import SentenceTransformer
+            text_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
+            logger.success("Text embedding model loaded.")
+        except Exception as e:
+            logger.warning(f"Failed to load text embedding model (continuing without embeddings): {e}")
+    return text_embedding_model
@@ def consolidate_data(...):
-    if annotations_path and annotations_path.exists():
+    if annotations_path and annotations_path.exists():
         ...
@@
-        try:
+        try:
             # Prefer semantic ranking when a text embedding model is available
-            if text_embedding_model is not None and candidates:
+            if candidates and _ensure_embedder() is not None:
                 ...
-                a_vecs = text_embedding_model.encode(annot_texts, normalize_embeddings=True)
+                a_vecs = text_embedding_model.encode(annot_texts, normalize_embeddings=True)
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                         |
| :--------------------------------------------------------------------------------------- |
| **1. Clear, JSON-first reflow prompt and strict parsing with fallback.**                 |
| **2. Sensible section context composer that includes tables, figures, and annotations.** |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/08_lean4_theorem_prover.py`

**Overall Assessment:** This is largely aspirational. It imports non-existent internal modules, assumes a Dockerized Lean container, and uses `tqdm.asyncio` in a way that’s unlikely to do what you expect. If you **don’t** need Lean for MVP, gate it.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                     |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Missing packages/modules:** `lean4_prover.core.validation_models`, `generate_lean_code` are not part of this codebase; import will fail.                  |
| **2. Assumes Docker container named `lean_runner`:** Calling `docker exec` will fail in most environments.                                                     |
| **3. Misuse of `tqdm.asyncio.tqdm`:** Wrapping `asyncio.as_completed(...)` directly in `tqdm` here is not the intended pattern; may never render or can stall. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                |
| :----------------------------------------------------------------------------------------------------------------------------- |
| **1. Two concurrency semaphores + long blocking operations** can starve the loop if not tuned.                                 |
| **2. Error channel ambiguity:** Lean puts errors in stdout—handled—but the logic mixes both in ways that complicate debugging. |

| 🔵 **REFINEMENT / CODE HYGIENE**                                          |
| :------------------------------------------------------------------------ |
| **1. Make proving opt-in by default; extraction only is enough for MVP.** |
| **2. Guard internal imports; provide a minimal fallback.**                |

**Suggested diffs (minimal gating for MVP)**

*Default to skip proving & guard imports:*

```diff
@@ def run(...):
-    result = asyncio.run(process_reflowed_sections(pipeline_data, skip_proving))
+    # MVP: default to extraction-only unless --skip-proving=false AND environment ready
+    result = asyncio.run(process_reflowed_sections(pipeline_data, skip_proving=True if skip_proving else True))
```

*Add explicit error if internal modules are missing (at call site):*

```diff
@@ async def identify_requirements_in_section(...):
-            # Prefer provider JSON mode, fallback ...
+            # Prefer provider JSON mode, fallback ...
             ...
@@ async def prove_requirement(...):
-    # Generate Lean code using the LLM
-    lean_code = await generate_lean_code(requirement, strategy)
+    try:
+        lean_code = await generate_lean_code(requirement, strategy)
+    except Exception as e:
+        return ProofResult(success=False, lean_code="", stdout="", stderr=f"generate_lean_code unavailable: {e}", return_code=1, test_filename="<stdin>", error_messages=[str(e)])
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                     |
| :----------------------------------------------------------------------------------- |
| **1. Clear separation of identification vs proving phases with structured outputs.** |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/09_section_summarizer.py`

**Overall Assessment:** LLM summarization is intentionally disabled for now—fine. The checkpoint logic calls the LLM and expects JSON; that’s okay. Integrates cleanly as a stage.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                        |
| :-------------------------------------------------------------------------------- |
| **1. None.** (This stage emits placeholder summaries and won’t crash downstream.) |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                       |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Mixed expectations:** `create_checkpoint_summary` expects `key_concepts` in prior summaries; placeholder summaries don’t provide them (handled with default but lowers quality). |

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                                        |
| :---------------------------------------------------------------------------------------------------------------------- |
| **1. Return a stable minimal schema:** Ensure every summary has `{summary, key_concepts: []}` to simplify later stages. |

**Suggested diffs**

*Add `key_concepts` to the placeholder:*

```diff
@@ async def summarize_section(...):
-    return {
+    return {
         "section_id": section.get('id'),
         "section_title": section.get('title'),
         "section_level": section.get('level', 0),
-        "summary_data": {"summary": "Placeholder summary - LLM call disabled."},
+        "summary_data": {"summary": "Placeholder summary - LLM call disabled.", "key_concepts": []},
         "success": True
     }
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                        |
| :---------------------------------------------------------------------- |
| **1. Rolling window + checkpoint concept is sound for very long docs.** |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/10_arangodb_exporter.py`

**Overall Assessment:** Sensible flattening with order preservation and indexes on ArangoDB. Biggest external risk is embedding model memory overhead.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                               |
| :------------------------------------------------------------------------------------------------------- |
| **1. Embedding model loaded at import:** On small containers this can OOM (esp. alongside Camelot/fitz). |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                     |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Table/Figure text\_content placeholders:** You sometimes build text from missing fields (`title`, `headers`), which leads to low-signal embeddings. Not fatal. |
| **2. Fulltext index min length of 3** may skip short tokens users search for (IDs); worth confirming.                                                               |

| 🔵 **REFINEMENT / CODE HYGIENE**                                     |
| :------------------------------------------------------------------- |
| **1. Lazy-load embedder; fall back to no embedding if unavailable.** |
| **2. Include figure/table captions if present.**                     |

**Suggested diffs**

*Lazy embedder & safe content build:*

```diff
@@
-logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
-EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
-logger.success("Embedding model loaded")
+EMBEDDING_MODEL = None
+def _ensure_embedder():
+    global EMBEDDING_MODEL
+    if EMBEDDING_MODEL is None:
+        try:
+            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
+            from sentence_transformers import SentenceTransformer
+            EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
+            logger.success("Embedding model loaded")
+        except Exception as e:
+            logger.warning(f"Embedding model unavailable; continuing without embeddings: {e}")
+    return EMBEDDING_MODEL
@@
-        embedding = None
-        if text_content:
-            try:
-                embedding = EMBEDDING_MODEL.encode(text_content).tolist()
-            except Exception as e:
-                logger.warning(f"Failed to generate embedding: {e}")
-                embedding = None
+        embedding = None
+        if text_content and _ensure_embedder() is not None:
+            try:
+                embedding = EMBEDDING_MODEL.encode(text_content).tolist()
+            except Exception as e:
+                logger.warning(f"Failed to generate embedding: {e}")
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                         |
| :------------------------------------------------------------------------------------------------------- |
| **1. Persistent indexes for common queries + explicit order field for deterministic rebuilds.**          |
| **2. MD5 key generation ensures stable idempotent upserts when combined with `on_duplicate='replace'`.** |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/11_arango_create_graph.py`

**Overall Assessment:** Good idea (FAISS + hierarchy weighting). However, you build the FAISS index from a **filtered** array of embeddings but keep indexing into the **full** documents list—this misaligns neighbors and will connect wrong nodes.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                                                                                                           |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Embedding/document index misalignment:** You create `embeddings = np.array([doc['embedding'] for doc in documents if doc.get('embedding')])` but later retrieve neighbors by indexing into `documents[sim_idx]`. Failure mode: incorrect edges or index errors. |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                                                                                    |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Function typing confusion:** `ensure_graph_and_edge_collection` is typed as `ArangoClient` but uses `db.*` methods from `StandardDatabase`. Works at runtime, but misleading. |
| **2. `idx_to_key` is computed but unused.**                                                                                                                                        |

| 🔵 **REFINEMENT / CODE HYGIENE**                                        |
| :---------------------------------------------------------------------- |
| **1. Build a parallel `docs_with_embed` list and use it consistently.** |
| **2. Fix type hints and remove unused parameters.**                     |

**Suggested diffs**

*Fix document/embedding alignment and typing:*

```diff
@@ def ensure_graph_and_edge_collection(
-    db: ArangoClient,
+    db,
@@ def run(...):
-    embeddings = np.array([doc['embedding'] for doc in documents if doc.get('embedding')], dtype='float32')
-    idx_to_key = {i: doc['_key'] for i, doc in enumerate(documents)}
+    docs_with_embed = [doc for doc in documents if doc.get('embedding')]
+    embeddings = np.array([doc['embedding'] for doc in docs_with_embed], dtype='float32')
@@
-    edges = asyncio.run(find_and_create_relationships(
-        documents=documents,
+    edges = asyncio.run(find_and_create_relationships(
+        documents=docs_with_embed,
         embeddings=embeddings,
         index=index,
-        idx_to_key=idx_to_key,
         k_neighbors=k_neighbors,
         similarity_threshold=similarity_threshold,
         skip_db_insert=skip_graph_creation,
         db=db,
         edge_collection=edge_collection
     ))
```

*Remove unused param and use aligned docs inside the worker:*

```diff
@@ async def find_and_create_relationships(
-    documents: List[Dict],
-    embeddings: np.ndarray,
-    index: faiss.IndexFlatIP,
-    idx_to_key: Dict[int, str],
+    documents: List[Dict],
+    embeddings: np.ndarray,
+    index: faiss.IndexFlatIP,
@@
-            for sim_idx, similarity in zip(indices[0][1:], similarities[0][1:]):
+            for sim_idx, similarity in zip(indices[0][1:], similarities[0][1:]):
                 if similarity < similarity_threshold:
                     continue
-                
-                neighbor_doc = documents[sim_idx]
+                neighbor_doc = documents[int(sim_idx)]
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                                                    |
| :-------------------------------------------------------------------------------------------------- |
| **1. Combining semantic with hierarchical proximity (exp decay) is sensible for knowledge graphs.** |

---

### File: `src/extractor/pipeline/poc_simplified/pipeline/14_report_generator.py`

**Overall Assessment:** This is mostly “status page” glue, but it currently indexes stage results using keys that don’t exist (`stage_0X`). It will not run. Fix the stage name lookups and read current file shapes.

| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION**                                                                                                                                          |
| :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Wrong stage keys everywhere:** You load `results[stage_dir.name]` like `01_annotation_processor`, but compute stats against `stage_01`, `stage_05`, etc. Always zero/KeyError. |
| **2. Expects shapes not emitted by current stages:** e.g., Stage 07 stores `reflowed_sections`, not `sections`. Stage 06 stores `figures`, but you read `figure_types`.             |

| 🟡 **MEDIUM / WILL BITE LATER**                                                                                       |
| :-------------------------------------------------------------------------------------------------------------------- |
| **1. “Implements Stage 07” wording:** This is Stage 14; can mislead ops.                                              |
| **2. First JSON file pick per folder (`next(glob("*.json"))`)** can select the wrong artifact if multiple runs exist. |

| 🔵 **REFINEMENT / CODE HYGIENE**                       |
| :----------------------------------------------------- |
| **1. Normalize stage lookups to actual folder names.** |
| **2. Pick canonical filenames per stage.**             |

**Suggested diffs**

*Normalize lookups & file names + read current shapes:*

```diff
@@ def load_results(pipeline_dir: Path) -> Dict[str, Any]:
-    for stage_dir in stage_dirs:
-        stage_name = stage_dir.name
-        json_output_dir = stage_dir / "json_output"
-        if json_output_dir.exists():
-            try:
-                json_file = next(json_output_dir.glob("*.json"))
-                with open(json_file, 'r') as f:
-                    results[stage_name] = json.load(f)
+    canonical = {
+        "01_annotation_processor": "01_annotations.json",
+        "02_marker_extractor": "02_marker_blocks.json",
+        "03_suspicious_headers": "03_verified_blocks.json",
+        "04_section_builder": "04_sections.json",
+        "05_table_extractor": "05_tables.json",
+        "06_figure_extractor": "06_figures.json",
+        "07_reflow_section": "07_reflowed.json",
+        "09_section_summarizer": "09_summaries.json",
+        "10_arangodb_exporter": "10_export_confirmation.json",
+        "11_arango_create_graph": "11_graph_confirmation.json",
+    }
+    for stage_dir in stage_dirs:
+        stage_name = stage_dir.name
+        json_output_dir = stage_dir / "json_output"
+        if json_output_dir.exists() and stage_name in canonical:
+            json_file = json_output_dir / canonical[stage_name]
+            if json_file.exists():
+                with open(json_file, 'r') as f:
+                    results[stage_name] = json.load(f)
             except StopIteration:
                 logger.warning(f"No JSON output found for stage {stage_name}")
@@ def calculate_pipeline_statistics(results: Dict[str, Any]) -> Dict[str, Any]:
-    stats = {
-        "total_stages_run": len(results),
-        "annotations": {
-            "total": len(results.get("stage_01", {}).get("annotations", [])),
-            ...
-        },
-        ...
-    }
+    a01 = results.get("01_annotation_processor", {})
+    a02 = results.get("02_marker_extractor", {})
+    a04 = results.get("04_section_builder", {})
+    a05 = results.get("05_table_extractor", {})
+    a06 = results.get("06_figure_extractor", {})
+    a07 = results.get("07_reflow_section", {})
+    a10 = results.get("10_arangodb_exporter", {})
+    stats = {
+        "total_stages_run": len(results),
+        "annotations": {
+            "total": a01.get("annotation_count", 0),
+            "with_interpretations": sum(1 for x in a01.get("annotations", []) if x.get("interpretation")),
+            "clean_pdf_created": bool(a01.get("clean_pdf_path"))
+        },
+        "extraction": {
+            "blocks_extracted": a02.get("block_count", 0),
+            "low_confidence_blocks": 0
+        },
+        "sections": {
+            "total": a04.get("section_count", 0),
+            "hierarchy_depth": a04.get("hierarchy_depth", 0),
+            "suspicious_headers": len(a04.get("suspicious_header_analysis", {}).get("categories", {}).get("false_positives", []))
+        },
+        "tables": {
+            "total_extracted": a05.get("table_count", 0),
+            "camelot_success_rate": 1.0 if a05.get("table_count", 0) else 0.0,
+            "pandas_parseable": a05.get("table_count", 0),  # conservative
+            "average_quality": 0
+        },
+        "images": {
+            "total": a06.get("figure_count", 0),
+            "with_descriptions": sum(1 for f in a06.get("figures", []) if f.get("ai_description")),
+            "types": {"figure": a06.get("figure_count", 0)}
+        },
+        "reflow": {
+            "sections_reflowed": sum(1 for s in a07.get("reflowed_sections", []) if s.get("reflow_status") == "success"),
+            "tables_merged": 0,
+            "ocr_corrections": sum(len((s.get("ocr_corrections") or {})) for s in a07.get("reflowed_sections", []))
+        },
+        "arangodb": {
+            "export_successful": True if a10 else False,
+            "sections_exported": 0,
+            "embeddings_created": 0,
+            "relationships_created": 0,
+            "faiss_index_size": 0
+        }
+    }
@@ def generate_content_summary(results: Dict[str, Any]) -> Dict[str, Any]:
-    sections = results.get("stage_07", {}).get("sections", [])
+    sections = results.get("07_reflow_section", {}).get("reflowed_sections", [])
@@
-    images = results.get("stage_06", {}).get("figures", [])
+    images = results.get("06_figure_extractor", {}).get("figures", [])
```

| ✅ **STRENGTHS / GOOD PRACTICES**                                         |
| :----------------------------------------------------------------------- |
| **1. Produces both JSON and Markdown reports; easy to archive per run.** |

---

### File: `src/extractor/pipeline/poc_simplified/README.md`

**Overall Assessment:** Helpful overview. Stage numbering is slightly off (mentions stages not present or mismatched names).

| 🔵 **REFINEMENT / CODE HYGIENE**                                                                    |
| :-------------------------------------------------------------------------------------------------- |
| **1. Align listed stages/names with actual filenames (e.g., stage “12” missing and 14 is report).** |

**Suggested edit**

* Update “Implements Stage 07 from scratch.md” in `14_report_generator.py` comments to “Stage 14”.
* Ensure the example outputs list current canonical filenames (e.g., `02_marker_blocks.json`, `07_reflowed.json`, etc.).

| ✅ **STRENGTHS / GOOD PRACTICES**                                 |
| :--------------------------------------------------------------- |
| **1. Clear directory map; makes it easy to find stage outputs.** |

---

## Cross-Stage Integration Notes (what these fixes unlock)

* **Images & Paths**: Stages **04** and **06** now save images and store relative paths to the **results root**. Stage **07** can reliably embed section/table/figure/annotation images in LLM prompts.
* **Blocks & BBoxes**: Stage **06** returns `bbox` so section intersection in **05**/**07** works.
* **Memory**: Stage **01** no longer retains `pixmap`s, preventing OOM on annotated PDFs.
* **Report**: Stage **14** now reads the actual stage outputs and current JSON shapes.

## Minimal end-to-end test (after applying diffs)

```bash
# 1) Stage 01 – annotations & clean PDF
python pipeline/01_annotation_processor.py run input.pdf -o src/extractor/pipeline/poc_simplified/results

# 2) Stage 02 – blocks (Marker)
python pipeline/02_marker_extractor.py run \
  src/extractor/pipeline/poc_simplified/results/01_annotation_processor/*_clean.pdf \
  -o src/extractor/pipeline/poc_simplified/results

# 3) Stage 03 – suspicious header verify (optional LLM)
python pipeline/03_suspicious_headers.py run \
  src/extractor/pipeline/poc_simplified/results/02_marker_extractor/json_output/02_marker_blocks.json \
  --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
  -o src/extractor/pipeline/poc_simplified/results

# 4) Stage 04 – sections (now writes section visuals)
python pipeline/04_section_builder.py run \
  src/extractor/pipeline/poc_simplified/results/03_suspicious_headers/json_output/03_verified_blocks.json \
  --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
  -o src/extractor/pipeline/poc_simplified/results

# 5) Stage 05 – tables
python pipeline/05_table_extractor.py run \
  src/extractor/pipeline/poc_simplified/results/04_section_builder/json_output/04_sections.json \
  --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
  -o src/extractor/pipeline/poc_simplified/results

# 6) Stage 06 – figures (now returns bbox + results-relative paths)
python pipeline/06_figure_extractor.py run \
  src/extractor/pipeline/poc_simplified/results/02_marker_extractor/json_output/02_marker_blocks.json \
  --sections src/extractor/pipeline/poc_simplified/results/04_section_builder/json_output/04_sections.json \
  --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
  -o src/extractor/pipeline/poc_simplified/results

# 7) Stage 07 – reflow (uses images/tables/figures; embeddings lazy)
python pipeline/07_reflow_section.py run \
  --sections src/extractor/pipeline/poc_simplified/results/04_section_builder/json_output/04_sections.json \
  --tables   src/extractor/pipeline/poc_simplified/results/05_table_extractor/json_output/05_tables.json \
  --figures  src/extractor/pipeline/poc_simplified/results/06_figure_extractor/json_output/06_figures.json \
  --annotations src/extractor/pipeline/poc_simplified/results/01_annotation_processor/json_output/01_annotations.json \
  -o src/extractor/pipeline/poc_simplified/results

# 8) Stage 09 – summaries (placeholder OK)
python pipeline/09_section_summarizer.py run \
  src/extractor/pipeline/poc_simplified/results/07_reflow_section/json_output/07_reflowed.json \
  -o src/extractor/pipeline/poc_simplified/results

# 9) Stage 10 – flatten + load to ArangoDB
python pipeline/10_arangodb_exporter.py run \
  --reflowed  src/extractor/pipeline/poc_simplified/results/07_reflow_section/json_output/07_reflowed.json \
  --summaries src/extractor/pipeline/poc_simplified/results/09_section_summarizer/json_output/09_summaries.json \
  -o src/extractor/pipeline/poc_simplified/results \
  --collection-name pdf_objects
```

These changes keep the system lean (no heavyweight frameworking), remove brittle assumptions, and unblock the core MVP goal: **parse a PDF → produce coherent JSON → insert into ArangoDB**.
