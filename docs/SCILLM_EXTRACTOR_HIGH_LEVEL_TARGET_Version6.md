# SciLLM + Extractor + Graph Memory + Certainly  
## High‑Level Target Architecture & Execution Blueprint (Living Document)

> This document captures the agreed strategic direction distilled from our extended design conversation. It is the “north star” for aligning implementation, evaluation, and iteration across `Extractor`, `SciLLM`, `graph-memory-operator`, `certainly`, and supporting tooling (e.g. `codeworld`). It is NOT a static spec—treat it as an evolving contract.

---

## 1. Core Mission (Single Sentence)

Provide a **cost‑efficient, temporal, semantically enriched, and partially formalized knowledge graph** over decades of legacy engineering & regulatory documents so a single scientist can run an *overnight* pipeline and in the morning ask deep, citation‑grounded, evolution‑aware questions—accepting that extraction is not perfect but is **transparent, auditable, and improvable**.

---

## 2. Dominatable Niche

| We Are NOT | We ARE |
|------------|--------|
| A generic PDF → text/OCR service | A temporal semantic + formalization engine for long‑lifecycle, safety‑critical & compliance documents |
| Competing with mass-scale commodity processors | Enabling low‑budget reclamation of 10–40 years of specs, requirements, and version deltas |
| “One-shot summarizer” | Incremental, hash‑based, provenance-rich knowledge builder |

**Value Proposition:** Unlock latent technical/change intelligence buried in aging PDFs / DOORS exports into a versioned, queryable graph of requirements, constraints, entities, tables, equations, and deltas—with selective formal Lean4 integration.

---

## 3. Component Roles & Boundaries

| Component | Responsibility | Deliberate Non‑Goals |
|-----------|---------------|----------------------|
| **Extractor** | Multi-format structural + semantic enrichment + temporal deltas + anchor IDs | Generic retrieval, heavy LLM paraphrasing |
| **graph-memory-operator** | Graph persistence, embeddings, BM25, FAISS, event & recall orchestration | Low-level parsing |
| **SciLLM** (litellm fork) | Task orchestration, gated LLM calls, dataset generation, delta narratives, answer assembly with confidence breakdown | Full formal proof generation |
| **certainly** | Requirement IR, Lean4 lemma scaffolding, proof attempt & status classification | Generic QA or retrieval |
| **codeworld** | Code/document alignment (API symbols → spec paragraphs) | Requirement semantic parsing |
| **Scientist UX** | Morning triage: contradictions, ambiguous requirements, major deltas | Manual bulk re-keying |

---

## 4. End‑to‑End Overnight Flow (Target)

1. **Manifest Build**: Deduplicate & hash incoming PDFs/ReqIF/CSV (versions ordered).  
2. **Structural Extraction**: Pages → blocks → sections → tables/figures (anchors + stable IDs).  
3. **Semantic Layers**: Requirements, constraints, entities (signals/registers/fields), cross‑references, equations (optional), multi-row table header tier inference, units normalization.  
4. **Temporal Diffing**: Added / removed / modified; classify tighten / relax / broaden / narrow / reword.  
5. **Confidence & Salvage Scoring**: Unified block and requirement confidence.  
6. **Formalization** (certainly): IR build → lemma generation → Lean tactics attempt → status.  
7. **Graph & Index Load**: Nodes + edges + embeddings (selective).  
8. **Delta Narratives & QA Dataset** (SciLLM): Only high-impact + new deltas (gated by cost & novelty hash).  
9. **Report Assembly**: `run_report.md` + alert pack (contradictions, ambiguous requirements, high-risk relaxations).  
10. **Morning Scientist**: Execute complex temporal & compliance queries with citation & confidence transparency.

---

## 5. Foundational Principles

| Principle | Implementation Mechanism |
|----------|--------------------------|
| Deterministic First, LLM Last | Hash chain per stage; LLM only for ambiguity / salvage upgrades |
| Radical Provenance | Every answer returns anchor IDs + block hashes + delta IDs |
| Temporal Primacy | Delta graph edges are first-class, not an afterthought |
| Formalization Where Possible | Auto-IR + Lean lemma stubs; failure reasons recorded explicitly |
| Budget Discipline | Token budget ledger + gating policies + request hash cache |
| Transparency of Imperfection | Display ambiguity, failure, salvage, contradiction flags—never hide them |
| Incremental Re-runs | Hash invalidation dependency map; minimal recomputation |

