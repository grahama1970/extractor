SciLLM Usage Contract (Extractor)

- Call SciLLM directly; no bespoke router/wrapper layers.
  - `from scillm import acompletion, parallel_acompletions, Router`.
  - For preflight/listing: `from scillm.paved import sanity_preflight, list_models_openai_like`.
- Pass `api_key` only; SciLLM sets correct headers for Chutes.
- Avoid stage‑local HTTP clients for `/chat/completions`.
- Prefer `parallel_acompletions(..., tenacious=True)` for batch probes.

If you need behavior SciLLM lacks, upstream it to SciLLM.

