# Extractor - Self-Correcting Agentic Document Processing System

Advanced multi-format document extraction system with self-correcting AI agents, annotation-guided learning, and continuous improvement through metadata accumulation. Handles PDFs, DOCX, PPTX, XML, HTML, and more with enterprise-grade accuracy. Includes a Lean4 integration path for deterministic proving and graph building (contradictions, dependencies, KNN neighborhoods) with an offline-friendly viewer.

## 🚀 Key Innovation: Self-Correcting Multi-Stage Pipeline

Unlike traditional extraction systems, this uses a **10-stage pipeline** where each stage contributes metadata, and AI agents make intelligent decisions based on accumulated knowledge:

```mermaid
graph LR
    PDF[Document Input] -->|Stage 1-3| Extract[Initial Extraction]
    Extract -->|Stage 4| Detect[Suspicious Detection]
    Detect -->|Stage 5| Enhance[JSON Enhancement]
    Enhance -->|Stage 6| Organize[Section Organization]
    Organize -->|Stage 7| Annotate[Annotation Matching]
    Annotate -->|Stage 8| Agent[AI Agent Enhancement]
    Agent -->|Stage 9| Validate[Gold Standard Validation]
    Validate -->|Stage 10| Learn[Pattern Learning]
    
    Learn -->|Knowledge Base| Extract
    
    style Agent fill:#f9f,stroke:#333,stroke-width:4px
    style Learn fill:#9f9,stroke:#333,stroke-width:2px
```

### The Magic: Metadata-Driven Enhancement

Each section accumulates metadata through the pipeline, including Surya confidence scores:

```json
{
  "section_id": "004",
  "metadata": {
    "extraction_confidence": {"stage1": 0.89, "stage3": 0.92},
    "surya_confidence": 0.99560546875,  // Neural network confidence
    "suspicious_blocks": [{"block_id": 4, "reason": "Low confidence table"}],
    "annotation_matches": [{"type": "FreeText", "content": "Merge Table"}],
    "knowledge_base_insights": {
      "similar_sections": [{
        "problem": "BHT table with split headers",
        "solution": "Camelot --lattice, then header fix",
        "outcome": "0.65 → 0.92 confidence"
      }]
    },
    "recommended_tools": [
      {
        "tool": "camelot_extractor",
        "command": "python camelot_extractor.py extract-tables doc.pdf --lattice",
        "expected_improvement": "0.67 → 0.90+"
      }
    ]
  }
}
```

**Result**: AI agents achieve 96% accuracy without knowing the expected outcome!

## 🎯 Quick Start

### Quick Sections Extraction (New)

Use the simplified pipeline to convert a PDF into a list of sections.

CLI:
```bash
# Extract sections and write outputs under data/results/pipeline
extract-sections data/input/pipeline/BHT_CV32A65X_marked.pdf -o data/results/pipeline

# Or via the legacy umbrella CLI (compat)
extractor-cli sections data/input/pipeline/BHT_CV32A65X_marked.pdf -o data/results/pipeline
```

Python API:
```python
from extractor.pipeline.api import extract_sections

sections, path = extract_sections("data/input/pipeline/BHT_CV32A65X_marked.pdf")
print(f"Sections: {len(sections)} at {path}")
```

### Basic Usage
```bash
# Extract any document with automatic format detection
python -m extractor document.pdf
python -m extractor presentation.pptx
python -m extractor report.docx

# With AI enhancement (requires API keys)
python -m extractor --enhance document.pdf

# Full pipeline with validation
python -m extractor --pipeline full document.pdf
```

### Python API
```python
from extractor import extract_document

# Simple extraction
result = extract_document("document.pdf")
print(result.text)

# With AI enhancement
result = extract_document("document.pdf", enhance=True)
print(f"Confidence: {result.metadata['confidence']}")
print(f"Fixes applied: {result.metadata['fixes_applied']}")
```

### Stock Validators (API/CLI)

- Easiest (one-liners):
  - API: `bash scripts/validate_api_local.sh`
  - CLI: `bash scripts/validate_cli_local.sh`