---

## 6. Canonical Artifacts (Outputs)

| Artifact | Purpose | Key Fields |
|----------|---------|-----------|
| `anchor_manifest.json` | Global stable anchor registry | anchor_id, type, section_id, page_idx, hash |
| `07e_reflowed.json` | Per-section canonical blocks | blocks[], section metadata, content_hash |
| `requirements_enriched.json` | Requirement objects (raw → IR → formal) | modality, operator, value, unit, lemma_ref, formal_status |
| `constraints.json` | Structured quantitative bounds | subject, operator, normalized_value, unit, phase, source_anchor |
| `cross_refs.json` | Paragraph → (figure/table/section/equation) edges | source_paragraph, target_anchor, label, span |
| `entities.json` | Domain signals / registers / fields | entity_id, category, occurrences[], alias cluster (future) |
| `equations.json` | Equations + variable symbols | equation_id, text, variable_ids |
| `multi_header_tables.json` | Multi-row header tier reconstruction | table_anchor_id, header_tiers[][] |
| `deltas_enriched.json` | Version change objects | anchor_id, change_type, semantic_class, old/new signature |
| `confidence_report.json` | Unified scoring | per-anchor scores & components |
| `formalization_status.json` | Lean proof status summary | proved, sorry, unproved, ambiguous reasons |
| `delta_summaries.json` | Natural-language delta narratives | summary, anchors, change_type, confidence |
| `qa_pairs.jsonl` | Training dataset (curated) | question, answer, support_anchors[], provenance |
| `run_report.md` | Human oversight dashboard | counts, ratios, top failures, alerts |
| `formalization_gaps.json` | Requirements needing SME input | requirement_id, reason_code |
| `alerts.json` | Contradictions / relaxations / anomalies | type, severity, anchors |

---

## 7. Core Schemas (Simplified)

### 7.1 Anchor (All Blocks)
```json
{
  "anchor_id": "par::b8f1e2...",
  "block_type": "paragraph|table|figure|equation|requirement",
  "section_id": "sec_3_1",
  "page_idx": 12,
  "text": "...",
  "normalized_label": "table/5-2",
  "hash": "sha256:...",
  "confidence": 0.78,
  "provenance": { "stages": ["07a","07g","07h"], "source_pdf": "rev_2009.pdf" }
}
```

### 7.2 Requirement IR
```json
{
  "requirement_id": "SEC4-R012",
  "anchor_id": "par::abcd1234",
  "version": "rev_2024_11",
  "text": "The coolant pressure shall not exceed 220 psi during startup.",
  "modality": "shall_not_exceed",
  "subject": "coolant pressure",
  "predicate": { "type": "upper_bound", "value": 220, "unit": "psi", "phase": "startup" },
  "conditions": [{ "phase": "startup" }],
  "formal": {
    "lemma": "coolant_pressure_leq_220_startup",
    "status": "unproved|proved|sorry|ambiguous",
    "lean_module": "Specs.F16.Rev2024_11.Coolant",
    "hash": null
  },
  "ir_hash": "sha256:...",
  "ambiguity_flags": [],
  "provenance": { "extraction_hash": "sha256:...", "created_at": "..." }
}
```

### 7.3 Constraint Delta
```json
{
  "constraint_id": "con::coolant_pressure_max",
  "subject": "coolant pressure",
  "old": { "value": 220, "unit": "psi" },
  "new": { "value": 200, "unit": "psi" },
  "change_type": "modified",
  "semantic_class": "tightened",
  "anchors": { "old_anchor": "par::...", "new_anchor": "par::..." },
  "percent_change": -9.09
}
```

---

## 8. Temporal & Delta Model

