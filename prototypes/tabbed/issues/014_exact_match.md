## Issue
Location: /classic (Classic Three-Panel Layout) → Inspector panel (right)
Task: Add a toggle “Exact JSON Match” in the Inspector panel (right), below the “Generate JSON” controls, that enforces strict equality between the generated JSON and the annotated “Gold Standard Result” JSON. When enabled, any mismatch fails with a toast and does not overwrite the gold JSON. Non-blocking flow remains the only path.

## Context
Annotators can generate JSON for a selected region via the non‑blocking LLM flow. Today the output always opens in the JSON dialog. We need a mode to strictly validate the model’s output against the curated “Gold Standard Result” before allowing any overwrite.

## Desired Behavior
- Toggle labeled “Exact JSON Match” appears under the “Generate JSON” controls in the Inspector panel.
- When ON and user clicks “Generate JSON”:
  - Parse model JSON and the current JSON dialog contents (gold) and deep-compare for exact equality.
  - If equal: show success toast “Exact JSON Match passed”; do not open or overwrite JSON.
  - If not equal: show error toast “Exact JSON Match failed: mismatch”; do not open or overwrite JSON.
- When OFF: Existing behavior preserved (open JSON dialog with generated JSON).

## Acceptance
- [ ] A toggle labeled “Exact JSON Match” with data-testid `toggle-exact-json` appears under the “Generate JSON” controls.
- [ ] With toggle ON and a mismatch, a toast error appears and JSON is not overwritten (dialog remains as‑is).
- [ ] With toggle ON and an exact match, a toast success appears (and no unintended overwrites occur).
- [ ] With toggle OFF, current behavior is preserved.

## Routes
- /classic

## Selectors (if known)
- Toggle: `[data-testid="toggle-exact-json"]`
- Generate button: `[data-testid="btn-export-json"]` (JSON modal open) and Inspector “Generate JSON” button next to it
- JSON dialog textarea: `textarea` in the JSON Dialog
- LLM chip: `[data-testid="llm-chip"]`

## Smokes to add
- scripts/smokes/issue_014.mjs
  - Assert the “Exact JSON Match” text is present.
  - Assert clicking “Generate JSON” opens the JSON dialog (non‑blocking).

## Artifacts
- scripts/artifacts/issue_014_*.{log,png}

## Meta
- id: 014
- created_at: (auto)

Last_smoke_at: (pending)
Last_suite_at: (pending)
Status: Open
