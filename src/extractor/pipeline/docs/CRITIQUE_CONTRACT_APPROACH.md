# Critique: Gaps in the Contract-Driven Approach

**Current Status**: `run_contract_pipeline.py` works for _Full Runs_, but fails the "Easy for Agent to Iterate" criteria.

## 1. The "Global Wipe" Problem (Efficiency vs Correctness)

- **Current State**: `_clean_slate()` wipes the entire `data/results/pipeline_contract` directory.
- **Critique**: This is "Correct" but **Inefficient**. If an agent is fixing Stage 14 (Report), they must re-run S01-S13 (Expensive/Slow). This discourages frequent verification.
- **Risk**: Agents (and humans) will naturally bypass the runner to run `python -m s14...` directly to save time, immediately re-introducing the "Stale Data" risk (e.g., S14 using an old S07 DB).

## 2. The "Zombie Downstream" Risk (Stale Data)

- **Current State**: If we allow running a single step (Atomic Execution) without strictly managing dependencies, we get:
  - Run S05 (Table Extract).
  - Update S05 code.
  - Re-run S05.
  - S06 (Figure Extract) and S07 (DuckDB) **remain on disk** from the previous run.
- **Critique**: S07 is now "poisoned" because it contains data from the _old_ S05 run. S14 will report incorrect stats.
- **Requirement**: "Prevent stale data upstream and downstream."
  - **Upstream**: Must assert it exists and is fresh _enough_ (or just trusted).
  - **Downstream**: **MUST** be aggressively deleted when an upstream step is re-run.

## 3. Agent Ergonomics ("Easy to Verify")

- **Current State**: The runner is a monolith.
- **Critique**: An agent needs to say: _"I fixed S07. Run S07 and verify it, and ensure S08+ are invalidated."_
- **Missing Functionality**:
  - `--step <step_name>`: Run specific step.
  - **Auto-Invalidation**: Automatically `rm -rf` the outputs of Successor Steps.
  - **Pre-flight**: Check Predessor Steps exist.

## 4. The "Fresh Context" Loop (Non-Interactive)

- **Requirement**: "Help the agent iterate with fresh context... and if fail after N tries, ask human."
- **Strategy**:
  1.  **Agent Tool**: `run_step(step="s07")`.
  2.  **System Action**:
      - Checks S01-S06 exist.
      - **Deletes** S07 output (Local Clean Slate).
      - **Deletes** S08-S14 output (Downstream Clean Slate).
      - Runs S07.
      - Verifies S07 Contract.
  3.  **Result**: Returns `success=False, stderr="..."` to Agent.
  4.  **Agent Loop**: Agent reads stderr, patches code, calls `run_step("s07")` again.
  5.  **Termination**: If loop count > N, notify user.

## Proposed Architecture: The "Smart Runner"

We need to upgrade `run_contract_pipeline.py` to support **Atomic Steps with Cascading Invalidation**.

### Pipeline DAG Definition

We must hardcode the dependency graph to know what "Downstream" means.

```python
PIPELINE_DAG = [
    "01_annotation_processor",
    "02_marker_extractor",
    "03_suspicious_headers",
    "04_section_builder",
    ["04a_layout_audit"], # leaf/parallel
    "05_table_extractor",
    "05c_table_merger", # depends on 05
    "06_figure_extractor",
    "07_assemble_corpus", # depends on 04, 05c, 06
    "10_markdown_exporter",
    "14_report_generator"
]
```

### New CLI Specs

`python scripts/smart_runner.py --step 05c`

1.  **Identify Index**: 05c is index 6.
2.  **Invalidate**: `rm -rf` outputs for index 6 (05c) AND 7, 8, 9, 10...
3.  **Verify Upstream**: Check index 0-5 exist.
4.  **Run**: Execute 05c.
5.  **Verify**: Check 05c contract.
