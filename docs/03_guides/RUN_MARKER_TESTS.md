# Running Marker Fork Tests

This project vendors a lightly amended fork of Marker-PDF under `src/extractor/core`.
The upstream Marker test suite should be run when updating the fork to ensure
behavioral parity and catch regressions.

## Prerequisites
- Clone upstream or your fork into `repos/marker` (already present in this repo).
- Python 3.10+ and a virtualenv (we use `uv` below).

## Quick Run
```bash
# From repo root
source .venv/bin/activate || (uv venv && source .venv/bin/activate)
uv pip install -e repos/marker[dev] || uv pip install -e repos/marker && uv pip install pytest
cd repos/marker
pytest -q
```

## Notes
- Keep the fork’s dependencies aligned with upstream. If upstream updates, re-pin
  versions as needed.
- Run these tests whenever core changes under `src/extractor/core` are made.
- Keep extractor’s own tests focused on the pipeline interface and a small set of
  “contract” checks against the forked core.
