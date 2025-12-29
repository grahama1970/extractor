# Brutal Review Request: Stage 09 LLM Enrichment Refactor

## Repository and branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/stage-09-llm-enrichment`
- **Paths of interest:**
  - `src/extractor/pipeline/steps/09_llm_enrichment.py`
  - `src/extractor/pipeline/steps/07_assemble_corpus.py` (env fix)
  - `src/extractor/pipeline/steps/08_extract_requirements.py` (env fix)

## Summary

Stage 09 was refactored to move from a "hacky" manual concurrency implementation to a strictly **SCILLM Paved Path** compliant architecture. The primary goal is to enrich extracted assets (tables/figures) with high-quality metadata using surrounding text context while maintaining high operator visibility and robust error handling.

## Objectives

### 1. SCILLM Contract Alignment

- Use `list_models_openai_like` for pre-flight discovery.
- Implement `parallel_acompletions_iter` for "as-completed" progress reporting and checkpointing potential.
- Leverage `SCILLM_JSON_STRICT=1` and `json_repair` for reliable structured output.

### 2. Contextual Enrichment

- Use DuckDB window queries to fetch `context_before` and `context_after` text for every asset.
- Improve prompt structure to separate system role, technical instructions, and contextual data.

### 3. Verification of "INFERRED" Logic

- Ensure the LLM correctly identifies when a verbatim caption is missing and prepends `INFERRED: ` to the generated title.

### 4. Code Hygiene

- Remove `sys.path.append` in favor of standardized `load_dotenv(find_dotenv(usecwd=True))`.

## Constraints for the patch

- No raw `openai` or `litellm` calls; use SciLLM helpers exclusively.
- No manual semaphore/concurrency logic (delegate to SciLLM).
- Maintain `loguru` standard for all logging.

## Acceptance criteria

- `PYTHONPATH=src uv run python src/extractor/pipeline/steps/09_llm_enrichment.py` runs and enriches assets without hanging.
- Progress logs (e.g., `[1/7]`, `[2/7]`) are visible and accurate.
- Table and figures columns `llm_title` and `llm_description` are populated correctly.

## Test plan

1. Run `07_assemble_corpus.py` to populate the `merged_content` table.
2. Run `09_llm_enrichment.py` with `--concurrency 4`.
3. Query DuckDB to verify that titles of tables without captions are prefixed with `INFERRED: `.

## Clarifying questions for Reviewers

1. **Pre-flight Policy:** Is `list_models_openai_like` sufficient for pre-flight, or should we use the more aggressive `sanity_preflight` (which currently has sync/async loop compatibility issues in this environment)?
2. **Context Size:** We are currently taking the immediate preceding/succeeding text block. Is this enough "signal" for complex hardware tables, or should we expand to N blocks?
3. **JSON Repair:** Is `json_repair` the preferred layer, or should we rely on SciLLM's internal `repair_invalid_json=True` (noting that `parallel_acompletions_iter` doesn't expose it as cleanly yet)?

## Deliverable

- A brutal technical critique of the file structure, prompt quality, and contract compliance.
- Suggested optimizations for the DuckDB context queries.
