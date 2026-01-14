# Contract-Driven Data Pipelines: A Pattern for Robustness

**Status**: Recommended Pattern (supersedes "Ralph Wiggum")
**Problem Addressed**: Stale Data & Hollow Success in complex pipelines.

## The Observation

Traditional "Agentic Loops" (like the Ralph Wiggum pattern of "Try -> Check Exit Code -> Retry") work well for **stateless tasks** (e.g., visiting a website, writing a single function).

However, they fail catastrophically in **Data Pipelines** due to **State Persistence**:

1.  **Stale Data**: If Step N fails but a previous run's output exists, Step N+1 consumes old data, creating a "Zombie Pipeline".
2.  **Hollow Success**: A script can exit with `0` (Success) without doing any work (e.g., "Output file already exists, skipping").
3.  **Phantom Artifacts**: partial failures leave debris that confuse downstream steps.

## The Solution: Contract-Driven Execution

Instead of "Looping until it looks like it worked," we enforce **Strict Contracts** with **Clean Slate Execution**.

### 1. The Contract (`CONTRACT.md`)

A single source of truth defining the **Input/Output Schema** for every step.

- **Not just**: "Does execute?"
- **But**: "Does `pipeline.duckdb` contain > 0 rows in table `merged_content`?"

### 2. The Runner (Contract Loop)

A specialized orchestrator replaces generic loops.

- **Clean Slate**: **MUST** delete the output directory before starting. No incremental builds during verification.
- **Strict Sequence**: Run Step 1. Verify Contract 1. Only then run Step 2.
- **Fail Fast**: If _any_ data contract is violated, the pipeline halts immediately.

### 3. Verification Logic

Verification is not "asking the LLM if it looks okay." It is code:

```python
def verify_step_07(db_path):
    rows = db.execute("SELECT count(*) FROM merged_content").fetchone()[0]
    assert rows > 0, "Pipeline DB is empty! S07 failed silently."
```

## Comparison

| Feature            | Ralph Wiggum (Generic Loop)  | Contract-Driven (Data Pipeline)    |
| :----------------- | :--------------------------- | :--------------------------------- |
| **Success Metric** | Exit Code 0 + "I'm helping!" | Schema Compliance + Data Freshness |
| **State Handling** | Ad-hoc / Ignored             | **Clean Slate** (Wipe & Rebuild)   |
| **Failure Mode**   | "Hollow Success" (masked)    | "Fail Fast" (immediate red)        |
| **Best For**       | Web browsing, Coding tasks   | ETL, Data Ingestion, ML Pipelines  |

## Implementation

This pattern is implemented in `tools/contract_loop/verify_pipeline_contract.py`
and defined in `tools/contract_loop/adapters/extractor/docs/CONTRACT.md`.
