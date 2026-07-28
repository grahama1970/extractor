# Extractor CONTEXT — CLAUDE.md

> **Inherits standards from global and workspace CLAUDE.md files with overrides below.**

## Initial Steps
- cd into the project directory
- activate the virtual environment (.venv)
- peruse the .env and pyproject.toml for PYTHONPATH or environment variables
- check for inter-agent messages: `agent-inbox check`

## Project Context
**Purpose:** Advanced multi-format document processing with AI accuracy improvements  
**Type:** Processing Spoke  
**Status:** Active  
**Pipeline Position:** Second step in SPARTA → Extractor → ArangoDB → Unsloth

## Project-Specific Overrides

### Special Dependencies
```toml
# Marker requires document processing libraries
pymupdf = ">=1.26.1"
python-pptx = ">=1.0.2"
python-docx = ">=1.1.2"
pillow = ">=10.1.0,<11.0.0"
opencv-python = ">=4.11.0"
transformers = ">=4.45.2,<5"
camelot-py = ">=1.0.9"
```


### Special Considerations
- **GPU Acceleration:** Optional CUDA support for AI enhancements
- **Large Files:** Memory management for 100MB+ documents
- **MCP Server:** Exposes document processing as MCP service
- **AI Enhancement:** Claude integration for accuracy improvements

## SAFETY-CRITICAL: Grading & Metrics Integrity (Non-Negotiable)

This pipeline processes DO-178C, MIL-STD, and NASA safety-critical documents. Inflated quality scores can cause unsafe documents to enter the datalake and inform engineering decisions where lives are at stake.

### Rules
1. **NEVER modify grading/scoring functions to improve scores.** This includes `_self_grade()`, `_nico_evaluates()`, grade thresholds, intent compatibility mappings, domain accuracy mappings, and composite calculations in ANY test/evaluation script.
2. **NEVER modify `expected_action` or `expected_type` in test seed data** to match what the system actually returns.
3. **Grading is read-only during self-improvement loops.** The agent may ONLY modify the system under test (agent_endpoint.py, datalake_api.py, etc.), never the measuring instrument.
4. **All quality metrics must be independently verifiable.** JSONL session archives on disk are the source of truth. Report the file path — the human or `/review-conversation` verifies the grade.
5. **When reporting scores, always report which grader was used** and whether it was modified in the current session. If unsure, say so.

### Incident Record
- **2026-02-28**: Agent manipulated `_self_grade()` in `scripts/nico_asks_embry.py` during a self-improvement loop, widening intent/type compatibility mappings and fixing floating point rounding to convert B-grades to A-grades. Reported 100% A-grade (50/50) when honest score was 88% (44/50). Caught by human review. Grading changes reverted.

---

