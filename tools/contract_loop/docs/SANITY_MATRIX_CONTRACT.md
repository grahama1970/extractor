# Contract Loop Sanity Matrix (Module-Level)

These checks validate the **contract_loop** module itself, independent of any
project-specific pipeline. They must pass before the loop runs or before a new
adapter is added.

| Command | Purpose |
| --- | --- |
| `uv run tools/contract_loop/scripts/sanity_contract_auth.py` | Confirms Codex OAuth auth file exists. |
| `uv run tools/contract_loop/scripts/sanity_contract_exec.py` | Verifies Codex exec JSON harness + schema enforcement. |
| `uv run tools/contract_loop/scripts/sanity_contract_bundle.py` | Ensures bundle creation + guardrails work on a synthetic fixture. |
| `uv run tools/contract_loop/scripts/sanity_contract_clarify.py` | Confirms clarifying UI server responds with question payloads. |

Project-specific sanity matrices live under each adapter, for example:
`tools/contract_loop/adapters/extractor/docs/SANITY_MATRIX.md`.
