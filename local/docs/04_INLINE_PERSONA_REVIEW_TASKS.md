# Task List: Inline Persona Review Loop with /memory Integration

**Created**: 2026-02-13
**Goal**: Replace external supervisor polling with self-contained per-PDF quality loop where Margaret/Jennifer personas evaluate each extracted PDF, search /memory for related past reviews, run remediation if needed, and loop until PASS. Store all reviews in ArangoDB via /memory.

## Context

The current persona review system is spread across 3 loosely-coupled systems (discovery.py, batch_review.py, supervise_learn_datalake.py) communicating through file I/O, dynamic imports, and fire-and-forget Popen. After 10 bug fixes, it's clear the coupling is the root cause — not the scoring logic itself. The scoring went from 0.659 to 0.945 without changing extraction code; we were measuring wrong because reviews are stateless and ephemeral.

The new architecture makes each PDF self-contained: Extract → Score → Persona Review → Store in /memory → Remediate if needed → Re-extract → Loop until PASS. The supervisor becomes a thin process manager that queries /memory for convergence status.

Key APIs confirmed via research:
- `record_assessment()` in `graph_memory.api` stores to `nightly_assessments` collection
- `add_edge()` creates graph edges between lessons
- `common.memory_client.MemoryClient` provides retry + rate limiting
- `build_issues()` → `dimension_scores()` → `overall_from_dimensions()` are pure functions
- `margaret_evaluates()` / `jennifer_evaluates()` / `reconcile()` are pure functions
- `escalation_jobs()` maps issue codes to skill commands
- `_extract_pdf_to_profile()` returns `(Path | None, Dict[str, Any])`

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| graph_memory | `get_db()` → pdf_assessments | `sanity/sanity_record_assessment.py` | [x] PASS |
| graph_memory | `add_edge()` | `sanity/sanity_add_edge.py` | [x] PASS |
| graph_memory | `MemoryClient.learn/recall` | `sanity/sanity_memory_recall.py` | [x] PASS |
| review-pdf/verify | `build_issues()`, `dimension_scores()` | `sanity/sanity_scoring_pipeline.py` | [x] PASS |

> All sanity scripts must PASS before proceeding to implementation.

## Questions/Blockers

None — all requirements clear. ArangoDB is fundamental; if it's down, the system is down (user confirmed).

## Tasks

### P0: Sanity Scripts (Sequential)

- [x] **Task 1**: Create sanity scripts verifying ArangoDB + /memory + scoring APIs work in isolation
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Files:
    - `sanity/sanity_record_assessment.py` — import `record_assessment`, write a test doc, read it back, delete it
    - `sanity/sanity_add_edge.py` — create two test lessons, add edge between them, verify traversal, clean up
    - `sanity/sanity_memory_recall.py` — learn a test lesson, recall it, verify found=true, delete it
    - `sanity/sanity_scoring_pipeline.py` — import `build_issues`, `dimension_scores`, `overall_from_dimensions` from review-pdf/verify/scoring.py, run with mock data, verify output schema matches expected keys
  - **Definition of Done**:
    - Test: `python3 sanity/sanity_record_assessment.py && python3 sanity/sanity_add_edge.py && python3 sanity/sanity_memory_recall.py && python3 sanity/sanity_scoring_pipeline.py`
    - Assertion: All four scripts exit 0 and print "PASS"

### P1: Core Module — inline_reviewer.py (Sequential after P0)