- API validator (manual version):
  - Start: `python -m uvicorn extractor.core.scripts.server:app --host 127.0.0.1 --port 8000`
  - Run: `python scripts/validate_api.py run --target http://127.0.0.1:8000 --tasks-file data/api_tasks.json`

- CLI validator (works standalone):
  - Run: `python scripts/validate_cli.py run --tasks-file data/cli_tasks.json --cwd .`

Notes:
- Sample tasks live in `data/api_tasks.json` and `data/cli_tasks.json`.
- The `run` subcommand is optional — both `... run --opts` and `--opts` forms work.
 - VS Code: run via “Tasks: Run Task” → `Run: Validators (API+CLI)` (also bound as the default Build Task: “Tasks: Run Build Task”).
 - Terminal: `make validate-all` (or run each: `make validate-api`, `make validate-cli`).

## Lean4 Graph (Contradictions, Dependencies, KNN)

To build the graph from Lean4 outputs and visualize it offline:

1) Produce Lean4 artifacts (from Lean4 repo):
```bash
python -m lean4_prover.cli_mini batch \
  --input-file in.json --output-file out.json \
  --deterministic --no-llm \
  --emit-edge-hints edge_hints.json
```

2) One‑click graph build (this repo):
```bash
export ARANGODB_URL=http://localhost:8529
export ARANGODB_USERNAME=root
export ARANGODB_PASSWORD=…
make graph-oneclick DB=lean4_prod HINTS=edge_hints.json
# Or, using Stage 10 flattened JSON with lemma pass-through:
uv run scripts/pipeline/stage10_pass_through_lemmas.py out.json flat10.json
make graph-oneclick DB=lean4_prod FLAT10=flat10.json
```

3) Viewer (self-contained):
```bash
# Prepare viewer JSON
make graph-viewer-prepare SRC=edge_hints.json   # or SRC=edges.json or SRC=docgen4.json
# Render static HTML
make graph-viewer-render JSON=graph.json
# Open viewer.html in a browser
```

Extras
- Emit DB-native edges (audit/bulk import):
  - `make graph-emit-db-edges HINTS=edge_hints.json OUT=db_edges.json`
- Metrics JSON:
  - `make graph-metrics DB=lean4_prod`

## 🏗️ Architecture: 10-Stage Self-Correcting Pipeline

Note on I/O policy:
- Stages 01–09 run offline-only and are designed to be deterministic, testable, and CI-friendly.
- All database I/O (e.g., ArangoDB reads/writes, graph operations) is deferred to stages 10–12.


### Stage 1-3: Initial Extraction
- **Stage 1**: Extract annotations (human guidance)
- **Stage 2**: Clean document (remove noise)
- **Stage 3**: Marker/native extraction

### Stage 4-5: Suspicious Detection & Enhancement
- **Stage 4**: Detect suspicious blocks (80%+ flagged)
- **Stage 5**: Create enhanced JSON with metadata

### Stage 6-7: Organization & Annotation Matching
- **Stage 6**: Organize into hierarchical sections
- **Stage 7**: Match annotations to content blocks

### Stage 8: AI Agent Enhancement ⭐
This is where the magic happens:

1. **Metadata Enrichment**: Each section gets comprehensive metadata
2. **Tool Recommendations**: Pre-computed based on issues detected
3. **Historical Patterns**: Similar fixes that worked before
4. **Visual Assets**: Pre-generated images for validation

The AI agent processes sections with this rich context:

```python
# Agent sees this metadata
{
  "agent_notes": {
    "summary": "BHT section with split header and low-quality table",
    "complexity": "medium",
    "recommended_approach": "Follow high-priority tools in order"
  },
  "recommended_tools": [
    {"tool": "text_cleaning", "reason": "Split header detected"},
    {"tool": "camelot_extractor", "reason": "Low table confidence"}
  ]
}

# Agent executes intelligently
✓ Merged split header: "4.1.5.4. BHT (Branch History Table) submodule"
✓ Extracted table with Camelot: confidence 0.67 → 0.91
✓ Merged table across pages: 8 rows total
✓ Achieved 96% match to gold standard
```

