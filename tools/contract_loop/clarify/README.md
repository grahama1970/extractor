# Clarify UI (Python Host + TUI)

This package hosts the structured clarifying questions used when a step
exhausts retries.

Files:
- `runner.py`: orchestration and timeout handling.
- `tui.py`: curses-style single-question prompt.
- `server.py`: temporary Flask server for multi-question forms.
- `types.py`: typed question/response models.

The Flask server serves the built assets from `tools/contract_loop/clarify-ui/dist`.
Build the UI with `tools/contract_loop/scripts/build_clarify_ui.sh`.