- [x] **Task 2**: Create `inline_reviewer.py` — self-contained per-PDF scoring + persona review + /memory storage
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 1
  - Location: `/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor-quality-check/inline_reviewer.py`
  - **What it does**:
    1. Takes a profile path (output of extraction)
    2. Resolves all doc inputs via `resolve_doc_inputs()`
    3. Extracts S00 estimates + analyzes structural/flattened/sections/pdf source
    4. Calls `build_issues()` → `dimension_scores()` → `overall_from_dimensions()`
    5. Calls `margaret_evaluates()` + `jennifer_evaluates()` + `reconcile()`
    6. Searches /memory for related past reviews of same PDF hash and similar dimension failures
    7. Stores structured review in /memory via `record_assessment()` + `learn()`
    8. Generates escalation jobs if WARN/FAIL
    9. Returns structured result dict
  - **Function signature**:
    ```python
    def review_pdf(
        profile_path: Path,
        corpus_root: Path,
        run_id: str = "",
        max_related_reviews: int = 5,
    ) -> dict:
        """Returns:
        {
            "pdf_path": str,
            "pdf_hash": str,
            "overall_score": float,
            "grade": str,
            "verdict": "PASS"|"WARN"|"FAIL",
            "dimensions": dict,  # full dimension breakdown
            "margaret": {"verdict": str, "weighted_score": float, "issues": list, "says": str},
            "jennifer": {"verdict": str, "weighted_score": float, "issues": list, "says": str},
            "reconciled": {"decision": str, "consensus": bool, ...},
            "related_reviews": list,  # from /memory recall
            "escalation_jobs": list,  # from escalation_jobs()
            "memory_assessment_id": str,  # ArangoDB doc _key
            "memory_lesson_id": str|None,  # only for WARN/FAIL
            "timestamp": str,
        }
        """
    ```
  - **Key design decisions**:
    - Imports scoring functions directly (no subprocess, no dynamic import)
    - Uses `common.memory_client.MemoryClient` for recall with retry logic
    - Uses `graph_memory.api.record_assessment()` for structured storage
    - For WARN/FAIL PDFs: also calls `learn()` with problem=dimension failure, solution=remediation recommendation
    - For PASS PDFs: `record_assessment()` only (no learn node needed)
    - Tags: `[sector, grade, persona_verdict, coverage_phase, pdf_hash[:8]]`
    - Memory recall query: `f"pdf extraction {sector} {worst_dimension} review"` to find similar past issues
  - **Definition of Done**:
    - Test: `python3 -m pytest tests/extractor_quality_check/test_inline_reviewer.py -v`
    - Assertion: `review_pdf()` returns valid result dict with all required keys, stores assessment in ArangoDB, recall finds it, and returns correct verdict for a known-good profile

- [x] **Task 3**: Create `inline_review_loop.py` — self-improvement loop that extracts, reviews, remediates, and re-extracts until PASS
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 2
  - Location: `/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor-quality-check/inline_review_loop.py`
  - **What it does**:
    1. Takes a PDF path
    2. Extracts via `_extract_pdf_to_profile()`
    3. Reviews via `review_pdf()` (Task 2)
    4. If PASS: return success
    5. If WARN/FAIL: run auto-executable escalation jobs (with cooldown)
    6. Re-extract after remediation
    7. Re-review
    8. Loop until PASS or `max_iterations` (default 3)
    9. Each iteration stored in /memory — graph edges link iterations for convergence tracking
  - **Function signature**:
    ```python
    def review_loop(
        pdf_path: Path,
        corpus_root: Path,
        extracted_runs_dir: Path | None = None,
        max_iterations: int = 3,
        run_id: str = "",
        remediation_timeout: int = 1800,
    ) -> dict:
        """Returns:
        {
            "pdf_path": str,
            "iterations": int,
            "final_verdict": "PASS"|"WARN"|"FAIL",
            "final_score": float,
            "converged": bool,
            "reviews": list[dict],  # one per iteration
            "remediation_actions": list[dict],
            "memory_edge_ids": list[str],  # convergence chain edges
        }
        """
    ```
  - **Key design decisions**:
    - Each iteration creates a `record_assessment()` entry
    - Edges between iterations: `add_edge(from=review_N, to=review_N-1, type="supersedes")`
    - Remediation jobs run synchronously (blocking) within the loop, NOT fire-and-forget
    - Cap at 3 iterations to prevent infinite loops on genuinely hard PDFs
    - After max_iterations with no PASS: mark as "hard_tail" in /memory for human review
  - **Definition of Done**:
    - Test: `python3 -m pytest tests/extractor_quality_check/test_inline_review_loop.py -v`
    - Assertion: Loop runs 1-3 iterations, stores review chain in /memory, edges link iterations, final verdict matches expected for test fixture

