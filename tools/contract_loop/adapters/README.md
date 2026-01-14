# Contract Loop Adapters

Adapters map the generic contract loop onto a project-specific pipeline.

Contents:
- `base.py` defines the adapter interface and shared types.
- `extractor.py` is the adapter for this repo.
- `extractor/` holds extractor-specific docs, fixtures, and sanity config.

Adding a new adapter:
1. Create `tools/contract_loop/adapters/<project>.py`.
2. Create `tools/contract_loop/adapters/<project>/docs/CONTRACT.md`.
3. Add `tools/contract_loop/adapters/<project>/docs/GOAL.md` and fixtures.
4. Provide a `sanity_config.py` for the project matrix (if needed).
