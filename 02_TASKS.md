# Task List: Extractor Skill Reliability & Usability

## Context
Make the extractor project and its pi-mono skill (`/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor`) fully tested, reliable, and easy for project-agents and humans to use.

**Key Feature:** Interactive preset collaboration flow:
1. If `--preset` provided → use it directly (skip s00)
2. If no `--preset`:
   - Run s00_profile_detector to analyze PDF
   - If high confidence match → auto-extract with that preset
   - If no match / low confidence → interactive prompt to select preset

## Current State
- Sanity tests: 7/7 passing (extractor project)
- Skill files: SKILL.md, run.sh, extract.py, sanity.sh
- Missing: README.md for maintainers
- Cross-format parity: 10 formats work (MD/DOCX 100%, PDF 87%, etc.)
- Uncommitted changes: custom_llm_provider fixes, --preset flag
- s00_profile_detector: Returns `matched`, `confidence` (point score), `needs_new_preset`

## Tasks

- [ ] **Task 1**: Verify extractor skill sanity.sh completes successfully
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Notes: Run `/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor/sanity.sh` and fix any failures. Should test all 10 formats.

- [ ] **Task 2**: Implement interactive preset collaboration flow in extract.py
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - Notes: Implement the full collaboration flow per Design Decisions:

    **Flow when no `--preset` provided for PDFs:**
    1. Run s00_profile_detector to get profile (features, preset match, confidence)
    2. If `confidence >= 8` → auto-extract, print:
       `Detected preset: arxiv (confidence: 12). Extracting in accurate mode...`
    3. If no match / low confidence:
       - If TTY (interactive): show prompt with feature summary + preset options
       - If non-TTY: auto-fallback to "auto" mode with warning log

    **Interactive prompt format:**
    ```
    Analyzing: paper.pdf
    Detected: multi-column layout, 12 pages
    Contains: 15 tables, 8 figures, formulas

    Select extraction preset:
      [1] arxiv - Academic papers (2-column, math) [RECOMMENDED]
      [2] requirements_spec - Engineering specs (REQ-xxx)
      [3] auto - Let pipeline decide
      [4] fast - Quick extraction, no LLM
    Enter choice [1-4] (default: 1):
    ```

    **Default mode logic:**
    - If tables/figures/equations/multi-column → default to "accurate"
    - Simple text-only → default to "fast"

    **New flags:**
    - `--no-interactive`: Skip prompts, use auto mode
    - `--profile-only`: Run s00 only, return flat JSON profile

    **Error handling:**
    - Corrupt PDF in batch: Log error, skip, continue
    - s00 failure: Fall back to prompt (or auto if non-TTY)

- [ ] **Task 3**: Add error handling guidance to skill output
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - Notes: When extraction fails in extract.py, provide actionable guidance (check env vars, try --fast mode, check CHUTES_API_KEY, etc.).

- [ ] **Task 4**: Create README.md for extractor skill maintainers
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2
  - Notes: Create `/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor/README.md` with maintainer guidance, collaboration flow documentation, troubleshooting, and code structure.

- [ ] **Task 5**: Update SKILL.md and --help with collaboration examples
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2, 4
  - Notes: Update both SKILL.md and extract.py --help to document the interactive collaboration flow.

- [ ] **Task 6**: Implement batch report generation
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2
  - Notes: After batch extraction, generate a summary report:

    **Report contents:**
    ```json
    {
      "batch_id": "2026-01-17T10:30:00",
      "total_files": 25,
      "succeeded": 22,
      "failed": 2,
      "skipped": 1,
      "results": [
        {"file": "paper1.pdf", "status": "success", "preset": "arxiv", "sections": 12, "tables": 5, "figures": 8, "arango_id": "docs/abc123"},
        {"file": "corrupt.pdf", "status": "failed", "error": "PDF corrupt: unable to read"},
        ...
      ],
      "aggregates": {
        "total_sections": 156,
        "total_tables": 42,
        "total_figures": 89,
        "total_pages": 312
      },
      "arango_collection": "extracted_documents",
      "ready_for": ["doc-to-qra", "edge-verifier"]
    }
    ```

    **Output options:**
    - `--report json` → JSON to stdout (default for batch)
    - `--report summary` → Human-readable summary
    - Write to `batch_report.json` in output dir