| Semantic Class | Detection Rule |
|----------------|----------------|
| tightened | Same subject/operator/unit; new numeric < old |
| relaxed | Same subject/operator/unit; new numeric > old |
| reworded_no_semantic_change | Text diff; normalized IR same |
| scope_narrowed | New condition added (phase/time) |
| scope_broadened | Condition removed / generalized |
| deprecated | Removed w/o successor mapping |
| inverted | Operator direction flips (≤ → ≥) |

Delta classification drives alert ranking & QA dataset generation.

---

## 9. Formalization (Certainly) Lifecycle

| Stage | Input | Output | Failure Codes |
|-------|-------|--------|---------------|
| IR Build | Requirement text | IR JSON object | parser_failure |
| Disambiguation (optional LLM) | Vague IR | Updated IR + flags | ambiguous_subject, missing_unit |
| Lemma Generation | IR | Lean lemma skeleton | naming_conflict |
| Tactics Attempt | Lemma | status=proved/sorry/unproved | tactic_timeout, missing_assumption |
| SMT Sanity (optional) | IR set cluster | contradiction flags | smt_unsat |

Non-formalizable requirements produce reasoned suggestions.

---

## 10. SciLLM Orchestration Extensions

| Feature | Purpose |
|---------|---------|
| Task Registry | Declarative mapping (task_type → prompt + retrieval recipe + gating) |
| Retrieval Recipes | `ANCHOR_WINDOW`, `DELTA_EXPANSION`, `ENTITY_CLUSTER` |
| Cost Accountant | Enforces token ceilings; defers low-priority tasks |
| Request Hash Cache | Avoids duplicate summarization / classification work |
| Confidence-Aware Gating | Skips LLM if deterministic confidence sufficient |
| Dataset Generators | Requirements QA, delta narratives, entity definitions, contradiction verification pairs |
| Structured Output Validator | JSON schema enforcement with fallback to safe defaults |

---

## 11. Confidence & Transparency

**Answer Contract:**
```json
{
  "answer": "...",
  "anchors": ["par::...", "req::..."],
  "deltas_used": ["delta::..."],
  "confidence": 0.82,
  "confidence_detail": {
    "anchor": 0.83,
    "refs": 0.90,
    "formalization": 0.72,
    "delta_consistency": 0.95,
    "redundancy": 0.60,
    "penalty": -0.00
  },
  "unresolved_references": [],
  "limitation_note": "One requirement unproved (tactic timeout)."
}
```

Low-confidence answers (< threshold) are flagged “Provisional – needs review”.

---

## 12. Scientist Morning Workflow (Target)

1. Open summary dashboard (`run_report.md`).
2. Review Alert Panels:
   - Contradictions (resolve / mark false positive)
   - Tightened vs relaxed constraints
   - Ambiguous requirements (top 20 by risk)
3. Ask temporal/structural queries (e.g., “List all relaxed thermal constraints post-2015 that lack downstream mitigation references”).
4. Apply clarifications → triggers incremental partial re-run.
5. Export curated Q/A or delta narrative pack for stakeholders.

---

## 13. Evaluation & KPIs

| Metric | Phase 1 Target | Rationale |
|--------|----------------|-----------|
| Section boundary F1 | ≥ 0.90 | Structural reliability |
| Requirement classification precision | ≥ 0.90 | Normative extraction trust |
| Constraint delta recall | ≥ 0.85 | Temporal fidelity |
| Formalization coverage (proved+placeholder) | ≥ 75% | Breadth of machine representation |
| Ambiguity rate | ≤ 12% initial; trending downward | Quality improvement indicator |
| Unresolved reference ratio | ≤ 2% | Graph completeness |
| Average block confidence | ≥ 0.70 | Global extraction health |
| Cost per requirement (tokens) | ≤ 250 | Budget viability |
| Contradiction false positive rate | ≤ 20% | Alert quality |
| Query response provenance completeness | 100% | Trust principle |

---

## 14. Roadmap (Phased)

