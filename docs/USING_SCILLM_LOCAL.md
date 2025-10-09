Using a Local SciLLM Checkout with uv (Best Practice)

Goal
- Depend on your local SciLLM checkout (distribution: scillm; import name remains litellm) without committing machine‑specific paths, and keep CI reproducible.

Quick options
1) Editable install (fastest dev loop)

   ```bash
   uv add --editable /home/graham/workspace/experiments/litellm
   ```

   Live edits to your SciLLM repo are immediately reflected in the downstream venv.

2) PEP 508 direct file URL in pyproject (team‑friendly; lockable)

   ```toml
   [project]
   dependencies = [
     "scillm @ file:///home/graham/workspace/experiments/litellm"
   ]
   ```

   Then sync:

   ```bash
   uv sync
   ```

3) CI / staging (pin to branch or commit)

   ```toml
   [project]
   dependencies = [
     "scillm @ git+ssh://git@github.com/grahama1970/scillm.git@feat:final-polish"
   ]
   ```

   Or pin to a SHA for strict reproducibility.

What code imports look like

```python
from litellm import Router
r = Router(...)
```

CLIs installed
- scillm and scillm-proxy console scripts are placed on PATH.

Environment variables
- Prefer SCILLM_* vars (resolver still supports LITELLM_* fallback):
  - SCILLM_DEFAULT_MODEL
  - SCILLM_SMALL_VLM_MODEL / SCILLM_MED_VLM_MODEL / SCILLM_LARGE_VLM_MODEL
  - SCILLM_SMALL_TEXT_MODEL / SCILLM_MED_TEXT_MODEL / SCILLM_LARGE_TEXT_MODEL
  - Optional: SCILLM_VISION_MODEL (generic fallback if tiered VLM vars missing)

Notes
- Use three slashes in file URLs: `file:///home/...`.
- Avoid committing machine‑specific file URLs to shared branches; prefer the editable workflow for local dev and VCS URLs for CI.

