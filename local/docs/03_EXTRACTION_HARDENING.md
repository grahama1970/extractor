# Task List: PDF Extraction Hardening (Continuous Service)

## Vision

**This is not a one-time process - it's a continuously running service that:**
1. Never stops collecting and testing PDFs
2. Learns failure patterns and builds a classifier model
3. Automatically improves extraction quality over time
4. Feeds learned patterns back into the pipeline

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PDF LEARNING SERVICE (Continuous)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌──────────────┐     ┌─────────────────────────┐  │
│  │ PDF Sources │────▶│  Extraction  │────▶│   Pattern Classifier   │  │
│  │  - arXiv    │     │   Pipeline   │     │   (failure detection)  │  │
│  │  - web      │     │  (14 stages) │     │                        │  │
│  │  - corpus   │     └──────────────┘     └────────────┬────────────┘  │
│  └─────────────┘                                       │               │
│                                                        ▼               │
│                         ┌──────────────────────────────────────────┐   │
│                         │           ArangoDB / Memory               │   │
│                         │  - Learned failure patterns               │   │
│                         │  - Classifier training data               │   │
│                         │  - Edge case examples                     │   │
│                         └──────────────────────────────────────────┘   │
│                                                        │               │
│                                                        ▼               │
│                         ┌──────────────────────────────────────────┐   │
│                         │         Auto-Fix Suggestions              │   │
│                         │  - Pattern-specific remediation           │   │
│                         │  - Pipeline parameter tuning              │   │
│                         │  - Preprocessor recommendations           │   │
│                         └──────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Classifier Model Design

### Features for Classification
- Page count, file size, DPI
- Font diversity score
- Table candidate density
- Figure/image ratio
- Unicode complexity score
- Column layout detection
- Header heuristic scores

### Classification Categories
1. **CLEAN** - Extracts perfectly
2. **FIXABLE** - Known patterns, auto-fix available
3. **PROBLEMATIC** - Needs manual review
4. **ADVERSARIAL** - Edge case, add to test corpus

### Training Data Sources
- `/mnt/storage12tb/extractor_corpus/results/` - extraction outcomes
- `batch_summary.jsonl` - quality signals per document
- Pattern annotations from `/memory`

### Future: /create-classifier Skill
Location: `/home/graham/workspace/experiments/pi-mono/.pi/skills/create-classifier/`
Purpose: Generic skill to train classifiers from labeled data
Inputs: features.parquet + labels.jsonl
Outputs: model.pkl + evaluation metrics

## Running the Continuous Service

### As a Background Process
```bash
# Run the daemon directly
python scripts/pdf_learning_daemon.py \
    --corpus /mnt/storage12tb/extractor_corpus \
    --interval 300  # Check every 5 minutes
```

### As a Systemd Service
```bash
# Install the service
sudo cp scripts/pdf-learning-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pdf-learning-daemon
sudo systemctl start pdf-learning-daemon

# Check status
sudo systemctl status pdf-learning-daemon
sudo journalctl -u pdf-learning-daemon -f
```

### Adding New PDFs
Drop PDFs into any of these directories:
- `/mnt/storage12tb/extractor_corpus/adversarial/` - Synthetic edge cases
- `/mnt/storage12tb/extractor_corpus/engineering/` - Requirements docs
- `/mnt/storage12tb/extractor_corpus/arxiv/` - Academic papers
- `/mnt/storage12tb/extractor_corpus/incoming/` - User-submitted PDFs

The daemon will automatically process new files on the next check interval.

### Analyzing Results
```bash
# Run failure collector
python scripts/failure_collector.py \
    --corpus /mnt/storage12tb/extractor_corpus

# Watch mode for live monitoring
python scripts/failure_collector.py \
    --corpus /mnt/storage12tb/extractor_corpus \
    --watch

# Extract classifier features
python scripts/extract_classifier_features.py \
    --corpus /mnt/storage12tb/extractor_corpus \
    --output /mnt/storage12tb/extractor_corpus/classifier
```

## Corpus Location (12TB Drive)

```
/mnt/storage12tb/extractor_corpus/
├── adversarial/           # Synthetic edge cases
├── engineering/           # Real-world requirements docs
├── arxiv/                 # Academic papers (continuous growth)
├── results/               # Extraction outputs + quality signals
│   └── batch_summary.jsonl
└── classifier/            # Model training data
    ├── features.parquet   # Document features
    ├── labels.jsonl       # Classification labels
    └── model.pkl          # Trained classifier
```

