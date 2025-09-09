# Proposed Simplified Project Structure

This proposal removes deep nesting and makes the active runtime paths obvious. It keeps the modified Marker extraction core and the simplified PDF→sections pipeline, while archiving legacy code.

## Recommendation (Option A: Code-only under `src/`)

- Keep package code under `src/extractor/` only.
- Move data assets (inputs, gold standards, results) to top-level `data/`.
- Keep tests at repo root `tests/`.

Proposed layout:

```
extractor/
├─ src/
│  └─ extractor/
│     ├─ core/                      # KEEP: modified Marker core
│     ├─ pipeline/                  # KEEP: flattened simplified pipeline
│     │  ├─ docs/
│     │  ├─ steps/
│     │  ├─ tools/                  # validators, small helpers
│     │  ├─ __init__.py
│     │  └─ api.py                  # thin wrapper: PDF → sections JSON
│     ├─ cli/                       # minimal CLI routing to core + pipeline
│     ├─ utils/                     # shared utilities (audited)
│     └─ __init__.py
├─ tests/                           # KEEP: all tests here (unit/integration)
├─ data/                            # NEW: non-package assets
│  ├─ input/
│  ├─ gold_standards/
│  └─ results/
├─ docs/                            # KEPT/REFRESHED: current docs
├─ .archive/
│  └─ deprecated/                   # organized legacy code & docs
└─ scripts/                         # dev utilities (kept ones only)
```

Why Option A:
- Packaging best practice: avoids shipping data in wheel, reduces install size.
- Clear separation of code vs. artifacts.
- CI/CD stays simple; tests remain discoverable under `tests/`.

## Alternative (Option B: All-in-one under `src/extractor/`)

Include `input/`, `gold_standards/`, `results/`, `test/` under `src/extractor/`. Not recommended for packaging:
- Data ships with the package; risks licensing/size issues.
- Test discovery conflicts; two test roots.
- Tooling (ruff/black/mypy) must filter non-code paths.

If demanded, place under `src/extractor/assets/` to reduce import collisions.

## Flattening `poc_simplified`

Current path: `src/extractor/pipeline/poc_simplified/pipeline/...`

Flatten to: `src/extractor/pipeline/...` with these mappings:
- `pipeline/docs/` → `src/extractor/pipeline/docs/`
- `pipeline/steps/` → `src/extractor/pipeline/steps/`
- `validate_gold_standard.py` → `src/extractor/pipeline/tools/validate_gold_standard.py`
- `pipeline/src/` (nested src) → eliminate; merge code into `src/extractor/pipeline/`
- `pipeline/gold_standards/` → `data/gold_standards/pipeline/`
- `gold_standard_output.json` → `data/results/gold_standard_output.json`
- `stage_*.log` → `logs/` or `data/results/logs/` (outside `src/`)

## CLI and Server alignment
- Ensure `extractor-cli` routes PDF→sections via `src/extractor/pipeline/api.py`.
- Keep FastAPI server under `src/extractor/core/scripts/server.py` (if serving core extraction). Add endpoint that proxies to sections pipeline if needed.

## Next actions
- Approve Option A (recommended) vs Option B.
- Execute Phase 4 (candidate moves) from the checklist after usage mapping.
- Update `pyproject.toml` scripts to the new paths.
- Refresh docs (Architecture, Deprecation Guide) and KEEP/ARCHIVE matrix.