- [ ] **Task 7**: Add downstream skill integration hooks (memory-first)
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6
  - Notes: Make extracted data queryable via memory and ready for downstream skills:

    **For memory/recall (PRIMARY):**
    - After each successful extraction, auto-learn to memory:
      ```python
      memory.learn(
          problem=f"What is in {filename}?",
          solution=f"{sections} sections, {tables} tables, {figures} figures. Topics: {topics}"
      )
      ```
    - Add `--learn` flag (default: True) to auto-store extraction summaries
    - Add `--scope` flag to specify memory scope (default: "documents")

    **For doc-to-qra:**
    - Output includes `markdown_path` for each document
    - Add `--qra` flag to automatically run doc-to-qra on successful extractions
    - Example: `./run.sh ./pdfs/ --qra --scope research`

    **For edge-verifier:**
    - Output includes `arango_id` for each document
    - Sections stored in ArangoDB are ready for edge linking

    **For episodic-archiver:**
    - Batch session can be archived for recall
    - Add `--archive` flag to store extraction session

    **Verification:**
    ```bash
    # After extraction, this should work:
    ./memory/run.sh recall --q "What tables are in paper.pdf?"
    # Returns: "paper.pdf contains 5 tables: Table 1 (Performance Metrics)..."
    ```

- [ ] **Task 8**: Add LLM-verified edge creation for multi-hop traversal
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6, 7
  - Notes: Create verified edges between extracted nodes using scillm:

    **Why edges matter:**
    - Without edges: "What relates to Table 5?" → requires full scan
    - With edges: "What relates to Table 5?" → follow graph edges → instant

    **Edge types to verify:**
    - `references`: Section A references Table B
    - `implements`: Code block implements Requirement X
    - `contradicts`: Claim A contradicts Claim B (across docs)
    - `extends`: Section in doc2 extends concept from doc1

    **Implementation using scillm:**
    ```python
    from scillm.batch import parallel_acompletions_iter

    # For each extracted node pair, verify relationship
    requests = [
        {
            "model": "chutes/text",
            "messages": [
                {"role": "system", "content": EDGE_VERIFY_PROMPT},
                {"role": "user", "content": f"Source: {node_a}\nTarget: {node_b}\nClassify relationship."}
            ],
            "response_format": {"type": "json_object"},
            "index": i
        }
        for i, (node_a, node_b) in enumerate(candidate_pairs)
    ]

    async for r in parallel_acompletions_iter(
        requests,
        api_base=api_base,
        api_key=api_key,
        custom_llm_provider="openai_like",  # Required per SCILLM_PAVED_PATH_CONTRACT
        concurrency=6,
        timeout=45,
        wall_time_s=300,
        tenacious=False,
    ):
        if r.get("ok"):
            # Store verified edge in ArangoDB
            store_edge(r["parsed"]["source"], r["parsed"]["target"], r["parsed"]["relationship"])
    ```

    **Flags:**
    - `--verify-edges`: Run edge verification after extraction (default: True for accurate mode)
    - `--edge-scope intra`: Only within-document edges
    - `--edge-scope cross`: Include cross-document edges (slower, more powerful)

    **Multi-hop query example:**
    ```
    User: "What requirements relate to the safety tables?"
    Agent: [graph traversal: requirements --references--> tables --tagged--> safety]
    Agent: "REQ-042, REQ-089, and REQ-103 reference Tables 7, 12, and 15 which are tagged as safety-related."
    ```

- [ ] **Task 9**: Commit extractor repo changes
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1, 2, 3, 6, 8
  - Notes: Commit uncommitted changes (custom_llm_provider fixes, --preset flag, CONTEXT.md, batch reporting, edge verification) to extractor repo.

- [ ] **Task 10**: Commit pi-mono skill changes
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 4, 5, 7, 9
  - Notes: Commit skill changes (extract.py with interactive flow, batch reports, memory hooks, edge verification, sanity.sh, SKILL.md, README.md) to pi-mono repo.

## Completion Criteria
1. `sanity.sh` passes for all formats
2. Interactive preset flow works for unknown PDFs
3. High-confidence PDFs auto-extract without prompting
4. `--no-interactive` flag works for batch/CI
5. `--profile-only` returns flat JSON profile for agents
6. Batch report generated with success/fail/metrics/arango_ids
7. Auto-learn to memory after extraction (`memory/recall` works)
8. LLM-verified edges created for multi-hop graph traversal
9. Downstream skills can consume batch_report.json directly
10. README.md exists with maintainer guidance
11. Error messages provide actionable next steps
12. All changes committed to both repos

