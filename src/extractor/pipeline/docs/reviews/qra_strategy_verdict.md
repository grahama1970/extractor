# QRA Strategy Verdict: Fidelity above All

**Date**: 2025-12-29
**Subject**: Critical Assessment for Model Training Goals

## The Verdict: YES.

The "Raw Corpus" approach is strictly superior for generating training data (QQR/QRA pairs) compared to the "Reflow" approach.

### 1. The "Reflow" Risk (Synthetic Slop)

Stage 07 "Reflow" uses an LLM to rewrite document images into proper Markdown.

- **Problem**: This rewrites the ground truth. It fixes typos, drops clauses, and normalizes tables.
- **Result**: You train your model on "perfect" synthetic text. When deployed on real, messy PDFs, it degrades.

### 2. The "Raw Corpus" Advantage (Ground Truth)

By storing exact outputs from Marker and Camelot in DuckDB:

- **Zero Rewriting**: The model sees the actual OCR/Extraction artifacts.
- **Traceability**: Every QRA pair can be linked to a specific `block_id` or `table_id`.
- **Fidelity**: Requirements extracted are verbatim from the source, not paraphrased.

### 3. The Citation Mechanism

The proposed `verification` step (matching LLM output against DB blocks) is only possible if the text hasn't been rewritten.

- If you Reflow, the citation won't match.
- If you use Raw Corpus, the citation matches exactly.

**Conclusion**:
The Pivot to DuckDB/Raw Corpus ensures **Data Integrity**. It is the only valid path for creating high-quality, hallucination-free Training Data.