## Context (Original)

Systematic discovery and fixing of PDF extraction edge cases using:
- `/fixture-tricky` for synthetic adversarial PDFs
- `/debug-pdf` for failure analysis
- Real engineering/scientific documents as stress tests
- Memory storage for learned patterns

## Test Corpus Locations

```
test_corpus/
├── adversarial/           # Synthetic edge cases from /fixture-tricky
│   ├── cursed_text.pdf    # Ligatures, math, invisible chars
│   ├── false_tables.pdf   # Text falsely detected as tables
│   ├── layout_traps.pdf   # Deep nesting, out-of-order
│   ├── malformed_tables.pdf
│   └── gauntlet_all.pdf   # All patterns combined
│
├── engineering/           # Real-world stress tests
│   ├── NASA_SP-2016-6105.pdf          # Requirements spec
│   ├── 2505.03335v2_marked.pdf        # Annotated arXiv
│   ├── CV32A65X_architecture.pdf      # RISC-V design doc
│   ├── HARDENS_ML22326A307.pdf        # Regulatory doc
│   └── nvidia-ampere-whitepaper.pdf   # GPU architecture
│
└── arxiv/                 # Papers from arXiv (to be collected)
    ├── cs.CL/             # Computational Linguistics (LLM papers)
    ├── cs.AI/             # AI research
    ├── cs.LG/             # Machine Learning
    └── math.OC/           # Optimization (heavy equations)
```

## Edge Case Categories to Test

### 1. False-Positive Tables
- numbered-list, address-block, code-block
- signature-block, key-value-pairs, toc-entries
- receipt-text, form-fields, toc-with-pagenums

### 2. Malformed Tables
- missing-columns, ragged-rows, empty-cells-chaos
- merged-simulation, numeric-alignment-hell, unicode-in-tables

### 3. Cursed Text
- ligatures (fi, fl, ff), math-notation
- subscript-superscript, lookalike-chars (homoglyphs)
- invisible-chars, mixed-numbers

### 4. Layout Traps
- deep-nesting (10+ levels), footnote-sections
- sidebar-content, out-of-order
- page-number-sections, partial-header
- sentence-as-header, allcaps-header-missed

## Crucial Dependencies

| Tool | Purpose | Sanity Script |
|------|---------|---------------|
| fixture-tricky | Generate adversarial PDFs | /fixture-tricky gauntlet |
| debug-pdf | Analyze failures | /debug-pdf sanity |
| pipeline_hardening.py | Bulk analysis | scripts/pipeline_hardening.py --help |
| self_healing_extractor | Pattern detection | test_self_healing_extractor.py |

## Tasks

### Phase 1: Adversarial PDF Testing (Day 1)

- [ ] **Task 1.1**: Run extractor on gauntlet_all.pdf and record failures
  - Agent: general-purpose
  - Parallel: 0
  - **Definition of Done**:
    - Test: Run pipeline on gauntlet_all.pdf
    - Assertion: Document which patterns fail extraction

- [ ] **Task 1.2**: Run extractor on each adversarial PDF individually
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1.1
  - **Definition of Done**:
    - Test: cursed_text.pdf, false_tables.pdf, layout_traps.pdf, malformed_tables.pdf
    - Assertion: Categorize failures by pattern type

- [ ] **Task 1.3**: Use /debug-pdf to analyze failures
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1.2
  - **Definition of Done**:
    - Test: Generate debug fixtures for top 5 failure patterns
    - Assertion: Minimal reproducible fixtures created

### Phase 2: Engineering Document Testing (Day 1-2)

- [ ] **Task 2.1**: Run extractor on NASA requirements doc
  - Agent: general-purpose
  - Parallel: 1
  - **Definition of Done**:
    - Test: Extract NASA_SP-2016-6105.pdf
    - Assertion: Requirements IDs extracted, tables detected

- [ ] **Task 2.2**: Run extractor on CV32A65X architecture doc
  - Agent: general-purpose
  - Parallel: 1
  - **Definition of Done**:
    - Test: Extract CV32A65X_architecture.pdf
    - Assertion: Diagrams captioned, sections structured

