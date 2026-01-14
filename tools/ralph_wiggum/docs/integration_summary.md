**NOTE:** Legacy Ralph Wiggum loop documentation. Current contract-loop docs live under `tools/contract_loop/docs`.

# Ralph Wiggum Loop - Extractor Summary (Legacy)

The legacy Ralph Wiggum loop runs the extractor stages in order and performs
basic step verification where available. The canonical entrypoint is:

```bash
bash scripts/ralph.sh [optional_pdf_path]
```

What it does:

- Runs the pipeline steps in sequence (S01 through S14).
- Calls each step's `--verify-only` check where supported.
- Writes outputs under `data/results/pipeline_ralph_aligned`.

For strict, step-by-step convergence with contracts and LLM judging, use the
Contract Loop instead:

```bash
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode deterministic
```

The Contract Loop is the supported path for deterministic validation going forward.
