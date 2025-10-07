Debug Utilities
===============

This folder isolates quick probes and diagnostics so that the pipeline code stays clean.

How to run (uv-managed venv):

- Vision probe (Router vs litellm on .env VLM aliases)
  uv run python debug/vision_probe.py

- Router text JSON probe (sanity on a text model)
  uv run python debug/router_text_probe.py --model "$LITELLM_LARGE_TEXT_MODEL"

- Steps help sweep (verifies all step CLIs import and show --help)
  uv run python debug/steps_help.py

Notes
- Probes respect CHUTES_* and OPENAI_* env for gateway routing and use your .env by default.
- The vision probe generates an in-memory PNG and tries both SciLLM Router and direct litellm.

