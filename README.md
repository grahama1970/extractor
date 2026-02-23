# Extractor - Self-Correcting Agentic Document Processing System

Advanced multi-format document extraction system with self-correcting AI agents, annotation-guided learning, and continuous improvement through metadata accumulation. Handles PDFs, DOCX, PPTX, XML, HTML, and more with enterprise-grade accuracy.

## Quick Start

```bash
# Extract any document (auto-detects format and preset)
python -m extractor.pipeline paper.pdf --out results/

# Fast mode (no LLM, quick extraction)
python -m extractor.pipeline paper.pdf --mode fast

# Accurate mode (full LLM pipeline)
python -m extractor.pipeline paper.pdf --use-llm

# Force specific preset (skip auto-detection)
python -m extractor.pipeline paper.pdf --preset arxiv
```

## Complete Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT DOCUMENT                                  │
│                    (PDF, HTML, DOCX, XML, EPUB, PPTX, etc.)                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                     STAGE 00: PROFILE DETECTOR                               │
│  • Analyze: domain, layout, tables, formulas, requirements                   │
│  • Match preset: arxiv, requirements_spec, auto                              │
│  • Determine route: fast vs accurate                                         │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                     PDF EXTRACTION (STAGES 01-06)                            │
│                                                                              │
│  s01 annotation_processor   │  Strip/process PDF annotations                │
│  s02 marker_extractor       │  Extract blocks via Marker/pymupdf4llm        │
│  s03 suspicious_headers     │  VLM verification of headers                  │
│  s04 section_builder        │  Build hierarchical sections                  │
│  s04a layout_audit          │  Audit layout quality                         │
│  s05 table_extractor        │  Extract tables (Camelot)                     │
│  s05b table_describer       │  VLM descriptions for tables                  │
│  s05c table_merger          │  Merge & deduplicate tables                   │
│  s06 figure_extractor       │  Extract figures/images                       │
│  s06b figure_describer      │  VLM descriptions for figures                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                     COMMON STAGES (07-14)                                    │
│                                                                              │
│  s07 json_assembler         │  Assemble sections + tables + figures → JSON   │
│  s08 extract_requirements   │  Mine requirements (REQ-xxx, SHALL, MUST)     │
│  s08 lean4_theorem_prover   │  Formal proofs (scientific papers)            │
│  s09 section_summarizer     │  LLM summaries per section                    │
│  s10 markdown_exporter      │  Export to Markdown                           │
│  s10 arangodb_exporter      │  Sync to ArangoDB graph                       │
│  s14 report_generator       │  Generate extraction report                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                          PIPELINE OUTPUTS                                    │
│                                                                              │
│  pipeline.duckdb            │  Queryable structured data                    │
│  04_sections.json           │  Hierarchical sections                        │
│  05_tables.json             │  Extracted tables with descriptions           │
│  06_figures.json            │  Extracted figures with descriptions          │
│  08_requirements.json       │  Mined requirements                           │
│  document.md                │  Human-readable Markdown                      │
│  ArangoDB Graph             │  documents → sections → requirements          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Separation of Concerns

Extractor focuses on **structure extraction**. For knowledge generation (Q&A pairs), use the downstream skills:

```
EXTRACTOR (this project)     QRA SKILL (separate)        MEMORY SKILL (separate)
────────────────────────     ───────────────────         ────────────────────────
• Extract sections           • Generate Q&A pairs        • Store with embeddings
• Extract tables             • Validate grounding        • Search & recall
• Extract figures            • Domain-focused            • Learn patterns
• Extract requirements       • LLM-intensive
• Export to DB/MD

Output: Structured JSON      Output: Q&A pairs           Output: Searchable memory
Cost: Low (mostly offline)   Cost: High (LLM tokens)     Cost: Embedding
```

**Orchestration:** The `/distill` skill combines all three:

```bash
# One command: Extract → QRA → Memory
.pi/skills/distill/run.sh --file paper.pdf --scope research
```

## Supported Formats & Parity

Cross-format parity measured against HTML reference:

