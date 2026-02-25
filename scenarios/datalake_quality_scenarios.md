# F-35 Datalake Quality Scenarios

## Program Context

The F-35 Joint Strike Fighter (JSF) is a multi-decade, $1.7T lifecycle program with
three variants (A/B/C), 1,900+ suppliers across 11 partner nations, and ~800,000 pages
of technical documentation per aircraft block upgrade.

**Margaret Chen** — Pratt & Whitney, West Palm Beach. Propulsion IPT lead for the
F135 engine. Her world is DO-178C, AS9100, turbine inlet temperatures, FADEC software,
and tracking requirements traceability from P&W subcontractors (e.g., Honeywell for
the FADEC, GKN for fan blades). She's dealt with Block 4 engine enhancement requirements
drifting from the original Block 3F baseline and needs to know when a vendor's
deliverable contradicts the prime spec.

**Jennifer Cheung** — NIWC Pacific, San Diego. Systems engineer on the F-35C carrier
variant mission systems. Her world is MIL-STD-1553, Link 16, cybersecurity (RMF/STIG),
and the DAS/EO-DAS sensor fusion subsystem. She coordinates between Northrop Grumman
(radar/DAS), BAE Systems (EW suite), and the JSF Program Office. She needs to track
requirements flow-down from the system spec (SDD) through subsystem specs to vendor
test reports across block upgrades.

**The datalake** contains extracted technical documents: vendor specs, test reports,
requirements documents, ICD sheets, FMEA analyses, cybersecurity assessment reports,
and airworthiness qualification packages — all processed through our extractor pipeline.

---

## Level 1: Program Orientation

_Margaret and Jennifer just got access to the datalake. They need to understand what's
in it before they can do real work._

### 1.1 Margaret — Inventory check
> "How many documents are in the datalake? Break them down by source type — I need to
> know how many are PDFs from vendor deliverables vs HTML from spec portals."

**Tests:** Collection count, asset_type distribution, basic state awareness.

### 1.2 Jennifer — Coverage assessment
> "Do we have any documents related to MIL-STD-1553 or Link 16 data bus specs?
> What about STIG checklists?"

**Tests:** BM25 text search, domain-specific terminology recall.

### 1.3 Margaret — Fragmentation check
> "Which documents have the most chunks? If a 30-page engine spec got split into
> 200 chunks, something's wrong with the extraction."

**Tests:** Per-doc chunk count aggregation, over-fragmentation detection.

### 1.4 Jennifer — Embedding quality
> "How many chunks have real embeddings vs zero vectors? I don't want to search
> against content that won't show up in semantic queries."

**Tests:** Data quality audit on embedding field, readiness for semantic search.

### 1.5 Margaret — Vendor inventory
> "List all documents that mention Honeywell, GKN Aerospace, or Rolls-Royce.
> I need to know which vendor deliverables we've ingested."

**Tests:** Multi-term BM25, entity-level filtering across vendor names.

### 1.6 Jennifer — Classification gaps
> "Are any of the documents marked as ITAR or CUI? We need to make sure
> controlled content isn't leaking into the wrong collections."

**Tests:** Content classification, security marking detection.

---

## Level 2: Find Specific Content

_Now they know what's in the datalake. They need to find specific engineering content
for their daily work._

### 2.1 Margaret — Thermal requirements
> "Show me any tables about turbine inlet temperature limits. I'm looking for
> the T41 max value from the Block 4 engine enhancement spec."

**Tests:** BM25 search for engineering-specific terms, table content retrieval.

### 2.2 Jennifer — Cybersecurity controls
> "Find all sections that discuss RMF control families — specifically AC
> (Access Control) and IA (Identification and Authentication) for the
> mission computer."

**Tests:** Domain-specific acronym search, section-level retrieval.

### 2.3 Margaret — Requirements with IDs
> "Find requirements that have traceability IDs like 'F135-SRS-xxxx' or
> 'PWA-REQ-xxxx'. Show me the requirement text and which document they came from."

**Tests:** Pattern-based content search, requirement ID preservation check.

### 2.4 Jennifer — Interface control documents
> "Show me the ICD tables between the DAS sensor and the mission computer.
> I need the message formats and data rates."

**Tests:** Table retrieval for ICD-specific content, multi-column table formatting.

### 2.5 Margaret — Test report results
> "Find any test reports that mention 'endurance test' or 'accelerated mission
> test' for the F135. Show me the pass/fail results tables."

**Tests:** Cross-document search, test result table extraction.

### 2.6 Jennifer — FMEA content
> "Do we have any Failure Mode and Effects Analysis documents? Show me the
> risk priority numbers for the highest-severity items."

