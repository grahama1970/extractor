# Providers Module

**Role in Pipeline:** ⚪ *Optional*

Adapters to external services (OCR engines, LLM calls, storage backends). Current sub-folders:

| Sub-dir | Purpose | Default Pipeline Dependency |
|---------|---------|----------------------------|
| `llm_call/` | Anthropic Claude helpers | No (AI features off by default) |
| `services/` | Third-party micro-services | No |

If running in *heuristic-only* mode, this directory is **not required** and can be archived, but keep it if you plan to enable AI enhancements.
