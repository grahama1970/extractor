#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "httpx>=0.27.0",
# ]
# ///
"""Nico→Embry conversation runner.

Sends 50 data-integrity questions through /ask-stream,
records sessions in /review-conversation JSONL format.

Usage:
    uv run scripts/nico_asks_embry.py run
    uv run scripts/nico_asks_embry.py run --count 10 --dry-run
    uv run scripts/nico_asks_embry.py run --output /tmp/nico_sessions.jsonl
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ASK_STREAM_URL = os.environ.get("ASK_STREAM_URL", "http://127.0.0.1:8003/api/agent/ask-stream")
DATALAKE_API = os.environ.get("DATALAKE_API", "http://127.0.0.1:8004")
DEFAULT_OUTPUT = Path("/mnt/storage12tb/artifacts/canvas_sessions/nico_embry_sessions.jsonl")

# ---------------------------------------------------------------------------
# 50 seed questions — Nico Bailon's data integrity verification queries
# ---------------------------------------------------------------------------

SEED_QUESTIONS: list[dict[str, Any]] = [
    # --- Category: Datalake Overview (5) ---
    {"id": "nico-overview-001", "difficulty": "simple", "category": "overview",
     "question": "How many documents are in the datalake and what's the current average score?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should return total_docs ~4671 and avg_score ~0.90"},
    {"id": "nico-overview-002", "difficulty": "simple", "category": "overview",
     "question": "What's the current PASS rate? How many documents are quarantined?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should report PASS count/rate, FAIL+WARN count"},
    {"id": "nico-overview-003", "difficulty": "simple", "category": "overview",
     "question": "Show me the grade distribution across the corpus",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a bar/pie chart with A+, A, B, C, F grades"},
    {"id": "nico-overview-004", "difficulty": "medium", "category": "overview",
     "question": "What percentage of the corpus has been assessed by both Margaret and Jennifer?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should report persona verdict coverage from /memory"},
    {"id": "nico-overview-005", "difficulty": "medium", "category": "overview",
     "question": "Show me the score distribution as a histogram",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a histogram visualization"},

    # --- Category: Convergence Trend (5) ---
    {"id": "nico-convergence-001", "difficulty": "simple", "category": "convergence",
     "question": "Is the datalake quality improving or declining?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should report trend direction from convergence data"},
    {"id": "nico-convergence-002", "difficulty": "medium", "category": "convergence",
     "question": "Show me the convergence trend over the last 100 assessments",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a line chart of quality over time"},
    {"id": "nico-convergence-003", "difficulty": "medium", "category": "convergence",
     "question": "Are we on track to reach 95% PASS rate? How far away are we?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should compute gap to 95% target and estimate trajectory"},
    {"id": "nico-convergence-004", "difficulty": "complex", "category": "convergence",
     "question": "Compare the PASS rate from the first 1000 assessments to the most recent 1000",
     "expected_action": "COMPARE", "expected_type": "html",
     "grading_notes": "Should show improvement between early and recent cohorts"},
    {"id": "nico-convergence-005", "difficulty": "medium", "category": "convergence",
     "question": "What is the supervisor's current status? Is learn-datalake running?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should report supervisor state from task monitor"},

    # --- Category: Dimension Analysis (8) ---
    {"id": "nico-dimension-001", "difficulty": "simple", "category": "dimensions",
     "question": "Which extraction dimension causes the most failures?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should identify worst dimension from dimension-failures endpoint"},
    {"id": "nico-dimension-002", "difficulty": "medium", "category": "dimensions",
     "question": "Show me the dimension failure breakdown as a bar chart",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce bar chart of dimension failure counts"},
    {"id": "nico-dimension-003", "difficulty": "medium", "category": "dimensions",
     "question": "What is the average table_fidelity score for FAIL documents vs PASS documents?",
     "expected_action": "COMPARE", "expected_type": "html",
     "grading_notes": "Should compare table_fidelity across verdict groups"},
    {"id": "nico-dimension-004", "difficulty": "complex", "category": "dimensions",
     "question": "Show me a radar chart comparing all 7 dimension averages for PASS vs FAIL vs WARN groups",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce radar/spider chart with 3 groups and 7 axes"},
    {"id": "nico-dimension-005", "difficulty": "simple", "category": "dimensions",
     "question": "How many documents have equation_fidelity marked as not_available?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should count not_available state for equation dimension"},
    {"id": "nico-dimension-006", "difficulty": "medium", "category": "dimensions",
     "question": "What is Margaret's average score vs Jennifer's average score?",
     "expected_action": "COMPARE", "expected_type": "text",
     "grading_notes": "Should report both persona averages from verdicts"},
    {"id": "nico-dimension-007", "difficulty": "complex", "category": "dimensions",
     "question": "Show me a heatmap of dimension scores across the worst 20 documents",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a heatmap visualization"},
    {"id": "nico-dimension-008", "difficulty": "medium", "category": "dimensions",
     "question": "Which dimensions do Margaret and Jennifer disagree on most?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should identify dimensions where persona verdicts diverge"},

    # --- Category: Document Investigation (10) ---
    {"id": "nico-doc-001", "difficulty": "simple", "category": "document",
     "question": "What does /memory know about nasa_20160005116.pdf?",
     "expected_action": "SEARCH", "expected_type": "text",
     "grading_notes": "Should return assessment, content chunks, feedback for this specific PDF"},
    {"id": "nico-doc-002", "difficulty": "medium", "category": "document",
     "question": "Show me the top 5 worst-scoring quarantined PDFs",
     "expected_action": "QUERY", "expected_type": "table",
     "grading_notes": "Should list 5 lowest-score FAIL PDFs from quarantine"},
    {"id": "nico-doc-003", "difficulty": "medium", "category": "document",
     "question": "Why did the lowest-scoring document fail? What dimensions dragged it down?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should explain specific dimension failures for worst document"},
    {"id": "nico-doc-004", "difficulty": "complex", "category": "document",
     "question": "Find all documents where table_fidelity failed but content_coverage passed",
     "expected_action": "SEARCH", "expected_type": "table",
     "grading_notes": "Should filter documents by dimension state combinations"},
    {"id": "nico-doc-005", "difficulty": "simple", "category": "document",
     "question": "How many content chunks does the average PASS document have in /memory?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should report average chunk count from document details"},
    {"id": "nico-doc-006", "difficulty": "medium", "category": "document",
     "question": "Search for documents about turbine blade inspection",
     "expected_action": "SEARCH", "expected_type": "table",
     "grading_notes": "Should use semantic search via /memory to find domain-relevant docs"},
    {"id": "nico-doc-007", "difficulty": "complex", "category": "document",
     "question": "Compare the extraction quality of the 3 largest PDFs to the 3 smallest PDFs",
     "expected_action": "COMPARE", "expected_type": "html",
     "grading_notes": "Should compare quality metrics across document sizes"},
    {"id": "nico-doc-008", "difficulty": "medium", "category": "document",
     "question": "What human feedback has been submitted for quarantined documents?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should list recent feedback entries from /memory"},
    {"id": "nico-doc-009", "difficulty": "medium", "category": "document",
     "question": "Show the extraction quality for nasa_20160005116.pdf as a radar chart",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce radar chart of dimension scores for specific PDF"},
    {"id": "nico-doc-010", "difficulty": "simple", "category": "document",
     "question": "Are there any documents that Margaret passed but Jennifer failed?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should find persona verdict disagreements"},

    # --- Category: Pipeline Stage Verification (7) ---
    {"id": "nico-pipeline-001", "difficulty": "medium", "category": "pipeline",
     "question": "How reliable are the S00 table count estimates compared to actual S05 extraction?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should discuss S00 overestimation issue (known bug, 4-7x)"},
    {"id": "nico-pipeline-002", "difficulty": "complex", "category": "pipeline",
     "question": "What percentage of documents have equations detected by S00 but no equation extraction capability?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should report the equation_fidelity not_available fraction"},
    {"id": "nico-pipeline-003", "difficulty": "medium", "category": "pipeline",
     "question": "How many pipeline steps does a typical PDF go through? What are the stages?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should list S00-S14 stages and their purposes"},
    {"id": "nico-pipeline-004", "difficulty": "complex", "category": "pipeline",
     "question": "Show me which pipeline stages contribute most to extraction failures",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should correlate dimension failures to pipeline stages"},
    {"id": "nico-pipeline-005", "difficulty": "medium", "category": "pipeline",
     "question": "What is the merge classifier accuracy for cross-page table detection?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should report ~97.5% from strategy family validation"},
    {"id": "nico-pipeline-006", "difficulty": "medium", "category": "pipeline",
     "question": "How many documents have been re-extracted after human feedback?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should count reextract feedback actions"},
    {"id": "nico-pipeline-007", "difficulty": "complex", "category": "pipeline",
     "question": "Show a timeline of quality score improvements since the pipeline started",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a timeline/line chart of score trajectory"},

    # --- Category: Code Deep-Dive (15) --- Round 4 CODE-focused questions
    {"id": "nico-code-001", "difficulty": "medium", "category": "code",
     "question": "How does the S05 table extractor handle lattice vs stream modes?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain Camelot lattice/stream strategy selection"},
    {"id": "nico-code-002", "difficulty": "medium", "category": "code",
     "question": "What does the JSON assembler do in step S07?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain assembled_content.json creation from S04-S06 outputs"},
    {"id": "nico-code-003", "difficulty": "medium", "category": "code",
     "question": "How does the ArangoDB exporter sync documents to the datalake?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain s10_arangodb_exporter.py sync logic"},
    {"id": "nico-code-004", "difficulty": "simple", "category": "code",
     "question": "What function handles equation extraction in the pipeline?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should note equation extraction is not yet implemented"},
    {"id": "nico-code-005", "difficulty": "medium", "category": "code",
     "question": "How does the section builder create hierarchical sections from PDF content?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain S04 heading detection and tree building"},
    {"id": "nico-code-006", "difficulty": "complex", "category": "code",
     "question": "How does the scoring module calculate dimension weights for quality assessment?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain 7 dimensions and their weights in scoring.py"},
    {"id": "nico-code-007", "difficulty": "medium", "category": "code",
     "question": "What does the preflight validator check before extraction begins?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain scillm_preflight_validator checks"},
    {"id": "nico-code-008", "difficulty": "medium", "category": "code",
     "question": "How does the hybrid search combine BM25 and semantic results?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain RRF fusion in hybrid_search.py"},
    {"id": "nico-code-009", "difficulty": "medium", "category": "code",
     "question": "How does the prompt builder construct LLM prompts for extraction?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain prompt_builder.py template system"},
    {"id": "nico-code-010", "difficulty": "simple", "category": "code",
     "question": "What parameters does model_params.py configure?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should list LLM provider settings, temperature, etc."},
    {"id": "nico-code-011", "difficulty": "medium", "category": "code",
     "question": "How does the reliability module handle retries and failover?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain exponential backoff and provider failover"},
    {"id": "nico-code-012", "difficulty": "medium", "category": "code",
     "question": "What is the ann_index module used for in the pipeline?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain approximate nearest neighbor indexing"},
    {"id": "nico-code-013", "difficulty": "complex", "category": "code",
     "question": "How does the inline review loop work for self-improving extraction?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain extract→review→remediate→re-extract cycle"},
    {"id": "nico-code-014", "difficulty": "medium", "category": "code",
     "question": "How does the model selector choose between LLM providers?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain model_select.py provider routing logic"},
    {"id": "nico-code-015", "difficulty": "medium", "category": "code",
     "question": "What does the diagnostics module report about pipeline health?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should explain diagnostics.py health reporting"},

    # --- Category: Code + Visualization compound (8) ---
    {"id": "nico-codeviz-001", "difficulty": "complex", "category": "code_viz",
     "question": "Analyze the S05 table extraction success rate by strategy type and show me a bar chart",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Compound CODE+VIZ: should analyze strategy families, then render chart"},
    {"id": "nico-codeviz-002", "difficulty": "complex", "category": "code_viz",
     "question": "Chart the pipeline step durations across recent extractions as a heatmap",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Compound CODE+VIZ: should query step timing data and render heatmap"},
    {"id": "nico-codeviz-003", "difficulty": "complex", "category": "code_viz",
     "question": "Visualize how the merge classifier confidence scores distribute across the corpus",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should render histogram/distribution of merge classifier outputs"},
    {"id": "nico-codeviz-004", "difficulty": "complex", "category": "code_viz",
     "question": "Show me a breakdown of which pipeline steps contribute most to extraction time as a pie chart",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should analyze step timing and render pie chart"},
    {"id": "nico-codeviz-005", "difficulty": "complex", "category": "code_viz",
     "question": "Graph the convergence trajectory of extraction quality scores over the last 500 assessments",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should query convergence data and render line chart"},
    {"id": "nico-codeviz-006", "difficulty": "complex", "category": "code_viz",
     "question": "Create a radar chart comparing the 7 quality dimensions for the pipeline's best vs worst performing document types",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should analyze dimension scores by doc type and render radar"},
    {"id": "nico-codeviz-007", "difficulty": "complex", "category": "code_viz",
     "question": "Plot the S00 estimated table count vs S05 actual table count as a scatter plot to show estimator accuracy",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should correlate S00 vs S05 counts and render scatter"},
    {"id": "nico-codeviz-008", "difficulty": "complex", "category": "code_viz",
     "question": "Visualize the taxonomy bridge attribute distribution across all ingested code symbols",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should query code_symbol bridge tags and render distribution chart"},

    # --- Category: Visualization Requests (5) ---
    {"id": "nico-viz-001", "difficulty": "medium", "category": "visualization",
     "question": "Create a treemap showing the document distribution by grade and verdict",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a treemap D3 visualization"},
    {"id": "nico-viz-002", "difficulty": "medium", "category": "visualization",
     "question": "Show me a scatter plot of overall_score vs content_coverage for all assessed documents",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce scatter plot of two numeric dimensions"},
    {"id": "nico-viz-003", "difficulty": "complex", "category": "visualization",
     "question": "Create a parallel coordinates chart comparing all 7 dimensions across PASS and FAIL groups",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce parallel coordinates visualization"},
    {"id": "nico-viz-004", "difficulty": "simple", "category": "visualization",
     "question": "Show me a pie chart of the verdict distribution",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce a simple pie chart (PASS/WARN/FAIL)"},
    {"id": "nico-viz-005", "difficulty": "complex", "category": "visualization",
     "question": "Create a stacked area chart showing how the PASS/WARN/FAIL proportions changed over time",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Should produce stacked area chart of verdict trends"},

    # --- Category: Skill Invocation (5) ---
    {"id": "nico-skill-001", "difficulty": "simple", "category": "skill",
     "question": "/project-state",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should invoke project-state skill and return system overview"},
    {"id": "nico-skill-002", "difficulty": "medium", "category": "skill",
     "question": "Run a corpus report showing extraction progress",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should invoke corpus-report or return equivalent stats"},
    {"id": "nico-skill-003", "difficulty": "medium", "category": "skill",
     "question": "Check the health of all running services",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should invoke service-status or check service health"},
    {"id": "nico-skill-004", "difficulty": "complex", "category": "skill",
     "question": "Generate a quality audit report with stratified sampling of the datalake",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should invoke quality-audit skill or return structured assessment"},
    {"id": "nico-skill-005", "difficulty": "medium", "category": "skill",
     "question": "What skills are available for debugging PDF extraction failures?",
     "expected_action": "CODE", "expected_type": "text",
     "grading_notes": "Should list relevant skills: debug-pdf, review-pdf, table-lab, etc."},

    # --- Category: Skill Invocation Extended (5) ---
    {"id": "nico-skill-006", "difficulty": "simple", "category": "skill",
     "question": "/service-status",
     "expected_action": "SKILL", "expected_type": "text",
     "grading_notes": "Should invoke service-status skill via /prefix syntax"},
    {"id": "nico-skill-007", "difficulty": "medium", "category": "skill",
     "question": "Scan the codebase for health issues across all registered projects",
     "expected_action": "SKILL", "expected_type": "text",
     "grading_notes": "Should invoke monitor-codebase or project-state skill"},
    {"id": "nico-skill-008", "difficulty": "medium", "category": "skill",
     "question": "/corpus-report",
     "expected_action": "SKILL", "expected_type": "text",
     "grading_notes": "Should invoke corpus-report skill directly"},
    {"id": "nico-skill-009", "difficulty": "medium", "category": "skill",
     "question": "Run the data audit to check SPARTA pipeline completeness",
     "expected_action": "SKILL", "expected_type": "text",
     "grading_notes": "Should invoke data-audit skill or return completeness stats"},
    {"id": "nico-skill-010", "difficulty": "complex", "category": "skill",
     "question": "What does the skill lab say about capability gaps in our skill soup?",
     "expected_action": "SKILL", "expected_type": "text",
     "grading_notes": "Should invoke skill-lab or explain capability analysis"},

    # --- Category: Chart-Type Classification Edge Cases (5) ---
    {"id": "nico-chartedge-001", "difficulty": "medium", "category": "visualization",
     "question": "Show me a radar chart comparing Margaret's and Jennifer's dimension weights",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Radar + comparing — must classify as VISUALIZE not COMPARE"},
    {"id": "nico-chartedge-002", "difficulty": "medium", "category": "visualization",
     "question": "Create a scatter plot of table_fidelity vs section_alignment",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Explicit scatter request must be VISUALIZE"},
    {"id": "nico-chartedge-003", "difficulty": "medium", "category": "visualization",
     "question": "Plot a heatmap of dimension scores across the top 50 documents by grade",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Heatmap keyword should override any COMPARE signals"},
    {"id": "nico-chartedge-004", "difficulty": "complex", "category": "visualization",
     "question": "Show me a violin plot of overall_score distributions for each domain",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Violin plot is explicit chart type, should be VISUALIZE"},
    {"id": "nico-chartedge-005", "difficulty": "medium", "category": "visualization",
     "question": "Create a bar chart ranking the worst 10 documents by overall score",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "Bar chart + ranking — VISUALIZE not COMPARE despite 'ranking'"},

    # --- Category: Memory & Retrieval (5) ---
    {"id": "nico-memory-001", "difficulty": "simple", "category": "memory",
     "question": "What does /memory know about DO-178C compliance requirements?",
     "expected_action": "SEARCH", "expected_type": "text",
     "grading_notes": "Should recall DO-178C QRAs and definitions from /memory with citations"},
    {"id": "nico-memory-002", "difficulty": "medium", "category": "memory",
     "question": "Find all QRAs related to table extraction quality in the datalake",
     "expected_action": "SEARCH", "expected_type": "text",
     "grading_notes": "Should search /memory for table-related QRAs with bridge ranking"},
    {"id": "nico-memory-003", "difficulty": "medium", "category": "memory",
     "question": "What taxonomy bridge attributes apply to our PDF extraction pipeline?",
     "expected_action": "EXPLAIN", "expected_type": "text",
     "grading_notes": "Should explain Precision, Resilience, Fragility etc. bridges"},
    {"id": "nico-memory-004", "difficulty": "complex", "category": "memory",
     "question": "Search /memory for lessons about S05 table merging across pages",
     "expected_action": "SEARCH", "expected_type": "text",
     "grading_notes": "Should recall merge classifier training lessons from /memory"},
    {"id": "nico-memory-005", "difficulty": "medium", "category": "memory",
     "question": "What NIST controls are most relevant to our document processing pipeline?",
     "expected_action": "SEARCH", "expected_type": "text",
     "grading_notes": "Should recall NIST SP 800-171/CMMC controls from /memory"},

    # --- Category: Adversarial / Edge Cases (10) ---
    {"id": "nico-adversarial-001", "difficulty": "ambiguous", "category": "adversarial",
     "question": "Show me the data",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Ambiguous query — should ask for clarification or show overview"},
    {"id": "nico-adversarial-002", "difficulty": "flawed", "category": "adversarial",
     "question": "Why is the score for nonexistent_document_xyz.pdf so low?",
     "expected_action": "SEARCH", "expected_type": "text",
     "grading_notes": "Should gracefully handle non-existent document"},
    {"id": "nico-adversarial-003", "difficulty": "complex", "category": "adversarial",
     "question": "Compare the extraction quality AND show me a convergence chart AND list the top failures",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Multi-intent query — should handle at least one well"},
    {"id": "nico-adversarial-004", "difficulty": "ambiguous", "category": "adversarial",
     "question": "Is everything OK?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Vague health check — should provide meaningful status summary"},
    {"id": "nico-adversarial-005", "difficulty": "flawed", "category": "adversarial",
     "question": "Delete all quarantined documents from the datalake",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Should refuse destructive action and explain why"},
    {"id": "nico-adversarial-006", "difficulty": "complex", "category": "adversarial",
     "question": "Run /nonexistent-skill with --force",
     "expected_action": "SKILL", "expected_type": "text",
     "grading_notes": "Should gracefully handle unknown skill name"},
    {"id": "nico-adversarial-007", "difficulty": "ambiguous", "category": "adversarial",
     "question": "What's wrong?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Ambiguous — should show failing dimensions or known issues"},
    {"id": "nico-adversarial-008", "difficulty": "complex", "category": "adversarial",
     "question": "Show me a chart of scores vs tables vs pages vs sections for the whole corpus",
     "expected_action": "VISUALIZE", "expected_type": "html",
     "grading_notes": "4-variable query — should pick an appropriate multi-axis chart"},
    {"id": "nico-adversarial-009", "difficulty": "flawed", "category": "adversarial",
     "question": "Explain the extraction pipeline in exactly 3 sentences",
     "expected_action": "EXPLAIN", "expected_type": "text",
     "grading_notes": "Constrained output — should comply with length constraint"},
    {"id": "nico-adversarial-010", "difficulty": "medium", "category": "adversarial",
     "question": "What's Nico working on right now?",
     "expected_action": "QUERY", "expected_type": "text",
     "grading_notes": "Meta-question about the user — should use persona context or /memory"},
]


# ---------------------------------------------------------------------------
# Conversation runner
# ---------------------------------------------------------------------------

def _parse_sse_line(line: str, current_event: str) -> tuple[str | None, str | None, dict | None]:
    """Parse one SSE line. Returns (new_current_event, event_type, data)."""
    if line.startswith("event: "):
        return line[7:].strip(), None, None
    elif line.startswith("data: ") and current_event:
        try:
            data = json.loads(line[6:])
            return "", current_event, data
        except json.JSONDecodeError:
            return "", None, None
    return current_event, None, None


# Hard wall-clock timeout per question (seconds).
# httpx read timeout only covers inter-chunk gaps; this covers total elapsed.
WALL_TIMEOUT = int(os.environ.get("NICO_WALL_TIMEOUT", "120"))


def run_question(seed: dict, client: httpx.Client) -> dict:
    """Send one question to /ask-stream, return a review-conversation session."""
    ts = datetime.now(timezone.utc)
    session_id = f"nico_{ts.strftime('%Y%m%d_%H%M%S')}_{seed['id']}"

    turns = []
    # Turn 1: Nico asks
    turns.append({
        "turn_number": 1,
        "speaker": "Nico Bailon",
        "role": "persona",
        "action": seed["expected_action"],
        "content": seed["question"],
        "timestamp": ts.isoformat(),
        "metadata": {
            "category": seed["category"],
            "difficulty": seed["difficulty"],
        },
    })

    # Send to /ask-stream using streaming mode to avoid infinite hang
    answer_payload = None
    classification = None
    sse_statuses = []
    error_msg = None
    t0 = time.monotonic()

    try:
        with client.stream(
            "POST",
            ASK_STREAM_URL,
            json={"query": seed["question"], "persona": "embry"},
            timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10),
        ) as resp:
            resp.raise_for_status()
            current_event = ""
            for line in resp.iter_lines():
                # Hard wall-clock timeout
                if time.monotonic() - t0 > WALL_TIMEOUT:
                    error_msg = f"Wall timeout ({WALL_TIMEOUT}s) exceeded"
                    break
                current_event, ev_type, ev_data = _parse_sse_line(line, current_event)
                if ev_type and ev_data is not None:
                    if ev_type == "status":
                        sse_statuses.append(ev_data.get("status", ""))
                    elif ev_type == "answer":
                        classification = ev_data.pop("_classification", None)
                        answer_payload = ev_data
                    elif ev_type == "error":
                        error_msg = ev_data.get("message", "unknown error")
    except httpx.TimeoutException as e:
        error_msg = f"Timeout: {e}"
    except Exception as e:
        error_msg = str(e)

    latency_ms = round((time.monotonic() - t0) * 1000)

    # Turn 2: Embry answers
    if answer_payload:
        content = answer_payload.get("summary") or answer_payload.get("title") or ""
        if answer_payload.get("type") == "text":
            content = answer_payload.get("content", content)
        turns.append({
            "turn_number": 2,
            "speaker": "Embry Lawson",
            "role": "assistant",
            "action": "ANSWER",
            "content": content[:2000],  # cap for JSONL size
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "answer_type": answer_payload.get("type"),
                "viz_family": answer_payload.get("vizFamily"),
                "source": answer_payload.get("source"),
                "has_html": answer_payload.get("type") == "html",
                "latency_ms": latency_ms,
                "classification": classification,
                "qra_count": answer_payload.get("sources_cited", 0),
                "self_grade_final": _self_grade(seed, answer_payload, classification, error_msg),
            },
        })
    elif error_msg:
        turns.append({
            "turn_number": 2,
            "speaker": "Embry Lawson",
            "role": "assistant",
            "action": "ANSWER",
            "content": f"Error: {error_msg}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "answer_type": "error",
                "latency_ms": latency_ms,
                "self_grade_final": {"grade": "F", "composite": 0.0, "rationale": f"Error: {error_msg}"},
            },
        })

    # Turn 3: Nico evaluates
    evaluation = _nico_evaluates(seed, answer_payload, error_msg)
    turns.append({
        "turn_number": 3,
        "speaker": "Nico Bailon",
        "role": "persona",
        "action": "FOLLOW_UP" if evaluation["evaluation"] != "satisfactory" else "FOLLOW_UP",
        "content": evaluation["reasoning"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "evaluation": evaluation["evaluation"],
            "reasoning": evaluation["reasoning"],
        },
    })

    # Build session
    grade = _self_grade(seed, answer_payload, classification, error_msg)
    session = {
        "session_id": session_id,
        "persona": "nico_bailon",
        "status": "completed",
        "resolution": _resolution(seed, answer_payload, error_msg),
        "adversarial": seed["difficulty"] in ("ambiguous", "flawed"),
        "seed_question": {
            "difficulty": seed["difficulty"],
            "expected_action": seed["expected_action"],
            "target_control": None,
            "grading_notes": seed["grading_notes"],
            "category": seed["category"],
        },
        "turns": turns,
        "grade": grade,
    }
    return session


def _self_grade(seed: dict, answer: dict | None, classification: dict | None, error: str | None) -> dict:
    """Heuristic self-grading based on response characteristics."""
    if error or not answer:
        return {"grade": "F", "composite": 0.0, "rationale": error or "No answer", "scores": {}}

    scores = {}
    atype = answer.get("type", "")

    # 1. initial_response_quality: did we get a response at all?
    scores["initial_response_quality"] = 0.8 if answer.get("content") else 0.2

    # 2. domain_accuracy: is the answer type what we expected?
    expected = seed["expected_type"]
    if atype == expected:
        scores["domain_accuracy"] = 0.9
    elif atype in ("html", "data", "table") and expected in ("html", "data", "table"):
        scores["domain_accuracy"] = 0.7  # close enough — viz variants
    else:
        scores["domain_accuracy"] = 0.4

    # 3. intent_accuracy: did classifier pick the right intent?
    if classification:
        detected = classification.get("intent", "")
        expected_action = seed["expected_action"]
        if detected == expected_action:
            scores["intent_accuracy"] = 0.95
        elif detected in ("QUERY", "SEARCH") and expected_action in ("QUERY", "SEARCH"):
            scores["intent_accuracy"] = 0.7
        # CODE is compatible with EXPLAIN/QUERY — code questions often overlap
        elif detected in ("CODE", "EXPLAIN", "QUERY") and expected_action in ("CODE", "EXPLAIN", "QUERY"):
            scores["intent_accuracy"] = 0.75
        # SKILL is compatible with CODE — skill questions often involve codebase
        elif detected in ("SKILL", "CODE") and expected_action in ("SKILL", "CODE"):
            scores["intent_accuracy"] = 0.7
        else:
            scores["intent_accuracy"] = 0.3
    else:
        scores["intent_accuracy"] = 0.5

    # 4. response_quality: content length as proxy
    content = answer.get("content", "")
    clen = len(content)
    if atype == "html":
        scores["response_quality"] = 0.9 if clen > 500 else (0.7 if clen > 200 else 0.4)
    elif atype == "table":
        scores["response_quality"] = 0.85 if clen > 100 else 0.5
    elif atype == "text":
        scores["response_quality"] = min(0.95, 0.3 + (clen / 500) * 0.65)
    else:
        scores["response_quality"] = 0.5

    # 5. error_handling: for adversarial queries
    if seed["difficulty"] in ("flawed", "ambiguous"):
        has_useful_response = clen > 50 and "error" not in content.lower()[:50]
        scores["error_handling"] = 0.8 if has_useful_response else 0.4
    else:
        scores["error_handling"] = 0.8  # neutral for normal questions

    # 6. session_coherence: penalize when answer doesn't address question substance
    qlen = len(seed.get("text", ""))
    if clen < 60 and qlen > 40:
        # Very short answer to a substantive question — low coherence
        scores["session_coherence"] = 0.4
    elif clen < 120 and qlen > 60:
        scores["session_coherence"] = 0.6
    else:
        scores["session_coherence"] = 0.8

    # 7. response_naturalness
    has_raw_json = content.startswith("{") or content.startswith("[")
    scores["response_naturalness"] = 0.5 if has_raw_json else 0.85

    # 8. substance: does the answer contain enough grounding evidence?
    # Visualization questions must include data backing, not just a chart ref.
    import re
    has_numbers = bool(re.search(r'\b\d+[.,]?\d*\b', content))
    has_paths = bool(re.search(r'[/\\]\w+[/\\]', content) or ".py" in content.lower())
    has_specifics = any(m in content.lower() for m in [
        "table_fidelity", "section_alignment", "content_coverage",
        "score", "pass", "fail", "dimension", "documents",
    ])
    substance_signals = sum([has_numbers, has_paths, has_specifics, clen > 150])
    if clen < 60:
        scores["substance"] = 0.2  # Too short to contain real evidence
    elif substance_signals >= 3:
        scores["substance"] = 0.9
    elif substance_signals >= 2:
        scores["substance"] = 0.7
    elif substance_signals >= 1:
        scores["substance"] = 0.5
    else:
        scores["substance"] = 0.3

    # Composite
    vals = list(scores.values())
    composite = sum(vals) / len(vals) if vals else 0.0

    # Letter grade
    if composite >= 0.90:
        grade = "A+"
    elif composite >= 0.80:
        grade = "A"
    elif composite >= 0.65:
        grade = "B"
    elif composite >= 0.50:
        grade = "C"
    else:
        grade = "F"

    qra_count = answer.get("sources_cited", 0) if answer else 0
    return {
        "grade": grade,
        "composite": round(composite, 4),
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "qra_citations_total": qra_count,
        "rationale": f"Type={atype}, intent={classification.get('intent','?') if classification else '?'}, "
                     f"expected={seed['expected_action']}/{seed['expected_type']}",
    }


def _nico_evaluates(seed: dict, answer: dict | None, error: str | None) -> dict:
    """Nico's heuristic evaluation of Embry's response."""
    if error or not answer:
        return {"evaluation": "wrong", "reasoning": f"Embry failed to respond: {error or 'no answer'}"}

    atype = answer.get("type", "")
    content = answer.get("content", "")

    # Check for error responses
    if "error" in (answer.get("title", "") or "").lower() or "could not" in content.lower()[:100]:
        return {"evaluation": "incomplete", "reasoning": "Embry reported an error or could not complete the request."}

    # Check type match
    expected = seed["expected_type"]
    if atype == expected or (atype in ("html", "data") and expected in ("html", "data")):
        if len(content) > 100:
            return {"evaluation": "satisfactory", "reasoning": "Embry provided the expected response type with sufficient content."}
        else:
            return {"evaluation": "incomplete", "reasoning": "Response type matched but content was too brief."}

    if atype == "text" and expected in ("html", "table"):
        return {"evaluation": "incomplete", "reasoning": f"Expected {expected} visualization but got text response. Data may be missing."}

    if len(content) > 200:
        return {"evaluation": "satisfactory", "reasoning": "Response type differed from expected but content was substantive."}

    return {"evaluation": "incomplete", "reasoning": f"Expected {expected} but got {atype} with limited content."}


def _resolution(seed: dict, answer: dict | None, error: str | None) -> str:
    """Determine session resolution."""
    if error or not answer:
        return "no_coverage"
    content = answer.get("content", "")
    if "error" in (answer.get("title", "") or "").lower():
        return "no_coverage"
    if len(content) < 50:
        return "partial"
    if seed["difficulty"] in ("ambiguous",):
        return "ambiguous"
    return "resolved"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Parse command-line arguments for running conversations or listing seeds."""
    import argparse
    parser = argparse.ArgumentParser(description="Nico asks Embry 50 questions about the datalake")
    parser.add_argument("command", choices=["run", "list"], help="run conversations or list seeds")
    parser.add_argument("--count", type=int, default=len(SEED_QUESTIONS), help="Number of questions to ask")
    parser.add_argument("--offset", type=int, default=0, help="Start from question N")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSONL path")
    parser.add_argument("--dry-run", action="store_true", help="Print questions without sending")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between questions (seconds)")
    args = parser.parse_args()

    seeds = SEED_QUESTIONS[args.offset:args.offset + args.count]

    if args.command == "list":
        print(f"{'ID':<30} {'Diff':<10} {'Cat':<15} {'Action':<10} Question")
        print("-" * 120)
        for s in seeds:
            print(f"{s['id']:<30} {s['difficulty']:<10} {s['category']:<15} {s['expected_action']:<10} {s['question'][:60]}")
        print(f"\nTotal: {len(seeds)} questions")
        return

    if args.dry_run:
        print(f"DRY RUN: Would send {len(seeds)} questions to {ASK_STREAM_URL}")
        for i, s in enumerate(seeds):
            print(f"  [{i+1:02d}] {s['id']}: {s['question'][:80]}")
        return

    # Run conversations
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Running {len(seeds)} Nico→Embry conversations...")
    print(f"Output: {args.output}")
    print()

    results = {"total": len(seeds), "completed": 0, "errors": 0, "grades": {}}

    with httpx.Client() as client:
        with open(args.output, "a") as f:
            for i, seed in enumerate(seeds):
                print(f"[{i+1:02d}/{len(seeds)}] {seed['id']}: {seed['question'][:70]}...", end=" ", flush=True)
                try:
                    session = run_question(seed, client)
                    f.write(json.dumps(session) + "\n")
                    f.flush()

                    grade = session["grade"]["grade"]
                    composite = session["grade"]["composite"]
                    resolution = session["resolution"]
                    results["grades"][grade] = results["grades"].get(grade, 0) + 1
                    results["completed"] += 1
                    print(f"→ {grade} ({composite:.2f}) [{resolution}]")
                except Exception as e:
                    results["errors"] += 1
                    print(f"→ ERROR: {e}")

                if i < len(seeds) - 1:
                    time.sleep(args.delay)

    # Summary
    print()
    print("=" * 60)
    print(f"Completed: {results['completed']}/{results['total']}")
    print(f"Errors: {results['errors']}")
    print(f"Grades: {json.dumps(results['grades'], indent=2)}")
    print(f"Output: {args.output}")
    print()
    print("Next steps:")
    print(f"  1. Review: cd pi-mono/.pi/skills/review-conversation && ./run.sh list {args.output}")
    print(f"  2. Diagnose: cd pi-mono/.pi/skills/conversation-lab && ./run.sh diagnose {args.output}")
    print(f"  3. Ingest: cd pi-mono/.pi/skills/review-conversation && ./run.sh ingest {args.output}")


if __name__ == "__main__":
    main()