**Tests:** Document type discovery, FMEA-specific table structure.

---

## Level 3: Cross-Document Analysis

_This is where the datalake earns its keep. Single-document search is Google.
Cross-document analysis is why we built this._

### 3.1 Margaret — Requirements delta across blocks
> "Compare the turbine inlet temperature requirements between the Block 3F
> baseline spec and the Block 4 enhancement spec. What changed? Did any
> vendor get a different limit than the prime spec states?"

**Tests:** Cross-document comparison, requirements drift detection, vendor vs prime delta.

### 3.2 Jennifer — Duplicate tables across vendors
> "I've seen at least three different vendors submit interface tables for
> the 1553 bus. Find all tables that describe 1553 message formats and
> tell me if they're consistent or if there are conflicts."

**Tests:** Cross-doc table dedup, conflict detection across vendor deliverables.

### 3.3 Margaret — Requirements flow-down verification
> "Take requirement F135-SRS-4201 (max turbine inlet temp) and trace it
> down through the subcontractor specs. Did Honeywell's FADEC spec and
> GKN's fan blade spec both reference the same limit value?"

**Tests:** Requirements traceability chain, multi-hop graph traversal.

### 3.4 Jennifer — Cybersecurity inheritance
> "The system-level RMF package says the mission computer inherits SC-28
> (Protection of Information at Rest) from the platform. But the subsystem
> spec says it implements its own. Which is it? Show me both documents."

**Tests:** Contradiction detection, control inheritance vs implementation conflict.

### 3.5 Margaret — Unit consistency
> "Find all tables that specify pressure values. Some vendors use PSI,
> others use kPa, and I've seen at least one use bar. Flag any document
> where the same parameter appears in different units."

**Tests:** Unit extraction, cross-document consistency check, computation.

### 3.6 Jennifer — Spec version cross-reference
> "We have three versions of the DAS ICD — v2.1, v3.0, and v3.2. What
> requirements were added in v3.0 and which were removed in v3.2?
> Generate a delta report."

**Tests:** Version-aware diff, requirements addition/removal tracking.

---

## Level 4: Extraction Quality Forensics

_Margaret and Jennifer are now power users. They're finding extraction bugs through
real usage — the most valuable quality signal possible._

### 4.1 Margaret — Split table detection
> "This thermal limits table was split across two chunks — the header row is
> in one chunk and the data rows are in another. Why weren't they merged?
> Show me both pieces so I can see what the pipeline did wrong."

**Tests:** Table merger (S05c) failure diagnosis, cross-chunk table reconstruction.

### 4.2 Jennifer — Section hierarchy collapse
> "The NIST 800-171 document shows all sections as top-level. But the
> original PDF has nested subsections (3.1, 3.1.1, 3.1.2). The section
> builder lost the hierarchy. What happened?"

**Tests:** S04 section builder depth detection failure, hierarchy reconstruction.

### 4.3 Margaret — Requirements ID stripping
> "The extracted requirements from the P&W spec don't have their traceability
> IDs — the pipeline stripped 'F135-SRS-4201' and just kept the text.
> Show me the raw extraction vs what's in the datalake."

**Tests:** S08 requirements extraction, ID preservation, data loss detection.

### 4.4 Jennifer — Table header misalignment
> "This table has merged header cells that span multiple columns. The
> extraction turned it into garbage — column 3 data ended up under
> column 2's header. Show me the HTML in the chunk."

**Tests:** Complex table extraction (colspan/rowspan), S05 Camelot strategy selection.

### 4.5 Margaret — Figure without description
> "The turbine blade stress analysis figure on page 47 was extracted but
> has no description. The VLM describer should have generated one.
> Did S06b skip it? Why?"

**Tests:** S06b figure describer coverage gap, VLM call failure.

### 4.6 Jennifer — Equation misclassification
> "The Shannon entropy formula in the cybersecurity assessment got extracted
> as a figure caption instead of an equation block. The LaTeX is missing."

**Tests:** Block classification error, equation vs figure boundary.

### 4.7 Margaret — Annotation overlay verification
> "Show me the annotated PDF overlay for the engine spec. I want to see
> where the section boundaries were drawn — they look wrong around the
> appendices."

**Tests:** /create-annotated-pdf integration, visual verification.

---

## Level 5: Corrective Actions

_They've found the bugs. Now they want fixes — and they want the pipeline to learn._

### 5.1 Margaret — Force table merge
> "The thermal limits table on pages 12-13 was split. Merge chunks
> datalake_chunks/a3f8... and datalake_chunks/b7c2... into a single table.
> Re-run S05c with merge_across_pages=true for this document."

