# TODO: Prompt‑Driven Gamified Orchestration

Goal: Make the entire UX prompt‑first (Markdown), with N Codex instances iterating under internal rules until plateau, and a winner chosen from measurements.

Done
- Prompt file support (`--prompt` / `--prompt-file`) in `scripts/gamified.py`
- Backend/dashboard autostart
- Per‑variant agent with plateau detection (`scripts/variant_agent.py`)
- Tasks block (pre / per_variant / post) in prompt
- Scorecard generation and winner posting
- Deprecated legacy harness/JS orchestrator under `deprecated/`

Next
- Finalize Smokes + Contracts: enforce instance prompt, agent outputs, scorecard shapes
- Integrate asyncio runner (codex_call, deprecated) for children (done) and wire status CLI (done)
- Harden detach mode I/O and add CI smokes for emit→aggregate
- Document runbook and protected paths for agent edits
