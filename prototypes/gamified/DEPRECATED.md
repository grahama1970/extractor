Deprecated components (moved under `prototypes/gamified/deprecated/`).

These belonged to the earlier manifest/harness/JS-variants flow and are retained only for reference:

- `harness/` — manifest adapter and Node evaluator for title-case JS variants
- `variants/` — JS title-case examples
- `web/` — static logger demo page
- `tests/` — tests for the legacy harness flow
- `orchestrator_smoke.py` — JS-only orchestrator smoke

Use the prompt-driven CLI instead:

```
python scripts/gamified.py run \
  --prompt-file prototypes/gamified/docs/prompt_multiplication_poc.md \
  --codebase .
```

