# cli_mini Integration Guide (Lean 4 Prover) for Extractor Pipeline

This guide explains how the extractor pipeline invokes the Lean 4 CLI mini orchestrator (cli_mini) to turn natural language requirements into compiled Lean 4 proofs with clear, machine‑readable outputs.

## Summary

- Entry: `python -m lean4_prover` (or console script `lean4-prover`)
- Commands: `suggest`, `run`, `batch`
- Outputs: JSON to stdout (parse `success` key); exit code is 0 (by design)
- Concurrency: Bounded; batch uses a global compile pool
- Optional preflight disambiguation: `--disambiguate` (with `--convention range|Icc` for classic range ambiguity)

## Prerequisites

- Docker container: `lean_runner` running a Lean 4 + Mathlib project at `/workspace/mathlib_project` (must include a lakefile). The CLI will auto‑start the container if it’s stopped.
- LLM provider via LiteLLM:
  - OpenAI: set `OPENAI_API_KEY`
  - Ollama: set `LITELLM_MODEL` or `LEAN4_MODEL` to `ollama/<model>` and `OLLAMA_BASE_URL`
- Caching (recommended): Redis if available; otherwise in‑memory (auto)
- UTF‑8 environment: Lean code uses Unicode (∑, ℕ, …)

## Installation

- In the lean4_prover repo:
  - `pip install -e .` (console scripts `lean4-prover`, `lean4-agent` will point to cli_mini)
  - Or call module directly: `python -m lean4_prover`

## Commands

- ### suggest
  - Purpose: Return 1–3 strategy names (no code generation or compile)
  - Example:
    - `python -m lean4_prover suggest "Prove that sqrt(x)^2 = x for x ≥ 0"`
    - Output (JSON): `["direct","structured"]` (example)

- ### run
  - Purpose: Generate → compile → optionally refine and pick best candidate
  - Common flags:
    - `--strategies "direct,structured,computational"`
    - `--max-refinements 2` (original + 2 refinements per strategy)
    - `--max-workers 8` (caps concurrency; 0=auto)
    - `--best-of` (selector picks the best compiled candidate)
    - `--disambiguate` (preflight: heuristics + LLM; skip ambiguous)
    - `--convention range|Icc` (for “first n naturals”: 0..n−1 or 1..n)
  - Example:
    - `python -m lean4_prover run "Prove that the sum of the first 100 natural numbers equals 4950." --disambiguate --convention range --max-refinements 2 --max-workers 6`

- ### batch
  - Purpose: Process a JSON list of items concurrently
  - Per-item overrides:
    - `strategies`, `max_refinements`, `workers`, `model`, `container`, `best_of`, `convention`, `try_both_conventions`
  - Important: Batch uses a global compile pool to cap total concurrency across items. Per‑item `workers` is ignored in this mode (by design).
  - Example:
    - Input JSON:
      ```json
      [
        {"requirement": "Prove that sqrt(x)^2 = x for x ≥ 0", "strategies": ["direct","computational"]},
        {"requirement": "Prove that the sum of the first 100 natural numbers equals 4950.", "convention": "range"}
      ]
      ```
    - Command:
      - `python -m lean4_prover batch -i /path/to/requirements.json --max-workers 8 --report`

## Output Contract (parse stdout JSON)

- run (success case, keys of interest):
  - `success: true`
  - `chosen: { item, rc, stdout, stderr, feedback[], attempt, strategy, compile_ms, [final_code?] }`
  - `compiled: [same shape as chosen]`
  - `failed: [ ... ]` (failed attempts with diagnostics)

- run (ambiguous with `--disambiguate`):
  - `success: false`
  - `needs_clarification: true`
  - `clarification_message: "<why>"`
  - optional: `heuristics`, `disambiguation_llm`, `interpretation`

- batch:
  - Array of per‑item outputs (each object shaped like `run` response)
  - Optional Markdown report when `--report` is set

Note: Process exit code is always 0; branch on the JSON `success` field.

## Disambiguation

- `--disambiguate`: Runs a preflight disambiguation (cheap heuristics + LLM). Ambiguous items are flagged and skipped from compilation with a rationale; your pipeline can route them back for clarification.
- Classic range ambiguity (“first n naturals”):
  - `--convention range` → 0..n−1
  - `--convention Icc` → 1..n

## Concurrency & Pooling

- Single run: `--max-workers` bounds compilation concurrency for that item.
- Batch: A global compile pool caps total concurrent compiles across all items; per‑item `workers` are ignored here. This prevents oversubscription and Docker thrashing.

## Recommended Flags for Extractor

- Balanced throughput:
  - `--max-workers 8` (or auto) and `--max-refinements 2`
  - `--best-of` when clarity matters
- Noisy requirements:
  - `--disambiguate` (and `--convention range` for classic range ambiguity)
- Batch: `--report` for auditing

## Python Integration Snippet (Extractor)

- Single item:

```python
import json, subprocess

cmd = [
    "python", "-m", "lean4_prover", "run",
    "Prove that sqrt(x)^2 = x for x ≥ 0",
    "--max-refinements", "2",
    "--max-workers", "6",
]
res = subprocess.run(cmd, capture_output=True, text=True)
data = json.loads(res.stdout)
if data.get("success"):
    chosen = data.get("chosen", {})
    print("Compile ms:", chosen.get("compile_ms"))
    print("Strategy:", chosen.get("strategy"))
    print("Lean code:", chosen.get("item", {}).get("lean"))
else:
    if data.get("needs_clarification"):
        print("Ambiguous:", data.get("clarification_message"))
    else:
        print("Failed:", data.get("error") or data)
```

- Batch:

```python
import json, subprocess, tempfile, os

items = [
  {"requirement": "Prove that sqrt(x)^2 = x for x ≥ 0", "strategies": ["direct","computational"]},
  {"requirement": "Prove that the sum of the first 100 natural numbers equals 4950.", "convention": "range"}
]
with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
    json.dump(items, f)
    f.flush()
    cmd = ["python", "-m", "lean4_prover", "batch", "-i", f.name, "--max-workers", "8", "--report"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(f.name)

results = json.loads(res.stdout)
for r in results:
    if r.get("success"):
        print("OK:", r.get("requirement"))
    elif r.get("needs_clarification"):
        print("Ambiguous:", r.get("clarification_message"))
    else:
        print("Failed:", r.get("requirement"), "->", r.get("error"))
```

## Troubleshooting

- Docker not found or lakefile missing:
  - Ensure container `lean_runner` exists and project lives at `/workspace/mathlib_project` (with a lakefile).
- LLM provider issues:
  - Confirm `OPENAI_API_KEY` or Ollama is set; Redis caching can reduce flakiness.
- Ambiguity trips:
  - Use `--disambiguate` and optional `--convention` to resolve classic cases.

## Stability & Versioning

- CLI commands and JSON shapes are stable for external use (`suggest`, `run`, `batch`).
- Batch concurrency uses a global compile pool for safety (documented behavior).
- Exit codes remain 0; parse `success` to branch. If you prefer nonzero exit on failure, a `--fail-on-error` flag can be added by request.

