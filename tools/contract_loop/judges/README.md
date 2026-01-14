# Judge Schemas

JSON schemas for structured Codex outputs and gate evaluations.

- `agent_task.schema.json`: task agent final response (strict JSON).
- `contract_gate.schema.json`: gate decision output (strict JSON).
- `contract_sanity.schema.json`: sanity check output (strict JSON).
- `llm_judge.schema.json`: pipeline LLM judge responses (strict JSON).

All schemas are strict (no extra keys) to keep downstream validation deterministic.