- [ ] **Task 2.3**: Run extractor on NVIDIA whitepaper
  - Agent: general-purpose
  - Parallel: 1
  - **Definition of Done**:
    - Test: Extract nvidia-ampere-whitepaper.pdf
    - Assertion: Multi-column handled, figures extracted

- [ ] **Task 2.4**: Run extractor on HARDENS regulatory doc
  - Agent: general-purpose
  - Parallel: 1
  - **Definition of Done**:
    - Test: Extract HARDENS_ML22326A307.pdf
    - Assertion: Requirements captured with compliance markers

### Phase 3: ArXiv Paper Collection (Day 2)

- [ ] **Task 3.1**: Search arXiv for LLM papers with complex tables
  - Agent: general-purpose
  - Parallel: 0
  - **Definition of Done**:
    - Test: /arxiv search "large language model benchmark" -n 20
    - Assertion: Download 20 PDFs with tables/figures

- [ ] **Task 3.2**: Search arXiv for math-heavy papers
  - Agent: general-purpose
  - Parallel: 0
  - **Definition of Done**:
    - Test: /arxiv search "optimization neural network convergence" -c math.OC -n 20
    - Assertion: Download 20 PDFs with equations

- [ ] **Task 3.3**: Search arXiv for transformer architecture papers
  - Agent: general-purpose
  - Parallel: 0
  - **Definition of Done**:
    - Test: /arxiv search "transformer attention mechanism architecture" -n 20
    - Assertion: Download 20 PDFs with diagrams

### Phase 4: Bulk Extraction & Pattern Analysis (Day 2-3)

- [ ] **Task 4.1**: Run pipeline_hardening.py analyze on full corpus
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 3.1, Task 3.2, Task 3.3
  - **Definition of Done**:
    - Test: python scripts/pipeline_hardening.py analyze test_corpus/
    - Assertion: analysis.json with pattern frequencies

- [ ] **Task 4.2**: Run batch extraction on full corpus
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 4.1
  - **Definition of Done**:
    - Test: python scripts/pipeline_hardening.py run-batch test_corpus/
    - Assertion: batch_results.json with success/failure for each doc

### Phase 5: Iterative Hardening (Day 3-4)

- [ ] **Task 5.1**: Fix top 3 failure patterns
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 4.2
  - **Definition of Done**:
    - Test: Re-run failed extractions
    - Assertion: Failure rate reduced by 50%+

- [ ] **Task 5.2**: Store learned patterns in /memory
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5.1
  - **Definition of Done**:
    - Test: /memory learn for each fixed pattern
    - Assertion: Patterns stored with solutions

- [ ] **Task 5.3**: Update failure_detector.py with new patterns
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5.1
  - **Definition of Done**:
    - Test: tests/test_failure_detector.py
    - Assertion: New patterns detected correctly

### Phase 6: Verification & Documentation (Day 4)

- [ ] **Task 6.1**: Re-run full corpus extraction
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5.3
  - **Definition of Done**:
    - Test: python scripts/pipeline_hardening.py run-batch test_corpus/
    - Assertion: >90% success rate

- [ ] **Task 6.2**: Update CHANGELOG.md with hardening results
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 6.1
  - **Definition of Done**:
    - Test: CHANGELOG.md has [1.2.0] entry
    - Assertion: Lists all patterns fixed

## Completion Criteria

1. 100+ documents processed through extraction pipeline
2. Top 10 failure patterns identified and documented
3. 50%+ of identified patterns fixed
4. All fixes stored in /memory for future recall
5. Success rate >90% on test corpus

## Questions/Blockers

None - proceed with automated testing.

## Background Execution

Run with task-monitor for progress tracking:
```bash
# Start task monitor TUI
python .pi/skills/task-monitor/monitor.py &

# Run orchestrator
/orchestrate 03_EXTRACTION_HARDENING.md
```

Or run phases individually:
```bash
# Phase 1: Adversarial testing
python scripts/pipeline_hardening.py analyze test_corpus/adversarial/

# Phase 2: Engineering docs
python scripts/pipeline_hardening.py run-batch test_corpus/engineering/

# Phase 4: Full corpus
python scripts/pipeline_hardening.py run-batch test_corpus/ --output batch_results.json
```