### Stage 9-10: Validation & Learning
- **Stage 9**: Validate against gold standards
- **Stage 10**: Store successful patterns for future use

## 🔒 Enterprise Security Features

### Path Security
- ✅ Path traversal prevention with allowed directory whitelist
- ✅ Symbolic link resolution
- ✅ File type validation

### Resource Protection
- ✅ Configurable limits (file size, pages, processing time)
- ✅ Memory-efficient streaming for large documents
- ✅ Timeout protection with graceful degradation

### Data Security
- ✅ Comprehensive Unicode sanitization
- ✅ SQL injection prevention (parameterized queries)
- ✅ Input validation at every stage

### Configuration
```python
# config.py
class ExtractionConfig(BaseSettings):
    max_file_size_mb: int = 100
    max_pages: int = 1000
    processing_timeout_sec: int = 300
    allowed_dirs: List[Path] = ["/safe/path"]
```

## 📊 Supported Formats

| Format | Method | Features | Performance |
|--------|--------|----------|-------------|
| **PDF** | Marker + AI | Full extraction with tables, images, layout | ~5-30s/page |
| **DOCX** | Native XML | Preserves styles, tables, images | <0.1s/page |
| **PPTX** | Native XML | Slides, notes, embedded content | <0.2s/slide |
| **HTML** | BeautifulSoup | Clean text, structure preservation | <0.1s/page |
| **XML** | Native parser | Full structure, namespace support | <0.05s/MB |
| **EPUB** | Native | Chapters, metadata, images | <1s/book |
| **Images** | OCR (Surya) | Text extraction from PNG/JPG | ~2s/image |

## 🧠 AI Enhancement Features

### Automatic Improvements
- **Split Header Merging**: "4.1.5.4. BHT (Branch History" + "Table) submodule"
- **Table Structure Repair**: "Descripti|on" → "Description"
- **Cross-Page Content**: Tables/lists continuing across pages
- **Block Reclassification**: Text incorrectly marked as headers
- **Figure Caption Generation**: Contextual descriptions
- **Confidence Scoring**: Every block includes Surya neural network confidence (0.0-1.0)

### Lean4 Theorem Proving Conversion
Convert technical specifications and mathematical documents to formal Lean4 code:

```bash
# Convert PDF to Lean4 theorems
python -m extractor.pipeline.poc_simplified.lean4_converter technical_spec.pdf

# Example output


## 🤖 LLM Router CLI (litellm_call)

Call any LiteLLM‑supported model (OpenAI/Anthropic/Gemini/Ollama, etc.) with automatic image handling and optional JSON wrapping.

Quick install: the console script `litellm-call` is provided by this package (see `pyproject.toml`).

Basic usage:
```bash
# Simple text
litellm-call "What is 2+2?"

# Enforce JSON + include usage/cost metadata when available
litellm-call --json "Return only {\"ok\":true}"

# Multiple prompts in one go
litellm-call "Capital of France?" "Largest ocean?"

# Fan-out across multiple models (prefixes results with model by default)
litellm-call --models openai/gpt-4o-mini,gemini/gemini-2.5-flash "Say hi"

# Read prompts from a file (one per line) or JSONL
litellm-call @prompts.txt
litellm-call --jsonl @prompts.jsonl

# Stdin
echo "What is 2+2?" | litellm-call --stdin

# Images: local path or remote URL inside the text; images are auto-detected
litellm-call "What’s in this image? data/samples/panda.png https://example.com/cat.jpg"

