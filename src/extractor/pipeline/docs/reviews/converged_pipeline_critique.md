# Brutal Comprehensive Critique: Requirements Extraction and Converged Pipeline

## Repository and Branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/stage-09-llm-enrichment`
- **Paths of interest:**
  - `src/extractor/pipeline/run_pipeline.py`
  - `src/extractor/pipeline/steps/s08_extract_requirements.py`
  - `src/extractor/pipeline/utils/db/schema.py`
  - `src/extractor/pipeline/ingest/html_provider.py`
  - `src/extractor/pipeline/adapters/unified_adapter.py`

---

## Summary of Changes

This feature branch introduces:

1. **Enhanced Requirements Extraction** with `req_id` generation, conditional requirement tracking, and reading order insertion
2. **Converged Pipeline Architecture** with HTML ingestion via `HTMLProvider` and `UnifiedAdapter`
3. **Lean4 Schema** for theorem proving (1:N proofs per requirement)

---

## 🔴 CRITICAL / WILL BREAK IN PRODUCTION

### 1. SQL Injection Vulnerability in Stage 08

**File:** `s08_extract_requirements.py` (lines 43-72, 218-221)

```python
blocks = con.sql(f"""
    SELECT text
    FROM blocks
    WHERE section_id = '{section_id}'  # UNSAFE STRING INTERPOLATION
    ...
""").fetchall()
```

**Impact:** Any section_id containing single quotes will break the query or allow injection. DuckDB is less exploitable than network databases, but this is still a critical code smell.

**Fix:** Use parameterized queries:

```python
con.execute("SELECT text FROM blocks WHERE section_id = ?", [section_id])
```

---

### 2. Bare `except Exception` Swallowing Errors

**File:** `s08_extract_requirements.py` (lines 195-199, 287-290)

```python
try:
    max_sort = con.sql("SELECT COALESCE(MAX(sort_order), 0) FROM merged_content").fetchone()[0]
except Exception:
    max_sort = 0  # SILENTLY IGNORES ALL ERRORS
```

**Impact:** Table not existing, connection issues, and schema mismatches are all hidden. You'll get `max_sort = 0` and never know why.

**Fix:** Catch specific exceptions or at minimum log the error:

```python
except duckdb.CatalogException as e:
    logger.warning(f"merged_content table may not exist: {e}")
    max_sort = 0
```

---

### 3. `re` Module Imported Inside Loop

**File:** `s08_extract_requirements.py` (line 211)

```python
for s_id, title, page_start in sections:
    ...
    import re  # IMPORTED ON EVERY ITERATION
    num_match = re.match(...)
```

**Impact:** Performance overhead from repeated import (though Python caches it). More importantly, this is a code smell indicating rushed implementation.

**Fix:** Move `import re` to the top of the file with other imports.

---

### 4. `uuid` Module Imported Inside Inner Loop

**File:** `s08_extract_requirements.py` (lines 260, 272)

```python
for item in extracted:
    ...
    import uuid  # IMPORTED ON EVERY REQUIREMENT
    r_id = f"req_{uuid.uuid4().hex[:8]}"
```

**Impact:** Same as above. Repeated import inside tight loop over every requirement.

**Fix:** Move `import uuid` to the top of the file.

---

### 5. HTMLProvider Missing Encoding Error Handling

**File:** `html_provider.py` (lines 43-47)

```python
try:
    content = self.file_path.read_text(encoding="utf-8")
except UnicodeDecodeError:
    content = self.file_path.read_text(encoding="latin-1")  # FALLBACK
```

**Impact:** If `latin-1` also fails (binary file misnamed as .html), the entire pipeline crashes with no recovery.

**Fix:** Add a final fallback with `errors='replace'` or log and skip:

```python
except Exception as e:
    logger.error(f"Cannot read {self.file_path}: {e}")
    return UnifiedDocument(id="error", ...)  # Or raise gracefully
```

---