**Tests:** Targeted S05c re-run, datalake chunk update, merge parameter override.

### 5.2 Jennifer — Fix section hierarchy
> "Re-extract the NIST 800-171 document with font-size-based section
> detection instead of regex. The current extraction missed the hierarchy."

**Tests:** S04 re-run with profile override, before/after comparison.

### 5.3 Margaret — Batch re-extract worst performers
> "Show me the 10 documents with the worst content_coverage scores.
> Re-extract them all with the 'accurate' preset and compare results."

**Tests:** Quality metrics → batch re-extraction → delta scoring.

### 5.4 Jennifer — Fix HTML entity encoding
> "The ATT&CK HTML chunks still have &amp; and &#x27; in them. Run the
> normalize skill on all HTML-sourced chunks and update the datalake."

**Tests:** /normalize integration, bulk chunk update.

### 5.5 Margaret — Vendor deliverable re-ingestion
> "Honeywell submitted a revised FADEC spec (Rev D). The old Rev C is in
> the datalake. Ingest Rev D, mark Rev C as superseded, and flag any
> requirements that changed between revisions."

**Tests:** Document versioning, supersedence marking, requirements diff.

### 5.6 Jennifer — Annotation correction
> "The section boundaries on the RMF assessment are wrong — Section 3.2
> starts on page 8, not page 7. Fix the annotations and re-export."

**Tests:** Manual annotation correction, re-export to datalake.

---

## Level 6: Learning & Convergence

_The full loop: find problem → diagnose → fix → learn → verify improvement → certify._

### 6.1 Margaret — Pattern-based lesson
> "Every Pratt & Whitney spec we extract loses the traceability ID column
> in requirements tables because the column header says 'Para.' instead of
> 'Requirement ID'. Create a lesson so the pipeline maps 'Para.' to
> requirement IDs for P&W documents."

**Tests:** Failure pattern → lesson → memory store → S08 prompt augmentation.

### 6.2 Jennifer — Extraction convergence tracking
> "We've re-extracted the NIST 800-171 document three times now. Show me
> the quality scores for each extraction. Are we converging or thrashing?"

**Tests:** Multi-run quality tracking, convergence vs oscillation detection.

### 6.3 Margaret — Vendor gap analysis
> "Of the 47 F135 vendors, which ones have NOT submitted deliverables to
> the datalake? Cross-reference against the vendor list in the program
> management plan."

**Tests:** Coverage gap analysis, cross-document entity extraction.

### 6.4 Jennifer — Classifier training from mistakes
> "The pipeline keeps classifying STIG checklists as regular tables instead
> of requirements. Collect the 20 worst misclassifications and train a
> classifier to detect STIG format."

**Tests:** Failure collection → /create-classifier → pipeline integration.

### 6.5 Margaret — Certification package
> "Generate the DO-178C qualification package for the extractor pipeline
> itself. I need to show that our extraction tool meets the same rigor
> we apply to FADEC software. Content coverage must be >= 0.95 across
> all P&W documents."

**Tests:** Full /extractor-quality-check at certification-level thresholds.

### 6.6 Jennifer — Cross-collection contradiction detection
> "Cross-reference all extracted requirements in datalake_chunks against
> the SPARTA QRA cybersecurity controls. Flag any place where a vendor's
> security implementation contradicts a NIST control."

**Tests:** Cross-collection graph traversal (datalake_chunks ↔ sparta_qra),
contradiction detection, escalation to program office.

---

## Implementation Roadmap

### Today (Levels 1-2): Recall works
- BM25 text search via `datalake_chunks_search` view (18,113 chunks)
- Formatter returns text, doc_id, asset_type, page, section_id, bridge_tags
- `/ask Margaret Chen "..."` routes through recall

### Next (Level 3): Cross-doc reasoning
- AQL aggregation queries for inventory metrics
- Graph traversal via `datalake_edges` for doc→chunk navigation
- Cross-document comparison prompts in the ask skill

### Then (Level 4): Quality forensics
- Integration with 7-dimension quality scoring framework
- `/create-annotated-pdf` for visual verification
- Before/after comparison helpers

### Later (Level 5): Corrective actions
- Agent-inbox dispatch for pipeline re-run triggers
- Targeted S05c/S04/S08 re-runs from ask queries
- Bulk re-extraction with quality delta tracking

### Finally (Level 6): Full convergence loop
- Lesson store integration (failure → lesson → prompt augmentation)
- Multi-run convergence tracking
- Cross-collection joins (datalake ↔ sparta_qra)
- Certification-ready reporting at dynamic annealing thresholds