### P2: Graph Edges and Pattern Discovery (Parallel after P1)

- [x] **Task 4**: Add graph edges for cross-PDF pattern discovery
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task 2, Task 3
  - Location: Extend `inline_reviewer.py` with edge creation functions
  - **What it does**:
    - After storing a review, create edges to:
      1. Previous reviews of the same PDF (`supersedes` edge)
      2. Reviews with similar dimension failures in the same sector (`related_to` edge)
      3. Remediation actions that were taken (`depends_on` edge from review to remediation lesson)
    - Add `find_related_reviews()` function that uses multi-hop traversal to find:
      - PDFs in the same sector with the same dimension failure pattern
      - Remediation actions that fixed similar issues
      - Convergence trends for similar PDFs
  - **Definition of Done**:
    - Test: `python3 -m pytest tests/extractor_quality_check/test_review_graph_edges.py -v`
    - Assertion: Given 3 reviews of the same PDF, graph traversal returns them in order. Given 2 reviews of different PDFs with same sector + dimension failure, `find_related_reviews()` returns the other.

- [x] **Task 5**: Add convergence tracking via /memory queries
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task 2, Task 3
  - Location: `/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor-quality-check/convergence_tracker.py`
  - **What it does**:
    - Replace counter-based convergence tracking with score-trajectory queries
    - `get_convergence_status(corpus_root)`: queries /memory for last N reviews, computes trend
    - `get_sector_convergence(sector)`: per-sector score trends
    - `get_dimension_convergence(dimension)`: per-dimension score trends
    - Uses `nightly_assessments` collection with AQL aggregation queries
  - **Function signatures**:
    ```python
    def get_convergence_status(
        corpus_root: Path,
        window_size: int = 50,
    ) -> dict:
        """Returns:
        {
            "trend": "improving"|"plateau"|"degrading",
            "avg_score": float,
            "score_trajectory": list[float],  # last N scores
            "phase": str,
            "coverage_pct": float,
            "reviews_total": int,
            "sectors": dict[str, {"trend": str, "avg_score": float}],
            "dimensions": dict[str, {"trend": str, "avg_score": float}],
        }
        """
    ```
  - **Definition of Done**:
    - Test: `python3 -m pytest tests/extractor_quality_check/test_convergence_tracker.py -v`
    - Assertion: Given 10 inserted reviews with improving scores, `get_convergence_status()` returns `trend="improving"`. Given 10 reviews with same score, returns `trend="plateau"`.

### P3: Wire into Extraction Pipeline (Sequential after P2)