### 6. `merged_content` Schema Not Defined in `schema.py`

**File:** `schema.py` defines `sections`, `blocks`, `tables`, `figures`, `requirements`, `lean4_proofs` but **NOT** `merged_content`.

**Impact:** Stage 08 inserts into `merged_content` assuming it exists, but `schema.py` doesn't create it. Either Stage 07 creates it dynamically (fragile) or the insert will fail on fresh runs.

**Fix:** Add `merged_content` table definition to `schema.py`:

```python
CREATE TABLE IF NOT EXISTS merged_content (
    id VARCHAR PRIMARY KEY,
    section_id VARCHAR,
    page INTEGER,
    type VARCHAR,
    content VARCHAR,
    asset_id VARCHAR,
    sort_order INTEGER
);
```

---

## 🟡 MEDIUM / WILL BITE LATER

### 1. No Idempotency Check for Requirements

**File:** `s08_extract_requirements.py`

**Issue:** Uses `INSERT OR REPLACE` but if the same section is processed twice (resume), you get duplicate requirements with different UUIDs.

**Impact:** Requirements count will double on every re-run for the same section.

**Fix:** Add resume check at the start:

```python
existing_reqs = con.sql(f"SELECT COUNT(*) FROM requirements WHERE section_id = '{s_id}'").fetchone()[0]
if existing_reqs > 0:
    logger.info(f"Skipping section {s_id}: {existing_reqs} requirements already exist")
    continue
```

---

### 2. Heuristic Filter May Reject Valid Sections

**File:** `s08_extract_requirements.py` (line 83)

```python
keywords = ["shall", "must", "require", "constraint", "comply", "will", "should", "tied to"]
```

**Issue:** Documents using different terminology (e.g., "The system NEEDS to...", "It is MANDATORY that...") will be skipped entirely.

**Impact:** Silent data loss - valid requirements won't be extracted.

**Fix:** Either:

1. Add more keywords ("mandatory", "need", "needs to", "expected to")
2. Log skipped sections prominently so operator notices
3. Add `--force-all-sections` flag to bypass heuristic

---

### 3. No Validation of LLM Response Schema

**File:** `s08_extract_requirements.py` (lines 154-164)

```python
data = json_repair.loads(content)
if isinstance(data, list):
    return data
```

**Issue:** No validation that each item has required fields (`text`, `type`, `confidence`). If LLM returns malformed objects, they go into the database with None values.

**Fix:** Add schema validation:

```python
REQUIRED_FIELDS = ["text", "type", "confidence", "citation_snippet"]
validated = []
for item in data:
    if all(item.get(f) is not None for f in REQUIRED_FIELDS):
        validated.append(item)
    else:
        logger.warning(f"Skipping malformed requirement: {item}")
return validated
```

---

### 4. HTMLProvider Doesn't Handle Nested Lists Properly

**File:** `html_provider.py` (lines 176-186)

```python
for li in tag.find_all("li", recursive=False):
    text = li.get_text().strip()  # FLATTENS NESTED LISTS
    ...
    nested = li.find(["ul", "ol"])
    if nested:
        self._process_list(nested)  # PROCESSES AFTER WHICH CREATES GAPS
```

**Issue:** Nested lists are processed after parent, breaking reading order. Also, `get_text()` already includes nested list text, causing duplication.

**Impact:** List items appear duplicated or out of order.

**Fix:** Either recurse first or extract only direct text nodes.

---

### 5. `_write_artifacts_index` Has New Signature But May Be Called Incorrectly

**File:** `run_pipeline.py` (line 389)

```python
def _write_artifacts_index(out: Path, stage_dir: Path) -> None:
```

**Issue:** The function was moved to module level with a new signature, but if any code path calls it with the old signature `(stage_dir)`, it will fail silently or raise TypeError.

**Impact:** Missing artifact indexes in some code paths.

**Fix:** grep for all call sites and verify signature matches:

