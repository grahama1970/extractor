# Services Module

**Role in Pipeline:** ⚪ *Optional (AI features)*

This package wraps external LLM providers (Anthropic Claude, OpenAI, Google Vertex/Gemini, Ollama) via unified helper classes. It is only used when **Claude/LLM enhancements** are enabled in settings or CLI flags.

A plain heuristic PDF→JSON run **does not import this module**.

If you plan to run without LLM features, the entire directory can be moved to `archive/` to slim the install footprint. Otherwise keep.
