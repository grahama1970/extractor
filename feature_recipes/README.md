# Feature Recipes

Feature recipes describe small, composable flows that scenarios can invoke.
They are intentionally deterministic and kept minimal so they can be reused by
both live scenarios and unit tests.

Recommended format:
- Short Python or Node modules with a single entrypoint function
- No network by default; accept explicit environment variables or parameters
- May export tiny data fixtures that tests in `tests/` can consume

Example ideas:
- `recipes/pdf_toolbar_check.py` — pure DOM selector and ordering rules
- `recipes/left_rail_modes.py` — compute expected labels for thumb modes

These modules should not write artifacts. Scenarios that call them are
responsible for artifact capture and logging.