# Session, progress, and output control
litellm-call --session-id dev-123 --no-progress --output results.txt --quiet "Hello"
```

Key options:
- `--json`: shorthand for `--response-format json_object` and `--wrap-json`. Non‑JSON output is wrapped like `{ content, metadata }`.
- `--models`: Comma‑separated list for one‑prompt → many‑models fan‑out.
- `--prefix-model/--no-prefix-model`: Prefix each line with `[model]` when using `--models` (defaults to on).
- `--image-cache-dir`: Persist image compression/downloads between runs.
- `--session-id`: Attaches a `user`/session identifier to provider calls when supported.
- `--no-progress`: Disables the progress bar (auto‑disabled for single non‑stream calls).
- `--output/-o` + `--quiet`: Append results to a file and suppress stdout.
- `--stream`: Streams plain text for a single prompt (no JSON augmentation).

### Python helper

The quickest way to call a model from your code:

```python
import asyncio
from extractor.pipeline.utils.litellm_call import llm

async def main():
    # JSON enforced
    s = await llm('Return only {"ok":true}', model='openai/gpt-4o-mini', json=True)
    print(s)

    # With an image
    t = await llm('Describe this image', image='data/samples/panda.png', model='gemini/gemini-2.5-flash')
    print(t)

asyncio.run(main())
```
/-- Branch History Table specification -/
structure BHT where
  clk_i : Signal  -- Clock input
  counter : Fin 4 -- 2-bit saturating counter
```

Features:
- **Process-Driven Autoformalization (PDA)**: Uses compiler feedback for iterative refinement
- **Pattern Recognition**: Identifies hardware specs, timing constraints, state machines
- **Multi-hop Dependencies**: Resolves cross-section theorem references
- **Knowledge Integration**: Learns from successful conversions

### Knowledge-Based Learning
Every extraction improves future ones:

```python
# System learns from annotations
annotation = {"type": "Square", "content": "4.1.5.4. BHT..."}
→ Pattern: "Square marks section headers with numbering"
→ Future: Auto-classify similar patterns

# System learns from fixes
fix = {"problem": "Split table header", "solution": "Camelot --lattice"}
→ Success rate: 0.96
→ Future: Apply same fix to similar tables
```

## 🔧 Installation

### Basic Installation
```bash
pip install -e .

# For development
pip install -e ".[dev]"
```

### Optional Dependencies
```bash
# For AI features
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"

# For Knowledge Base
docker run -d -p 8529:8529 arangodb:latest
```

## 📈 Performance Metrics

### Extraction Accuracy
- **Without AI**: 75-85% accuracy
- **With AI Enhancement**: 94-98% accuracy
- **With Annotations**: 96-99% accuracy

### Processing Speed
- **Text-only documents**: 0.5-2 seconds
- **Complex PDFs**: 10-60 seconds
- **With full AI enhancement**: +50-200% time

### Real Example Results
```json
{
  "document": "BHT_technical_spec.pdf",
  "pages": 24,
  "processing_time": "45.2s",
  "fixes_applied": 12,
  "accuracy": {
    "before": 0.72,
    "after": 0.96
  },
  "confidence_metrics": {
    "average_surya_confidence": 0.945,
    "blocks_below_threshold": 3,
    "confidence_after_fixes": 0.982
  },
  "improvements": [
    "Merged 3 split headers",
    "Fixed 2 split tables",
    "Corrected 7 misclassified blocks",
    "All blocks now have Surya confidence scores"
  ]
}
```

## 🚀 Advanced Usage

### LLM Batch Calls (codex_call + litellm_call)
- Canonical input: JSONL (one JSON object per line).
- Fields per item:
  - "text": user prompt (required)
  - "image": optional local path or URL (litellm_call compresses/encodes automatically)
  - "model": optional per-item model override (otherwise environment defaults)
  - Any provider-specific parameters you add are passed through to the API (e.g., temperature, response_format, reasoning), but are only sent if you include them.
- Reasoning mapping:
  - codex_call: `--reasoning low` adds only `model_reasoning_effort: "low"` to each JSONL item.
  - litellm_call: forwards any user-specified fields; it does not invent reasoning unless you include it in your JSONL.

Example JSONL (data/demos/codex_call_demo_simple.jsonl)

Also see a more complex set: data/demos/codex_call_demo_medium.jsonl (mix of images, remote URLs, and provider params like temperature/top_p).
{"text": "What is 2+2?", "model": "gpt-5"}
{"text": "What is the capital of France?", "model": "gpt-5"}
{"text": "Describe this image.", "image": "data/images/table.png", "model": "gpt-5"}
{"text": "List three prime numbers under 20.", "model": "gpt-5"}
{"text": "Explain JSON Lines (JSONL) in one sentence.", "model": "gpt-5"}

