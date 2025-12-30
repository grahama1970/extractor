# Copilot Review Round 3 — Post-Test Verification

## Repository and Branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/stage-09-llm-enrichment`
- **HEAD SHA:** `20fb3191` (6 commits ahead of initial review)

## Context

Pipeline test completed successfully after applying Copilot Round 1 + Round 2 fixes.

### Test Run Summary

**1. Verification Run (summary-only):** `--summary-only`

- Status: PASS (exit code 0)
- Blocks: 116, Sections: 3, Tables: 6, Figures: 1

**2. Full Verification Run (LLM enabled):** `--skip-fig-descriptions` (S08+S09 enabled)

- Status: PASS (exit code 0)
- **S08 Requirements:** 29 extracted matching "REQ-..." pattern.
- **S09 Enrichment (Tables):** 6 tables enriched with `llm_title` (LATERAL JOIN coverage fix verified).
- **S09 Enrichment (Figures):** 0 enriched (pending investigation, but pipeline ran).
- **S03b:** Metrics logging implemented and verified via code inspection.

### Issues Found & Fixed

**FIXED:** `s10_arangodb_exporter` ImportError

- Module doesn't exist but was being imported unconditionally
- Wrapped in try/except since arango export is optional

## All Fixes Applied (6 commits)

| ---------- | ------------------------------------------------------------------ |
| `e4a4e9b9` | S03b index mismatch, prompt bug; S06 unreachable code; S10 DB name |
| `0d95e01b` | S08 idempotency; Schema drift; HTMLProvider encoding |
| `c5eb72ef` | S06 log-summary non-fatal; S09 runtime ALTERs removed |
| `cbad2112` | S06 docstring; S10 relative image paths |
| `20fb3191` | s10_arangodb_exporter import wrapped in try/except |

## Review Focus Areas

### 1. Verify Fixes Are Correct

The pipeline test passed, but please confirm:

- S03b tuple approach for index tracking works correctly
- S08 deterministic IDs produce stable results on re-run
- S10 relative paths work for embedded images in Markdown

### 2. Missing Modules to Audit

The test revealed these imports are guarded but modules don't exist:

- `s10_arangodb_exporter` — wrapped in try/except
- `s11_arango_create_graph` — already guarded

Should these be:
a) Created as stub modules that log "not implemented"?
b) Removed from the codebase entirely?
c) Left as-is with optional imports?

### 3. Test Without --summary-only

The test used `--summary-only` which skips:

- Stage 08 requirements extraction
- Stage 09 LLM enrichment
- Stage 09 section summarizer

Should we run a full test with LLM enabled to validate those stages?

### 4. Remaining Deferred Items

Per Round 2, these items were deferred:

- S03b verification summary metrics
- S09 asset coverage (drive from primary tables/figures)

Are these still needed given the pipeline passes?

### 3. Evidence for Verification (Requested by Copilot)

#### S03b: Tuple Approach for Index Tracking

**File:** `src/extractor/pipeline/steps/s03b_header_verifier.py`
**Confirmation:**

- Candidates list stores tuples: `candidates.append((i, b))`
- Request includes index: `"index": block_idx`
- Response handler uses index to map back:

```python
req_idx = r["index"]
block_idx = requests[req_idx]["index"]
block = blocks[block_idx]
```

#### S08: Deterministic IDs

**File:** `src/extractor/pipeline/steps/s08_extract_requirements.py`
**Confirmation:**

- Uses SHA1 hash of section ID + requirement ID for stability:

```python
id_hash = hashlib.sha1(f"{s_id}:{req_id}".encode()).hexdigest()[:12]
r_id = f"req_{id_hash}"
```

- Idempotency check skips sections with existing requirements.

#### S10: Relative Image Paths

**File:** `src/extractor/pipeline/steps/s10_markdown_exporter.py`
**Confirmation:**

- Computes path relative to `pipeline_dir`:

```python
img_abs = Path(content)
img_rel = img_abs.relative_to(pipeline_dir) if img_abs.is_absolute() else Path(content)
sec_lines.append(f"![{title}]({img_rel})")
```

#### Missing Modules / Optional Imports

**File:** `src/extractor/pipeline/run_pipeline.py`
**Start Line:** ~498
**Status:** Wrapped `s10_arangodb_exporter` in `try/except ImportError`.

---

## Deliverable

1. Confirmation of fix correctness (see Evidence above)
2. Recommendation for missing module handling (Keep as optional imports)
3. Full test results (see Summary above)
