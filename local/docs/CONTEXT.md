# CONTEXT.md - Learn Datalake / Review PDF Handoff

**Last Updated**: 2026-02-19
**Session Focus**: Monitoring convergence after deploying S04 section detection fixes + S05c ML merge classifier
**Primary Working Repo**: `/home/graham/workspace/experiments/pi-mono` (skills)
**Secondary Repo**: `/home/graham/workspace/experiments/extractor` (pipeline code)

---

## Current State

- `learn-datalake` supervised loop running: `corpus_1771526964`, 8 workers, `--inline-review`
- Supervisor command: `./run.sh start-supervised /mnt/storage12tb/extractor_corpus --label corpus --workers 8 --task-monitor --task-monitor-project datalake_training --inline-review`
- Restart count: 247, run count: 268
- Heartbeat: fresh
- Memory server: healthy on port 8601

### Improvements Deployed

1. **S04 adaptive font threshold** — `body_font_size + 1pt` (reduced from +2pt) instead of fixed 11pt (s04_section_builder.py:96)
2. **S04 TOC demotion threshold** — `s03_confidence < 0.70` instead of 0.90 (s04_section_builder.py:1052)
3. **S05c ML merge classifier** — Logistic regression on 8 tabular features, F1=0.802, `USE_MERGE_CLASSIFIER=true` in .env
4. **S04 TOC text normalization** — `_normalize_toc_text()` strips Roman numerals (I, II, III...), decimal prefixes, letter prefixes before matching. `_toc_fuzzy_match()` provides 80% word-overlap fallback. (s04_section_builder.py:131-165)
5. **`looks_like_header_text()` regex fix** — Now matches single-level decimal numbering `1. Title` (was only matching multi-level `1.1 Title`). (section_builder_utils_local.py:213)

### Convergence Results (Run corpus_1771526964 vs Baseline 1771515898)

| Metric | Baseline (84 verdicts) | Current (13 verdicts) | Delta |
|---|---|---|---|
| **Overall avg** | 0.835 | **0.941** | **+0.106** |
| **PASS rate** | 3.6% | **92.3%** | **+88.7pp** |
| **WARN rate** | 82.1% | 7.7% | -74.4pp |
| **FAIL rate** | 14.3% | **0.0%** | **-14.3pp** |

### Issue Code Shift

| Issue | Baseline | Current | Interpretation |
|---|---|---|---|
| section_overseg | 49 (58%) | 6 (46%) | S04 fixes working |
| table_recall_low | 21 (25%) | 7 (54%) | Now dominant issue |
| figure_recall_low | 102 (121%) | 0 (0%) | Eliminated |
| table_overextract | 3 (4%) | 1 (8%) | Stable |

### Remaining Quality Gap

- **table_recall_low** is the #1 issue (54% of verdicts with escalations)
- Only WARN: PDF `0050f308` score=0.760, flat trajectory [0.76, 0.76, 0.76] despite 3 remediation iterations
- Root cause: Camelot lattice mode can't detect borderless tables (datasheets, specs)
- ML merge classifier helps with cross-page merging but doesn't solve detection of borderless tables
- Needs: stream mode table detection or vision-based approach

---

## Score Trajectory (Historical)

```
0.659 → 0.718 → 0.784 → 0.786 → 0.810 → 0.818 → 0.843 → 0.848 → 0.945 → 0.941
```

Each jump corresponds to a specific fix documented in MEMORY.md.

---

## Plan File: Table Merge Classifier

Active plan at `~/.claude/plans/bright-kindling-kay.md`:
- **All phases complete** (1-5): Data collection → benchmark → train → inference API → S05c integration
- Model: Logistic regression, 8 tabular features, 2435 training pairs, F1=0.802
- Deployed: `USE_MERGE_CLASSIFIER=true` in `.env`
- Model path: `pi-mono/.pi/skills/create-table-classifier/models/merge-classifier-final/`

---

## Key Architecture

- **Convergence pattern**: Extract → Assess (review-pdf) → Gate (PASS/WARN into memory, FAIL quarantined) → Track convergence → Loop
- **Quality gate**: 7 dimensions (content_coverage 0.22, section_alignment 0.18, table_fidelity 0.16, equation_fidelity 0.14, ordering_yx 0.12, figure_fidelity 0.10, data_quality 0.08)
- **Grade thresholds**: A+ ≥0.95, A ≥0.88, B ≥0.78, C ≥0.65, F <0.65. **Never lower thresholds.**
- **Inline review**: Per-PDF scoring → persona review → /memory storage → escalation → remediation → re-extract (max 3 iterations)

---

## How To Continue

### 1) Check loop status
```bash
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake
./run.sh status-supervised --table
```

### 2) Tail current run log
```bash
tail -50 /home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/state/runs/learn_datalake_corpus_1771526964.log
```

### 3) Parse verdicts from current run
```bash
grep 'inline_review verdict=' <log> | sed 's/.*verdict=\([^ ]*\) score=\([^ ]*\).*/\1 \2/'
```

### 4) If supervisor dies, restart
```bash
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake
./run.sh start-supervised /mnt/storage12tb/extractor_corpus --label corpus --workers 8 --task-monitor --task-monitor-project datalake_training --inline-review
```

### 5) Check agent inbox
```bash
python3 ~/.claude/skills/agent-inbox/inbox.py check --project extractor
```

---

## Key Files To Read First

- `pi-mono/.pi/skills/learn-datalake/supervise_learn_datalake.py` — supervisor
- `pi-mono/.pi/skills/review-pdf/verify/scoring.py` — quality scoring
- `pi-mono/.pi/skills/review-pdf/verify/analysis.py` — extraction analysis
- `extractor/src/extractor/pipeline/steps/s04_section_builder.py` — section detection (recent fixes)
- `extractor/src/extractor/pipeline/steps/s05c_table_merger.py` — table merger (ML classifier)
- `pi-mono/.pi/skills/create-table-classifier/scripts/merge_inference.py` — merge model inference

---

## Notes For Incoming Agent

- **Do not stop the supervised loop** — it's running and producing good results
- **Query memory first** — `./run.sh recall --q "your topic"` before scanning code
- **Check agent-inbox** — cross-project collaboration with memory project is active
- **table_recall_low is the next frontier** — borderless table detection needs stream mode or vision approach
- **S04 and merge classifier changes are uncommitted** — commit when 20+ verdicts confirm improvement
- **S04 TOC normalization + header regex fixes deployed** — new extractions will use improved section detection (Roman numerals, single-level decimal numbering). Monitor section_oversegmentation count in next batch of verdicts.
- The critical execution contract: Extract → Assess → Gate → Track convergence → Loop
