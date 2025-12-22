# SciLLM / Chutes Quick Troubleshooting (2025-11-27)

What usually goes wrong
- Missing or unset Chutes env vars (`CHUTES_API_BASE`, `CHUTES_API_KEY`, `CHUTES_TEXT_MODEL`, `CHUTES_VLM_MODEL`).
- Local shims masking the real package (now removed: `src/scillm/`).
- Outdated scillm package lacking `scillm.completion/acompletion`.
- Conflicting `OPENAI_*` env vars causing wrong bearer headers.

Baseline checks
1) Load env:
   ```bash
   set -a && source .env && set +a
   ```
2) Verify package/version (expect 1.77.3 or newer):
   ```bash
   uv run python - <<'PY'
   import scillm
   import importlib.util
   print('scillm version:', getattr(scillm, '__version__', 'unknown'))
   print('has completion:', importlib.util.find_spec('scillm.completion') is not None)
   PY
   ```
3) Run the doctor:
   ```bash
   uv run python scripts/tools/scillm_quick_doctor.py
   ```
   Expect: `{"ok": true, ...}` and exit 0.

Common fixes
- If doctor says missing CHUTES_*: ensure they are in `.env` and re-source.
- If doctor says `scillm.completion unavailable`: reinstall scillm (no shim):
  ```bash
  uv pip install --upgrade scillm==1.77.3
  ```
- If bearer conflicts: unset OPENAI_* (doctor already does this), or clear them in your shell.
- If using editable `../litellm`: ensure that repo is up to date and includes `scillm/completion.py` and `scillm/acompletion.py`.

Upgrading to the latest scillm
- Note: `pyproject.toml` pins scillm to a file path (`scillm @ file:///home/graham/workspace/experiments/litellm`).
  That means uv/pip will re-install from that local path whenever deps are synced.
  To upgrade, update the local litellm repo and reinstall editable:
  ```bash
  uv pip install -e ../litellm
  ```
  Ensure the local repo is pulled to the latest tag/commit before installing.
  If/when we switch to a PyPI wheel in pyproject, `uv pip install --upgrade scillm`
  will apply; until then, the file:// path wins.

Pipeline sanity command
```bash
uv run python scripts/tools/scillm_quick_doctor.py && \
python -m src.cli data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  data/results/parity_runs/pdf --mode accurate
```

Notes
- 09a annotator is enabled in accurate runs; audit expects its outputs.
- If you see the shutdown warning `Task was destroyed but it is pending!`, it’s benign; file upstream if persistent.
- Keep scillm pinned to 1.77.3 (or newer official) to avoid regressions.