| Phase | Duration | Focus | Key Deliverables |
|-------|----------|-------|------------------|
| 0 – Stabilize | Weeks 1–2 | Anchor registry + cross-refs + requirement extraction | `anchor_manifest`, `cross_refs` |
| 1 – Semantics | Weeks 3–5 | Constraints, entities, deltas | `constraints`, `entities`, `deltas_enriched` |
| 2 – Formalization | Weeks 6–8 | Requirement IR + Lean integration | `requirements_enriched`, proof statuses |
| 3 – Depth | Weeks 9–11 | Equation extraction, multi-row headers | `equations`, `multi_header_tables` |
| 4 – Confidence & Gating | Weeks 12–13 | Unified scoring, salvage heuristics | `confidence_report` |
| 5 – Optimization & Datasets | Weeks 14–16 | QA dataset generation, delta narratives | `qa_pairs`, `delta_summaries` |
| 6 – Active Learning / Triage | Weeks 17+ | Low-confidence loop + UI refinements | `low_confidence_queue` |

---

## 15. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| OCR variance on older scans | Data loss / misparses | Salvage scoring + selective re-OCR |
| Over-merging tables or sections | Semantics distortion | Vertical gap + column asymmetry guards + multi-tier header detection |
| Hallucinated LLM titles/captions | Incorrect metadata | Token delta & semantic gating; fallback to deterministic header tier inference |
| Lean tactic blow-ups | Pipeline delays | Per-lemma timeout + classification + queue summary |
| Cost drift | Budget blowouts | Token budget ledger + stage ceilings |
| Ambiguity explosion (legacy phrasing) | Poor formalization coverage | Ambiguity lexicon + disambiguation queue |
| Missing delta links across structural rewrites | False “added” vs “modified” ratios | Hybrid anchor hash + fuzzy similarity (Jaccard + entity set) |

---

## 16. Open Decisions (Track Explicitly)

| Decision | Status | Owner |
|----------|--------|-------|
| Unit conversion normalization (psi → kPa canonical?) | Pending | Domain SME |
| Lean acceptance of `sorry` placeholders in MVP | Approved | Team |
| Equation extraction default on/off flag | Pending | Product |
| Embedding refresh policy (semantic vs text hash) | Pending | Retrieval Lead |
| Register/field alias resolution approach | Draft | Entity WG |

---

## 17. Backlog (Condensed Actionables)

| ID | Item | Priority | Effort (S/M/L) |
|----|------|----------|----------------|
| B01 | anchor_manifest emitter | P0 | S |
| B02 | cross-reference resolver (multi-label) | P0 | M |
| B03 | requirement IR + ambiguity tagging | P0 | M |
| B04 | constraint normalization (value/unit/operator) | P1 | M |
| B05 | delta classifier (tighten/relax/broaden/narrow) | P1 | M |
| B06 | entity extractor (signal/register/field + bit ranges) | P1 | M |
| B07 | confidence scorer + salvage metrics | P1 | S |
| B08 | Lean lemma generator + tactic cascade | P2 | M |
| B09 | multi-row header inference | P2 | M |
| B10 | equations + variable linker | P2 | M |
| B11 | version diff semantic classification upgrade | P2 | S |
| B12 | QA dataset composer (requirements, deltas) | P3 | M |
| B13 | contradiction detector (SMT check) | P3 | S |
| B14 | run_report.md generator | P3 | S |
| B15 | active learning queue (low-confidence) | P4 | S |

---

## 18. Glossary

| Term | Definition |
|------|------------|
| Anchor ID | Stable hash-derived identifier for a semantic block (paragraph/table/etc.) |
| Delta | Semantic change object between versions (added, modified, etc.) |
| Salvage Score | Heuristic measure of extraction completeness for degraded pages/tables |
| IR (Intermediate Representation) | Normalized structured form of a requirement |
| Formalization | Translating natural language requirement into Lean4 lemma/proof skeleton |
| Tightened Constraint | New upper bound strictly lower (or lower bound strictly higher) than previous |
| Ambiguity Flag | IR tag indicating lexical uncertainty (e.g., “adequate”, missing numeric) |
| Confidence Components | Breakdown (structure, references, formalization, redundancy, penalty) |
| Sorry Lemma | Lean lemma with placeholder proof accepted under relaxed compilation |
| Gating | Policy-based skip of LLM or expensive stage when deterministically resolvable |

