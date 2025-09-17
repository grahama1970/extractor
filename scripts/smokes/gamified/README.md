# Gamified Smokes (CLI)

This folder contains standalone smoke scripts for the prompt‑driven "gamified" orchestrator. They mirror the pytest smokes under `tests/smoke/gamified`, but are convenient to run locally or from CI via Makefile.

Smokes:
- contracts_smoke.py — validates schema contracts (delegates to pytest)
- emit_aggregate_smoke.py — emit instance prompts, synthesize minimal iter_01.json, aggregate and print winner
- prompt_contract_smoke.py — emit prompts and assert required prompt sections exist
- wait_here_timeout_smoke.py — run sequential with short timeouts and assert a scorecard is produced
- run_all.py — runs the above in order

Conventions:
- Uses `workspace/runs/<run_id>` for artifacts
- Never writes outside `workspace/`
- Prints concise pass/fail messages and exits non‑zero on failure
