# Project Context: Extractor + tasks_loop

## 🎯 Project Objective

The **Extractor** is a multi-stage pipeline designed to transform complex, technical PDFs into highly structured Markdown and JSON reports for LLM ingestion. The primary innovation is a **"Twin-Driven Development"** strategy: scanning real client PDFs to create synthetic "twins" for robust, private, and scalable testing.

---

## 🏗 Architecture Overview

The pipeline follows a **15-stage sequence** (S01-S14). Data transitions from raw PDF blocks to structured JSON artifacts, and finally into a **DuckDB database** which serves as the "source of truth" for enrichment and export.

### The "Spine": `merged_content` Table

Stage 07 (`s07_duckdb_ingest`) is the most critical architectural pivot. It assembles all prior artifacts into a linear reading order within DuckDB.

- **Table**: `merged_content`
- **Columns**: `id`, `section_id`, `page`, `type` (text, table, figure, requirement), `content`, `asset_id`, `sort_order`.
- **Ordering**: `sort_order = (page * 10000) + y0`. This logic determines the linear flow of the document.

### Crucial Step: S10 Markdown Exporter

Stage 10 converts the DuckDB corpus back into a **linear Markdown file**.

- **Why it's crucial**: This is the file eventually consumed by LLMs for global reasoning.
- **Aggregation**: It joins `merged_content` with `sections` (S04), `tables` (S05), `figures` (S06), `requirements` (S08), and `lean4_proofs` (S11).
- **Outputs**: `full_document.md` and per-section MD files.
- **Failures**: If S07 miscalculates `sort_order` or if S08/S09 fail to populate summaries/requirements, S10 produces a "hollow" or jumbled document.

---

## ⟳ tasks_loop Framework

Located in `tools/tasks_loop/`, this is the verification harness used to develop the pipeline.

### Core Mechanics: `SPEC.md` & Contracts

1.  **Fixture**: A folder in `fixtures/` containing a `source.pdf` and a `SPEC.md`.
2.  **SPEC.md**: Contains **YAML frontmatter** defining expected outcomes (block counts, section counts, required table markers).
3.  **Compilation**: `compile_contracts.py` transforms `SPEC.md` YAML into machine-readable JSON contracts.
4.  **Gates**: `tools/tasks_loop/gates/gate_sXX.py` scripts verify step outputs against these contracts.

### Mimicry Skill (The "Twin" Workflow)

Found in `tools/tasks_loop/utils/`:

- **Scanner**: `fixture_scanner.py` analyzes a real PDF's layout/fonts and produces a `mimic_spec.json`.
- **Generator**: `create_fixture_pdf.py` consumes the spec to generate a "Lorem Ipsum" PDF with identical structure.
- **VLM Debugging**: The scanner produces **DevTools-style visual overlays** (bounding boxes) to verify detection quality.

---

## 🔍 Critical Evaluation & Brittleness

### 🔴 Red Flags (Brittle/Non-working)

- **Column Layouts**: The `sort_order` (`page * 10000 + y0`) fails on multi-column PDFs as it reads strictly top-to-bottom across columns.
- **DuckDB State**: Steps S08 and S09 modify the database in-place. There is no rollback mechanism if an enrichment step partially fails.
- **Path Fragility**: `run_pipeline.py` hardcodes `data/results/pipeline`. If multiple fixtures are run concurrently without proper `--pipeline-dir` isolation, data will bleed across runs.
- **Aspirational S11**: Lean4 integration exists but is highly dependent on a specific Docker environment and theorem-proving agent state which is not always initialized.

### 🟡 Medium Risks (Over-engineered/Aspirational)

- **Contract Compilation**: The YAML -> JSON -> Gate pipeline is robust but adds significant friction when adding new pipeline stages.
- **S10 Complex UNION**: The query in `s10_markdown_exporter.py` is getting very large. It should likely be refactored into a DuckDB View for maintainability.

### ✅ Green Fields (Working Well)

- **Mimicry Loop**: Effectively solves the privacy barrier for client data.
- **Gate-based CI**: Reliable pass/fail signals for headless agents.
- **Sanity Manifests**: Correctly prevents cascading failures by checking dependencies first.

---

## 🚀 Handoff Checklist for Next Agent

1.  **Context**: Read `tools/tasks_loop/README.md` first.
2.  **Environment**: Use `uv run` and ensure `CHUTES_TEXT_MODEL` is set in `.env`.
3.  **Fixtures**:
    - `synthesis_messy_BHT`: Tests multi-page tables and ambiguous headers.
    - `synthesis_scale_50p`: Tests 50-page stability and S02 fallback.
4.  **Key Commands**:
    - Build Twin: `python tools/tasks_loop/utils/fixture_scanner.py --pdf input.pdf --output spec.json --debug-visuals`
    - Run Pipeline: `python tools/tasks_loop/run_pipeline.py s10 --fixture synthesis_scale_50p`
5.  **LLM Pattern**: Use `extractor.pipeline.utils.chutes_scillm` for all completions. Do NOT use raw OpenAI/Anthropic SDKs.
