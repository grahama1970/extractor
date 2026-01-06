# Ralph Wiggum Postmortem & The Path Forward

**Status**: 🔴 Failed (Experiment Concluded) -> Pivoting to Contract-Driven Execution.

## 1. The Experiment

We attempted to solve "fragile pipelines" by implementing the "Ralph Wiggum Pattern":

> _"I'm helping!"_ — A loop that mistakenly thinks it's succeeding because it checks for _activity_ rather than _outcomes_.

The implementation (`ralph.sh`) ran the full pipeline (S01-S14) and verified exit codes.

## 2. The Failure Mode: "Hollow Success"

The experiment successfully demonstrated the problem it was meant to solve, but fell victim to it itself.

- **Observed**: `ralph.sh` exited with `0` (Success). It printed `✅ Ralph Pipeline Complete`.
- **Reality**: The Final Report showed **missing data**.
  - S01-S06: Extracted correctly (116 blocks, 4 tables).
  - S07 (DuckDB): Failed silently or failed to persist critical tables.
  - S14 (Report): Generated a report proving that the database stats were empty.

**Why?**
The verification checks were too shallow:

- Checked "Does file exist?" -> **Yes.**
- Failed to check "Is the content inside valid against the schema?"
- Relied on CLI wrappers (`s14_report_generator.py`) that swallowed exceptions or mismanaged paths.

## 3. The Pivot: Contract-Driven Execution

We are discarding "Ralph" (ad-hoc checks) for **Contracts** (Schema Enforcement).

**The Specs (`src/extractor/pipeline/steps/CONTRACT.md`):**
We already possess a rigorous specification for every step. We just aren't enforcing it.

| Step             | Contract (simplified)                                    |
| :--------------- | :------------------------------------------------------- |
| **S04 Sections** | JSON must contain `sections` list > 0 items.             |
| **S05 Tables**   | JSON must contain `tables` list.                         |
| **S07 DB**       | `merged_content` row count > 0 in DuckDB.                |
| **S14 Report**   | `statistics` key must be populated + `db_stats` present. |

**The New Plan:**

1.  **Contract Runner**: A script (e.g., `codex exec` loop) that runs a step.
2.  **Strict Validator**: After **every** step, it loads the output artifact and validates it against `CONTRACT.md`.
3.  **Clean Slate**: Run in a fresh, isolated state to prevent stale data (e.g., old DuckDB files) from masking failures.

## 4. Summary of Current State

- **Pipeline Code**: Mostly working (S01-S06 solid).
- **Orchestration**: Moving from `ralph.sh` (bash/ad-hoc) to Contract Enforcer.

## 5. Resolution and Codification

The problems identified here have been solved by the **Contract-Driven Data Pipeline** pattern.
See: [CONTRACT_DRIVEN_DATA_PIPELINES.md](file:///home/graham/.gemini/antigravity/brain/e798a01e-b43d-4bf8-8404-0a8308348507/CONTRACT_DRIVEN_DATA_PIPELINES.md)

**Key Wins:**

1.  **Clean Slate Enforced**: `run_contract_pipeline.py` wipes `data/results/pipeline_contract` before running.
2.  **Schema Validated**: S07 now verified to contain 20+ merged rows, not just a file on disk.
3.  **Bug Squashed**: The S07 silent failure (unreachable CLI code) was detected and fixed.