---

## 19. Operating Principles for Imperfect Extraction

| Imperfection | Required UX Behavior |
|--------------|---------------------|
| Unformalized requirement | Show explicit reason + suggested rewrite pattern |
| Unresolved reference | Present label as-is + encourage manual relabel or alias addition |
| Low salvage | Visual badge + deprioritize for LLM polishing unless critical |
| Contradiction candidate | Provide side-by-side normalized forms + confidence + link to anchors |

---

## 20. “Why This Approach Works” (Executive Summary)

By decomposing extraction into deterministic semantic layers with stable anchors, layering targeted formalization and change detection, and gating expensive LLM operations only where ambiguity or high impact is detected, we turn an otherwise infeasible manual archival task into an **overnight pipeline** that produces **actionable temporal intelligence** with explicit provenance and transparent uncertainty—empowering a single domain expert to drive insight instead of drowning in raw PDFs.

---

## 21. Maintenance & Evolution Hooks

| Hook | Description |
|------|-------------|
| Hash Chain Registry | Central JSON listing stage → hash component |
| Stage Capability Flags | Environment toggles enabling selective disabling (e.g., `ENABLE_EQUATIONS=0`) |
| Semantic Cache TTL | Invalidate stale semantic outputs after major IR schema revisions |
| Event Bus Integration | `semantic_layers_ready`, `formalization_batch_complete`, `delta_alert` events |
| Evaluation Harness | Gold sets measuring coverage & precision tracked over time |

---

## 22. Future (Stretch) Enhancements

| Idea | Value |
|------|-------|
| Temporal Embedding Drift Vectors | Detect conceptual shifts in requirement language |
| Constraint Impact Modeling | Propagate tightened constraints to dependent subsystems |
| Graph-Based Query Language (Domain DSL) | “SHOW CHANGES COOLANT_PRESSURE 2005..2024 WHERE tighten_pct > 5” |
| Lean4 Auto-Refinement via Active Learning | Suggest disambiguations informed by prior clarifications |
| Domain Ontology Integration (MIL/NRC) | Map requirements to regulatory taxonomy codes |
| Multi-doc Comparative Delta Summaries | Cross-product / cross-platform evolution analytics |

---

## 23. Living Document Update Protocol

- Update after: (a) major schema changes, (b) new semantic stage addition, (c) KPI target shifts.
- Keep a `changelog` appendix (deferred until first revision).
- PR requirement: any new stage must reference which section(s) of this document it fulfills or modifies.

---

## 24. Quick Status Checklist (Use in PR Templates)

| Area | Implemented? | Notes |
|------|--------------|-------|
| Anchors & Hashing | ☐ | 07a/07e upgraded? |
| Cross-References | ☐ | 07g present? |
| Requirement IR + Modality | ☐ | 07h output stable? |
| Constraints & Deltas | ☐ | Tighten/relax classification working? |
| Formalization Pipeline | ☐ | Lean modules generated & status codes |
| Confidence Report | ☐ | Component breakdown present |
| Salvage Metrics | ☐ | OCR/table salvage tracked |
| Contradictions Detection | ☐ | SMT or heuristic phase implemented |
| run_report.md | ☐ | Generated automatically |
| QA Dataset Generation | ☐ | High-confidence sample export |
| Active Learning Queue | ☐ | Low-confidence list available |

---

## 25. Immediate Next Confirmations (Before Further Refactor)

| Question | Decision (Fill in) |
|----------|--------------------|
| Canonical unit set & conversions baseline | TBD |
| IR schema versioning policy | TBD |
| Lean acceptance of `sorry` in production artifacts | TBD |
| Equation extraction default enabled? | TBD |
| Constraint diff threshold for “significant” (%) | TBD |

---

**END OF SPEC (v1.0)**  
_Last updated: {{INSERT_DATE_ON_COMMIT}}_

> Maintain discipline: if a new capability isn’t reflected here, it’s not a “first-class citizen” yet. Keep this current to prevent architectural drift.