Run via Codex (exec path):
- `cat data/demos/codex_call_demo_simple.jsonl | python src/extractor/pipeline/utils/codex_call.py --stdin --jsonl --codex-bin codex`
- Add minimal reasoning (Codex flag parity): `... --reasoning low` (adds `model_reasoning_effort: "low"` to each item).

Run via API (LiteLLM):
- `cat data/demos/codex_call_demo_simple.jsonl | python src/extractor/pipeline/utils/litellm_call.py --stdin --jsonl`
- To pass reasoning through the API, include it yourself in JSONL, e.g., {"reasoning": {"effort": "low"}}.


### Custom Pipeline Configuration
```python
from extractor import PipelineConfig, extract_document

config = PipelineConfig(
    stages=[1, 2, 3, 4, 8, 9],  # Skip some stages
    enable_ai=True,
    batch_size=5,  # Process 5 sections at once
    confidence_threshold=0.8
)

result = extract_document("document.pdf", config=config)
```

### Batch Processing
```python
from extractor import BatchProcessor

processor = BatchProcessor(max_workers=4)
results = processor.process_directory(
    "/documents",
    pattern="*.pdf",
    config={"enable_ai": True}
)
```

### Custom Workers
```python
from extractor.workers import BaseWorker

class CustomTableWorker(BaseWorker):
    def process(self, table_block):
        # Custom table processing logic
        return enhanced_table

# Register custom worker
extractor.register_worker("custom_table", CustomTableWorker)
```

## 🔌 Integration Examples

### With LangChain
```python
from langchain.document_loaders import ExtractorLoader

loader = ExtractorLoader("document.pdf", enable_ai=True)
documents = loader.load()
```

### With LlamaIndex
```python
from llama_index import ExtractorReader

reader = ExtractorReader()
documents = reader.load_data("document.pdf")
```

### REST API
```python
# Start API server
uvicorn extractor.api:app --reload

# Use API
POST /extract
{
  "file": "document.pdf",
  "enable_ai": true,
  "output_format": "markdown"
}
```

## 📊 Monitoring & Debugging

### Progress Tracking
```python
from extractor import extract_document

def progress_callback(stage, progress, message):
    print(f"Stage {stage}: {progress}% - {message}")

result = extract_document(
    "document.pdf",
    progress_callback=progress_callback
)
```

### Debug Mode
```bash
# Verbose logging
EXTRACTOR_LOG_LEVEL=DEBUG python -m extractor document.pdf

# Save intermediate outputs
python -m extractor --debug --save-intermediate document.pdf
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

### Key Areas for Contribution
- New format extractors (native implementations)
- Additional AI workers (math, code, diagrams)
- Language-specific improvements
- Performance optimizations

## 📝 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Built on top of excellent open-source projects:
- [Marker](https://github.com/VikParuchuri/marker) - PDF extraction
- [Surya](https://github.com/VikParuchuri/surya) - OCR and layout
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF manipulation
- [Camelot](https://github.com/camelot-dev/camelot) - Table extraction

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Worker Development](docs/WORKERS.md)
- [Security Guide](docs/SECURITY.md)
- [Performance Tuning](docs/PERFORMANCE.md)
- [Debuggable Typer CLI (VS Code friendly)](docs/03_guides/DEBUGGABLE_TYPER_CLI.md)
# 🧾 Stage 14: Report Generator (Run, Debug, Debug-Bundle)

Stage 14 aggregates all prior stage outputs into a final machine-readable JSON report (`final_report.json`) and a human-friendly Markdown report (`final_report.md`). It expects the standard pipeline results layout under `data/results/pipeline`.

CLI usage:

```bash
# Run (reads stage outputs under data/results/pipeline)
python -m extractor.pipeline.steps.14_report_generator run data/results/pipeline

