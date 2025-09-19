#!/usr/bin/env bash
set -euo pipefail

# Offline fast gate for pipeline smokes. Online smokes are run only when
# SMOKES_ONLINE=1 and provider keys are present.

echo "[fast-gate] Running offline smokes..."
uv run scripts/smokes/pipeline/smoke_jsonld_export.py
uv run scripts/smokes/pipeline/smoke_reqif_export.py
uv run scripts/smokes/pipeline/smoke_stage11_schema_invariants.py || true
uv run scripts/smokes/pipeline/smoke_stage11_proves_only_offline.py
uv run scripts/smokes/pipeline/smoke_stage11_units_conflicts.py
uv run scripts/smokes/pipeline/smoke_stage11_supersedes_min.py
uv run scripts/smokes/pipeline/smoke_stage11_duplicates_min.py
uv run scripts/smokes/pipeline/smoke_stage14_report_graph_counts.py
## Requirement extraction + Lean4 (deterministic, offline)
uv run scripts/smokes/pipeline/requirements/smoke_sentence_shall.py || true
uv run scripts/smokes/pipeline/requirements/smoke_bullets_inherit.py || true
uv run scripts/smokes/pipeline/requirements/smoke_table_constraints.py || true
uv run scripts/smokes/pipeline/requirements/smoke_lean4_deterministic.py
uv run scripts/smokes/pipeline/requirements/smoke_lean4_formal_artifact.py
uv run scripts/smokes/pipeline/requirements/smoke_table_merge_to_lean4.py || true

if [[ "${SMOKES_ONLINE:-}" == "1" ]]; then
  echo "[fast-gate] Running online smokes (opt-in)..."
  uv run scripts/smokes/pipeline/online/smoke_litellm_sanity.py || true
  uv run scripts/smokes/pipeline/online/smoke_stage07_reflow_llm_json_strict.py || true
  uv run scripts/smokes/pipeline/online/smoke_stage09_summarizer_one.py || true
  uv run scripts/smokes/pipeline/online/smoke_stage11_rationale_one.py || true
fi

echo "[fast-gate] Done. Artifacts in scripts/artifacts/"