```bash
grep -n "_write_artifacts_index" src/extractor/pipeline/run_pipeline.py
```

---

### 6. UnifiedAdapter Generates sort_order Without Context

**File:** `unified_adapter.py` (lines 93-98)

```python
sort_order = section_sort_base + section_req_idx * 10
```

**Issue:** For HTML, `section_sort_base` is calculated from section index, not page position. Requirements get sequential sort_order but may not interleave correctly with text blocks.

**Impact:** Reading order may be off for HTML documents.

**Fix:** Use block insertion order or calculate sort_order based on DOM position.

---

## 🔵 REFINEMENT / CODE HYGIENE

### 1. Unused `section_number` Parameter

**File:** `s08_extract_requirements.py` (line 112)

```python
def extract_requirements_llm(router, title: str, text: str, tables: List[str], section_number: str = "") -> List[Dict[str, Any]]:
```

**Issue:** `section_number` is passed but never used inside the function body.

**Fix:** Either use it in the prompt or remove the parameter.

---

### 2. Magic Numbers

**File:** `s08_extract_requirements.py`

```python
THRESHOLD_CITATION_MATCH = 80.0  # Magic number
sort_order = section_sort_base + section_req_idx * 10  # Magic 10
page * 10000  # Magic multiplier
```

**Fix:** Define constants with descriptive names:

```python
SORT_ORDER_SECTION_MULTIPLIER = 10000
SORT_ORDER_BLOCK_INCREMENT = 10
```

---

### 3. Duplicate Logging

**File:** `s08_extract_requirements.py` output shows:

```
13:34:08 | INFO     | run_extract_requirements:208 - Processing Section...
2025-12-30 13:34:08.621 | INFO     | extractor.pipeline.steps.s08_extract_requirements:run_extract_requirements:208 - Processing Section...
```

**Issue:** Every log message appears twice - once from loguru default handler and once from custom format.

**Fix:** Remove duplicate handlers or configure loguru once at entry point.

---

### 4. Comment-Only Code Path Indicators

**File:** `html_provider.py` has multiple `# TODO`, `# Note`, `# For MVP` comments suggesting incomplete implementation.

**Fix:** Either complete the implementation or create actual TODO issues/tickets.

---

## ✅ STRENGTHS / GOOD PRACTICES

### 1. Clean Separation of Concerns

- `HTMLProvider` handles parsing
- `UnifiedAdapter` handles conversion
- `run_pipeline.py` handles orchestration
- Clear strategy pattern with `_run_pdf_strategy` vs `_run_html_strategy`

### 2. Proper Use of DuckDB for Local State

- Using DuckDB instead of scattered JSON files improves queryability
- Schema defined centrally in `schema.py`

### 3. `req_id` Format is Human-Readable

- `REQ-4.1.5.4-001` is much better than `req_a7f8b2c1`
- Easy to trace requirements back to source sections

### 4. Conditional Requirement Tracking

- Extracting `is_conditional` and `condition_text` is forward-thinking
- Enables sophisticated downstream analysis

---

## Clarifying Questions

1. **merged_content creation:** Where is `merged_content` table created? Is it in Stage 07 dynamically or should it be in `schema.py`?

2. **Resume semantics:** Should Stage 08 clear existing requirements before re-running, or append/update? Current behavior appears to append duplicates.

3. **Lean4 integration:** Is there existing Lean4 code that will use `lean4_proofs`? The table is created but never populated.

4. **HTMLProvider completeness:** Is the current simple implementation sufficient, or do we need to handle more complex HTML (CSS, JavaScript-rendered content)?

---

## Recommended Next Steps

1. **Fix SQL injection** - Parameterize all queries immediately
2. **Add merged_content to schema.py** - Ensure table exists before insert
3. **Move imports to file top** - `re`, `uuid` inside loops is a smell
4. **Add resume/idempotency check** - Prevent duplicate requirements
5. **Validate LLM response schema** - Don't trust LLM output blindly