## Questions/Blockers
None - all resolved (see Design Decisions below).

## Design Decisions (Resolved)

### Confidence & Auto-Extract
- **Threshold**: Auto-extract if `confidence >= 8`
- **Scoring reference**: +5 filename trigger, +4 section pattern, +3 layout match, +1-2 features

### Feature Display in Prompt
Show counts for actionable context:
```
Detected: multi-column layout, 12 pages
Contains: 15 tables, 8 figures, formulas
```

### Default Mode Selection
- If tables/figures/equations/multi-column detected → default to "accurate"
- Simple text-only document → default to "fast"

### Non-TTY / Batch Behavior
- Auto-detect non-interactive environment (`not sys.stdin.isatty()`)
- Auto-fallback to "auto" mode with logged warning:
  `WARN: Non-interactive environment. Using auto mode for: paper.pdf`
- `--no-interactive` flag available for explicit control

### Agent-Friendly Output
- Add `--profile-only` flag: runs s00 only, returns flat JSON with profile + recommendation
- All output should be agent-friendly (flat structure, not deeply nested)
- Example: `{"preset": "arxiv", "confidence": 12, "tables": 15, "figures": 8, "has_formulas": true, "recommended_mode": "accurate"}`

### Preset List in Prompt
- Dynamically read from PRESET_REGISTRY
- Always include "auto" and "fast" options
- Show recommended default based on s00 analysis

### Error Handling
- Corrupt PDF: Log error, skip file, continue batch iteration
- s00 failure: Fall back to interactive prompt (or auto mode if non-TTY)
- Extraction failure: Provide actionable guidance (check env vars, try --fast, etc.)

### Batch Report Format
- JSON format with flat structure (agent-friendly)
- Includes: batch_id, totals, per-file results, aggregates, arango_ids
- Written to `batch_report.json` in output dir
- `--report summary` option for human-readable output

### Downstream Skill Integration

**Memory-First Pattern**: Extracted content must be queryable via `memory/recall`:
- After extraction, agent can ask: "What tables did paper.pdf contain?"
- `memory/recall --q "tables in paper.pdf"` → returns extracted table summaries

**Integration points:**
- **memory/learn**: After successful extraction, auto-learn key facts:
  ```bash
  # Automatic after extraction:
  memory/run.sh learn \
    --problem "What is in paper.pdf?" \
    --solution "12 sections, 5 tables, 8 figures. Key topics: [detected from s00]"
  ```
- **doc-to-qra**: Each result includes `markdown_path` for Q&A generation
- **edge-verifier**: Each result includes `arango_id` for knowledge graph linking
- **episodic-archiver**: `--archive` flag stores extraction session for recall

**Typical agent workflow:**
```bash
# 1. Extract batch of PDFs
./extractor/run.sh ./pdfs/ --out ./extracted/

# 2. Content is now queryable via memory:
./memory/run.sh recall --q "tables in paper.pdf"

# 3. Optional: Generate Q&A pairs for deeper recall
./doc-to-qra/run.sh ./extracted/batch_report.json research

# 4. Optional: Link to knowledge graph
./edge-verifier/run.sh --batch ./extracted/batch_report.json
```

**User/Agent Q&A flow:**
```
User: "What did we extract from the engineering specs?"
Agent: [calls memory/recall --q "extracted engineering specs"]
Agent: "We extracted 3 PDFs with 45 requirements, 12 tables, and 8 figures.
        The main topics were: flight control, navigation, safety systems."
```

### LLM-Verified Edge Creation
- **Purpose**: Enable multi-hop graph traversal within and across documents
- **Uses**: `scillm.batch.parallel_acompletions_iter` with `custom_llm_provider="openai_like"`
- **Edge types**: references, implements, contradicts, extends, related
- **Candidate generation**: KNN/embedding similarity to find potential pairs
- **Verification**: LLM classifies relationship with confidence score
- **Storage**: Verified edges stored in ArangoDB `document_edges` collection

**Flags:**
- `--verify-edges` (default: True for accurate mode, False for fast)
- `--edge-scope intra|cross|both` (default: intra)

**Multi-hop query example:**
```
Query: "What requirements relate to safety tables?"
Graph traversal:
  requirements --references--> tables --tagged--> safety
Result:
  REQ-042 → Table 7 (Safety Metrics)
  REQ-089 → Table 12 (Failure Modes)
  REQ-103 → Table 15 (Risk Assessment)
```
