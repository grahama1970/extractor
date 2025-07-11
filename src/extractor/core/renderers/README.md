# Renderers Module

**Role in Pipeline:** 🟢 *Crucial*

Renderers take a fully-populated `Document` model and emit the requested outward format:

| Renderer | Output | Status |
|----------|--------|--------|
| `markdown.py` | Markdown + image assets | stable |
| `html.py` | HTML document | stable |
| `json.py` | Flattened JSON blocks | stable |
| `hierarchical_json.py` | Nested JSON (sections/blocks) | beta |
| `arangodb_json.py` | ArangoDB import format | beta |

If you add a new renderer, remember to update `output.text_from_rendered()`.

Non-essential demo renderers or half-finished experiments should be moved to `archive/renderers/`.