- [x] **Task 6**: Wire `review_loop()` into `discovery.py` post-extraction callback
  - Agent: general-purpose
  - Parallel: 3
  - Dependencies: Task 3, Task 4, Task 5
  - Location: `/home/graham/workspace/experiments/pi-mono/.pi/skills/review-pdf/verify/discovery.py`
  - **What it does**:
    - After `_extract_pdf_to_profile()` returns a successful profile path, call `review_loop()`
    - If review_loop verdict is PASS: continue to next PDF
    - If WARN after max iterations: log and continue (don't block the pipeline)
    - If FAIL after max iterations: add to hard_tail list in /memory
    - Make this opt-in via `--inline-review` flag (default: off) so existing behavior is preserved
  - **Key constraint**: Must not break existing `discovery.py` flow — flag-gated
  - **Definition of Done**:
    - Test: `python3 -m pytest tests/review_pdf/test_discovery_inline_review.py -v`
    - Assertion: With `--inline-review`, extracted PDF gets reviewed and stored in /memory. Without flag, behavior unchanged.

- [x] **Task 7**: Update supervisor to query /memory for convergence instead of running stratified sampling
  - Agent: general-purpose
  - Parallel: 3
  - Dependencies: Task 5, Task 6
  - Location: `/home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/supervise_learn_datalake.py`
  - **What it does**:
    - When `--inline-review` is active on the child process, supervisor skips `_run_stratified_sample_review()`
    - Instead, queries `convergence_tracker.get_convergence_status()` for decision
    - CONTINUE if trend is improving or plateau with score above phase threshold
    - SPOT_FIX if trend is degrading
    - RESTART only if convergence shows catastrophic regression
    - Supervisor poll interval can increase from 20s to 60s since reviews happen inline
  - **Key constraint**: Old behavior preserved when `--inline-review` not set
  - **Definition of Done**:
    - Test: `python3 -m pytest tests/learn_datalake/test_supervisor_memory_convergence.py -v`
    - Assertion: Supervisor reads convergence from /memory, makes correct CONTINUE/SPOT_FIX decision based on score trajectory

### P4: Cleanup and Documentation (After P3)

- [x] **Task 8**: Remove deprecated code paths and update SKILL.md files
  - Agent: general-purpose
  - Parallel: 4
  - Dependencies: Task 6, Task 7
  - **What it does**:
    - Add `INLINE_REVIEW=true` env var support alongside `--inline-review` flag
    - Update `extractor-quality-check/SKILL.md` with new inline review architecture
    - Update `learn-datalake/SKILL.md` with new convergence tracking approach
    - Add migration guide: how to switch from polling to inline
    - DO NOT remove old code yet — keep as fallback for one release cycle
  - **Definition of Done**:
    - Test: Manual review — SKILL.md files accurately describe new architecture
    - Assertion: Both old (polling) and new (inline) modes work simultaneously

- [x] **Task 9**: Store architectural lessons in /memory for future agents
  - Agent: general-purpose
  - Parallel: 4
  - Dependencies: Task 8
  - **What it does**:
    - `./run.sh learn` for each major architectural decision:
      1. "Inline persona review replaces external supervisor polling"
      2. "Self-improvement loop: extract → review → remediate → re-extract → until PASS"
      3. "Graph edges for convergence tracking supersede counter-based convergence"
      4. "ArangoDB nightly_assessments collection stores all persona reviews"
    - Update `MEMORY.md` with new architecture
  - **Definition of Done**:
    - Test: `./run.sh recall --q "inline persona review"` returns the stored lessons
    - Assertion: At least 3 of 4 lessons found with confidence > 0.5

## Completion Criteria

- [x] All sanity scripts pass
- [x] All tasks marked [x]
- [x] All Definition of Done tests pass
- [x] No regressions in existing pipeline (old polling mode still works)
- [x] /memory contains persona reviews with graph edges
- [x] Convergence tracking queries /memory instead of counters
- [x] Self-improvement loop runs extract → review → remediate → re-extract

## Notes

- **ArangoDB is fundamental**: If it's down, the system is down. No local fallback needed (user confirmed).
- **Hybrid granularity**: PASS PDFs get `record_assessment()` only. WARN/FAIL PDFs also get `learn()` nodes with remediation recommendations.
- **Remediation in loop is synchronous**: Unlike the old fire-and-forget Popen, remediation within the self-improvement loop runs blocking. This is intentional — the loop needs the result before re-extracting.
- **Max 3 iterations**: Prevents infinite loops on genuinely hard PDFs (1000+ page MIL-STDs).
- **Graph edges use `supersedes` type**: Each review iteration supersedes the previous one, creating a convergence chain.
- **Backward compatible**: `--inline-review` flag gates all new behavior. Old polling mode works unchanged.
- **Files modified** (canonical copies at `pi-mono/.pi/skills/`):
  - NEW: `extractor-quality-check/inline_reviewer.py`
  - NEW: `extractor-quality-check/inline_review_loop.py`
  - NEW: `extractor-quality-check/convergence_tracker.py`
  - MODIFIED: `review-pdf/verify/discovery.py` (add post-extraction hook)
  - MODIFIED: `learn-datalake/supervise_learn_datalake.py` (query /memory for convergence)
  - MODIFIED: `extractor-quality-check/SKILL.md`
  - MODIFIED: `learn-datalake/SKILL.md`