# Debug (sanity mode; creates a temp dir and exercises error paths)
python -m extractor.pipeline.steps.14_report_generator debug

# Debug-bundle (materialize a one-shot bundle of stage outputs)
python -m extractor.pipeline.steps.14_report_generator debug-bundle bundle.json -o data/results/pipeline
```

Bundle format (minimal viable example):

```json
{
  "07_reflow_section": {
    "reflowed_sections": [
      {"title": "Intro", "level": 1, "reflow_status": "success", "reflowed": true, "text_chunks": [], "merged_tables": [], "ocr_corrections": {}}
    ]
  },
  "06_figure_extractor": {"figure_count": 0, "figures": []}
}
```

Outputs written to the results root:

- `final_report.json` (validated in CI using `schemas/final_report.schema.json`)
- `final_report.md` (headings and totals lightly snapshotted in tests)

Troubleshooting:

- If `final_report.json` is missing, ensure at least Stage 07 output is present (or use `debug-bundle`).
- If durations or metrics are `0`, some stages may not have emitted canonical JSON; see `14_report_generator/json_output/` for per-stage writes.
- The CLI respects `.env` if present, but does not require it; run fully offline.

## CI Quick Start (UX + Smokes)

- Prereqs:
  - Python venv + dev deps: `make setup`
  - Frontend deps: `cd prototypes/tabbed/html && npm ci`
- Start servers via VS Code Tasks:
  - `Prototype: Preview (0.0.0.0:8080)` or `Prototype: Dev (vite on 8080)`
  - `Backend: FastAPI (8000)` or the compound `Run: Backend + Preview`
- Start Chrome with CDP (if no Browserless):
  - Linux/macOS: `google-chrome --remote-debugging-port=9222`
  - macOS app path: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222`
- One command local CI:
  - `make ci`
  - Defaults: `BASE_URL=http://127.0.0.1:8080`, `CDP_URL=http://127.0.0.1:3000/json/version`
  - Override: `make ci BASE_URL=http://127.0.0.1:8080 CDP_URL=http://127.0.0.1:9222/json/version`
  - Stage 07 timeout (optional, CI): `export STAGE07_LLM_TIMEOUT=30`
- Health-only (CDP): `make ux-health`
- Full smokes (requires live servers + CDP): `make smokes`
- Single issue smoke: `make smoke-issue ISSUE=019` (or `020`)

Artifacts (logs + screenshots) are saved to `scripts/artifacts/`.
# Extractor
## Happy Path (single CLI)

- Primary command (all formats, minimal surface):
  - PDF (fast text-only):
    ```bash
    python -m src.cli extract /abs/input.pdf /abs/out --mode fast
    ```
  - PDF (accurate, normalized artifacts):
    ```bash
    uv pip install -e ".[accurate]"
    python -m src.cli extract /abs/input.pdf /abs/out --mode accurate
    ```
  - Structured (HTML/DOCX/PPTX/XLSX/EPUB/RST/XML/MD):
    ```bash
    python -m src.cli extract /abs/input.html /abs/out
    ```

- The unified CLI writes a stable envelope when the pipeline emits a `final_report.json`:
  ```json
  { "meta": {"pdf": "…", "results": "…", "mode": "fast|accurate", "took_ms": 1234}, "items": [], "errors": [] }
  ```

### Operator wrapper (optional)

- `pipeline-run` remains available for operator workflows and JSON envelopes:
  - Fast (deterministic):
    ```bash
    pipeline-run --pdf /abs/input.pdf --results /abs/out --mode fast --json
    ```
  - Accurate (install extras first):
    ```bash
    uv pip install -e ".[accurate]"
    pipeline-run --pdf /abs/input.pdf --results /abs/out --mode accurate --json
    ```

### Notes

- `pipeline-happy` and `pipeline-run-all` remain available but are considered aliases. Prefer the unified `python -m src.cli extract` surface.
- Heavy dependencies (torch/transformers/spaCy/FAISS/opencv/camelot/ocr) are optional in the `accurate` extra; the default install stays lean for CI and fast iteration.