| Format       | Method                   | Parity    | Notes                            |
| ------------ | ------------------------ | --------- | -------------------------------- |
| **Markdown** | Direct parse             | 100%      | Perfect structural match         |
| **DOCX**     | Native XML (python-docx) | 100%      | Perfect structural match         |
| **HTML**     | BeautifulSoup            | Reference | Baseline for comparison          |
| **XML**      | defusedxml               | 90%       | Structure preserved              |
| **PDF**      | 14-stage pipeline        | 87%       | Varies by document complexity    |
| **RST**      | docutils                 | 85%       | Section structure varies         |
| **EPUB**     | ebooklib                 | 82%       | Chapter structure varies         |
| **PPTX**     | python-pptx              | 81%       | Slide-based structure            |
| **XLSX**     | openpyxl                 | 16%       | Expected (spreadsheet format)    |
| **Images**   | OCR/VLM                  | 16%       | Requires VLM for text extraction |

## ArangoDB Schema

```
s10_arangodb_exporter creates:

NODES (Vertices):
  documents/doc_{hash}     ← Root document node
  sections/sec_{hash}      ← Section nodes (hierarchical)
  requirements/req_{id}    ← Requirement nodes

EDGES:
  has_section: Document → Section
  has_section: Section → SubSection (hierarchy)
  has_requirement: Section → Requirement
```

## Presets

| Preset                | Detected When                                           | Features                         |
| --------------------- | ------------------------------------------------------- | -------------------------------- |
| **arxiv**             | Academic papers (2-column, math, "Abstract/References") | Full LLM pipeline, Lean4 proving |
| **requirements_spec** | Engineering specs (REQ-xxx, "Shall", nested sections)   | Requirements mining enabled      |
| **auto**              | Unknown documents                                       | Heuristic-based routing          |

## CLI Reference

```bash
# Basic extraction
python -m extractor.pipeline <pdf> --out <dir>

# Key flags
--preset <name>          # Force preset (arxiv, requirements_spec, auto)
--use-llm                # Enable LLM for improved accuracy
--offline-smoke          # Deterministic mode, no network calls
--skip-export            # Don't write to ArangoDB
--extract-requirements   # Mine requirements (s08)
--annotate-pdf           # Generate annotated PDF with overlays
--auto-ocr/--no-auto-ocr # Control scanned PDF handling
--skip-scanned           # Skip detected scanned PDFs
--ocr-lang <code(s)>     # Set OCR language (default: eng)


# Batch processing
python -m extractor.pipeline ./documents/ --out ./results --glob "**/*.pdf"
```

## Environment Variables

```bash
# Required for LLM stages
CHUTES_API_BASE=https://llm.chutes.ai/v1
CHUTES_API_KEY=<your-key>
CHUTES_VLM_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
CHUTES_TEXT_MODEL=moonshotai/Kimi-K2-Instruct-0905

# Required for ArangoDB export
ARANGO_HOST=http://localhost:8529
ARANGO_DB=extractor_graph
ARANGO_USER=root
ARANGO_PASSWORD=<password>

# Optional for Lean4 proving
SCILLM_API_BASE=http://localhost:8787/v1
```

## Project Structure

```
src/extractor/
├── core/
│   ├── presets.py           # Preset registry (arxiv, requirements_spec)
│   ├── providers/           # Format-specific extractors
│   │   ├── docx.py
│   │   ├── html.py
│   │   ├── epub.py
│   │   └── ...
│   └── schema/
│       └── unified_document.py
├── pipeline/
│   ├── run_pipeline.py      # Main orchestrator
│   └── steps/
│       ├── s00_profile_detector.py
│       ├── s01_annotation_processor.py
│       ├── s02_marker_extractor.py
│       └── ... (14+ stages)
└── tools/
    └── tasks_loop/
        ├── sanity/          # API sanity scripts
        └── tasks/           # Task files
```

## Related Skills (pi-mono)

| Skill         | Purpose                                |
| ------------- | -------------------------------------- |
| `/extractor`  | User-facing interface to this pipeline |
| `/distill`    | Extract → QRA → Memory (orchestrator)  |
| `/qra`        | Generate Q&A pairs from text           |
| `/doc-to-qra` | Document → Memory (simplified)         |
| `/memory`     | Store and recall knowledge             |

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
