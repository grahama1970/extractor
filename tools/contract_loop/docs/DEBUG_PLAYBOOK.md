# Contract Loop Debug Playbook

**Goal:** Collaborate with the pipeline to fix broken steps without "hollow success" or state corruption.

## What is `--debug` mode?

When you run `verify_pipeline_contract.py --debug`, the loop enters a strict collaboration mode:

1.  **Enforced Hygiene**: It **forces** downstream cleaning and upstream reruns. Passing `--no-clean-downstream` or `--no-rerun-upstream` now errors immediately so you cannot accidentally disable hygiene.
2.  **Rich Logging**: `stdout` and `stderr` for every attempt stream to the console **and** are captured under `out/<step>/attempt_<n>/{stdout.log, stderr.log}`. Verification commands write under the same attempt directory so all evidence lives together.
3.  **Structured Clarifications**: When a step exhausts its retries, debug mode launches the clarifying UI. Single-question cases use a curses menu inline; multi-question cases launch a temporary Flask form (`http://127.0.0.1:<port>/`) that closes automatically after submission. Responses are saved to `out/clarifications/<step>/attempt_<n>.json` and recorded in `manifest.json`.
4.  **Debug Summary**: After the run, `out/debug.md` lists every attempt, status, log directory, and bundle pointer so humans can jump directly to evidence.
5.  **Collaboration Bundles**: Every failed attempt automatically zips the manifest, logs, judge outputs, clarifications, and other artifacts into `out/bundles/<step>_attempt_<n>.zip`. The CLI prints the relative path and the manifest records the bundle so humans can open it in VS Code instantly.
6.  **Verbose Output**: The console still streams logs in real-time; captured files are an additional audit trail, not a replacement.

## Usage

```bash
# Debug a specific step (e.g., table extraction)
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/my_doc.pdf \
  --start-step 05_table_extractor \
  --debug
```

## Where are my logs?

If step `05_table_extractor` fails on attempt 1:

- **Stdout**: `data/results/pipeline_contract/05_table_extractor/attempt_1/stdout.log`
- **Stderr**: `data/results/pipeline_contract/05_table_extractor/attempt_1/stderr.log`
- **Manifest**: `data/results/pipeline_contract/manifest.json` (contains timing and status)
- **Summary Table**: `data/results/pipeline_contract/debug.md` links every attempt + log path.
- **Bundle**: `data/results/pipeline_contract/bundles/05_table_extractor_attempt_1.zip` packages manifest, logs, judge outputs, and clarifications for that failed attempt.
- **Clarifications**: `data/results/pipeline_contract/clarifications/05_table_extractor/attempt_1.json` captures the structured answers from the curses/HTML UI when retries are exhausted.

## Bundle Guardrails

- Default thresholds: warn at 50 MB (`--bundle-warn-mb`) and fail at 100 MB (`--bundle-max-mb`).
- If a bundle would exceed the warning threshold, the CLI prints a ⚠️ line with the size; operators can raise the limit via CLI when necessary.
- If the bundle would exceed the max threshold, the run fails before writing to disk (so we never silently emit huge archives). Re-run with `--bundle-max-mb <value>` to override intentionally.

## Clarifying UI Tips

- Single-question flow: uses a curses selector (arrow keys + Enter) or fallback text input if the terminal lacks curses support.
- Multi-question flow: launches a Flask server bound to `127.0.0.1` on an ephemeral port and serves the React UI from `tools/contract_loop/clarify-ui/dist`. The CLI prints the URL; submit once and the server shuts down automatically.
- Responses live under `out/clarifications/<step>/attempt_<n>.json` and are bundled automatically.
- Timeout: default is 15 minutes (`--clarify-timeout`), after which the run exits with code 4. Increase the timeout on the CLI if you expect a longer review session.
- Editing the UI:
  - `tools/contract_loop/scripts/clarify_ui_dev.sh` — starts the Vite dev server (set `VITE_API_BASE` to point at a running contract-loop instance or mock API).
  - `tools/contract_loop/scripts/build_clarify_ui.sh` — rebuilds the production assets the Python server will serve.

## Troubleshooting

- **"Step failed after N attempts"**: The loop proved the code is broken. Check `stderr.log` for the traceback.
- **"Upstream step failed verification"**: The issue is earlier in the chain. Run with `--start-step <upstream>` to fix it first.
