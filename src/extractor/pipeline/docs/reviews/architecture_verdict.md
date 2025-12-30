# Architecture Verdict: The Case for Simplification

**Date**: 2025-12-29
**Author**: Antigravity Coordinator

## 1. The Core Question

> "Is this the best approach... or is [the current pipeline] actually nearing completion?"

**Honest Answer**:
The current pipeline is "nearing completion" only in the sense that the code is written and runs. However, **Stages 06b ('Sketcher') and 07 ('Reflow') are architecturally flawed** for the goal of reliable data extraction. They attempt to _reconstruct_ the visual document layout in Markdown via an LLM ("Reflow"). This is:

1.  **Expensive**: Requires massive context.
2.  **Brittle**: Slight layout quirks cause the LLM to hallucinate or drop content.
3.  **Unnecessary**: If the goal is _Data Extraction_ (Requirements/Tables), we don't need a pretty Markdown document. We need structured data.

## 2. Validation of Your Proposal

> "We could create knowledge excerpts from the corpus text, and for a second LLM round, ask it to gather and merge any tables."

**YES.** This is superior because:

- **Separation of Concerns**: `pdf -> text/layout` (Deterministic) vs `text -> data` (Probabilistic/LLM).
- **Reduced Entropy**: Passing a list of text blocks and a list of CSV tables to an LLM is much less ambiguous than asking it to "reflow this page image".
- **Debuggability**: You can inspect the "Raw Corpus" (JSON) and see exactly what the LLM received. In "Reflow", the input is a messy mix of image tokens and bounding boxes.

## 3. The "Sunk Cost" Assessment

We are not starting over. We are **harvesting**.

| Stage                   | Status      | Verdict                                            |
| :---------------------- | :---------- | :------------------------------------------------- |
| **01 Annotations**      | Working     | **KEEP**. Essential for human-in-the-loop.         |
| **02 Marker**           | Working     | **KEEP**. Best-in-class text block extraction.     |
| **03 Headers**          | Working     | **KEEP**. Critical for sectioning.                 |
| **04 Section Builder**  | Working     | **KEEP**. The spine of the corpus.                 |
| **05 Tables (Camelot)** | Working     | **KEEP**. Deterministic table data > OCR.          |
| **06 Figures**          | Working     | **KEEP**. Visual context.                          |
| **06b Layout Sketcher** | Complex     | **KILL**. Too much heuristic glue.                 |
| **07 Reflow**           | Brittle     | **KILL**. The source of "Slop".                    |
| **08 Prover**           | Theoretical | **PAUSE**. Enable only after extraction is robust. |

## 4. The Path Forward (The "Focused" Pipeline)

Instead of fixing Stage 07, we replace it.

**New Workflow:**

1.  **Extract Ingredients** (Stages 01-06). Status: DONE.
2.  **Step 07 (New): Assemble Corpus**:
    - Iterate sections from Stage 04.
    - Deterministically zip content: `Section.text_blocks + Section.intersecting_tables + Section.intersecting_figures`.
    - Output: `corpus.json` (Structured, clean).
3.  **Step 08 (New): Focused Extraction**:
    - Function: `extract_requirements(corpus_chunk)`
    - Input: Clean text + Table CSVs.
    - Output: List of Requirements.
    - **Note**: This plays to the LLM's strength (Reasoning/Extraction) rather than its weakness (Layout/formatting).

## 5. Conclusion

**Do not double down on the current Stage 07.** It is "Completable" but will always be a maintenance nightmare. Pivot to the **Focused Corpus** approach immediately. It uses 80% of the existing code (the hard extraction parts) but discards the 20% that is causing the headache (the layout reconstruction).
