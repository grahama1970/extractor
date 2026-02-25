# Extractor Pipeline Improvement Plan

> Generated: 2026-02-04
> Author: Claude (Opus 4.5)
> Status: ACTIVE

## Executive Summary

Assessment of the extractor project revealed that **all blocking and high-priority issues from 01_TASKS.md have been resolved**. This plan outlines verification steps, remaining cleanup tasks, and future improvements leveraging the pi-mono skills ecosystem.

---

## Phase 1: Verification & Cleanup (Immediate)

### 1.1 Verify Task Completion Status

| Task Range | Category | Status | Action |
|------------|----------|--------|--------|
| TASK-001 to TASK-004 | Blocking | ✅ VERIFIED COMPLETE | Update docs |
| TASK-005 to TASK-008 | Sanity Functions | ✅ VERIFIED COMPLETE | Update docs |
| TASK-009 to TASK-012 | Code Quality | ⚠️ NEEDS VERIFICATION | Verify each |
| TASK-013 to TASK-015 | Cleanup | ⚠️ NEEDS VERIFICATION | Verify each |
| TASK-016 to TASK-026 | Preset Propagation | ✅ 14/14 files have preset_config | Update docs |

### 1.2 Verification Commands

```bash
# Step imports test
pytest tests/pipeline/steps/test_cli_factories_all_steps.py -v

# Collect all tests
pytest tests/ --collect-only 2>&1 | tail -5

# Run core smoke tests
make smokes-cli 2>&1 | tail -20
```

### 1.3 Documentation Updates

- [x] Update CONTEXT.md - remove stale drift note
- [x] Update 01_TASKS.md - mark TASK-001 to TASK-008 complete
- [ ] Update 01_TASKS.md - mark remaining tasks complete after verification
- [ ] Update CHANGELOG.md with verification summary

---

## Phase 2: Skill Integration Testing (Short-term)

### 2.1 Run All Skill Sanity Checks

| Skill | Command | Purpose |
|-------|---------|---------|
| `/extractor` | `./sanity.sh` | Verify extraction across formats |
| `/debug-pdf` | `./sanity.sh` | Verify failure analysis pipeline |
| `/prompt-lab` | `./sanity.sh` | Verify QRA evaluation |
| `/fixture-tricky` | `./sanity.sh` | Verify adversarial PDF generation |
| `/doc2qra` | `./run.sh --help` | Verify doc-to-memory pipeline |

### 2.2 End-to-End Integration Test

```bash
# Test the full extraction → QRA → memory pipeline
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/extractor
./run.sh tests/fixtures/sample.pdf --out /tmp/extract_test

# Verify outputs
ls -la /tmp/extract_test/
cat /tmp/extract_test/04_section_builder/json_output/04_sections.json | jq '.sections | length'
```

### 2.3 Debug-PDF → Extractor Integration

```bash
# Create a test fixture and verify extractor handles it
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/fixture-tricky
uv run generate.py false-tables --output /tmp/false_tables.pdf

# Run extractor on the tricky fixture
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/extractor
./run.sh /tmp/false_tables.pdf --fast --out /tmp/tricky_result
```

---

## Phase 3: Pipeline Hardening (Medium-term)

### 3.1 Add Missing Test Coverage

| Area | Current | Target | Action |
|------|---------|--------|--------|
| Pipeline step imports | 14/14 | 14/14 | ✅ Complete |
| Sanity functions | 21/21 | 21/21 | ✅ Complete |
| Format parity tests | Partial | Full | Add cross-format tests |
| Failure pattern tests | 14/17 | 17/17 | Add network pattern mocks |

### 3.2 Improve Failure Detection

The `/debug-pdf` skill detects 14/17 patterns. Add detection for:
- `auth_required` - Marketing platform cookie gates
- `access_restricted` - Government/defense access controls
- (These require network-level detection in fetcher, not local PDF analysis)

### 3.3 Preset Calibration System

Leverage the calibration system for dynamic preset tuning:
```
src/extractor/pipeline/calibration/
├── calibration_runner.py
├── calibration_ui.py
└── preset_tuner.py
```

---

## Phase 4: Continuous Improvement (Long-term)

### 4.1 Memory-Driven Learning

Use `/memory` skill to learn from extraction patterns:
```bash
# Learn successful extraction patterns
./run.sh paper.pdf --learn --scope extraction_patterns

# Recall patterns for similar documents
memory recall "PDF extraction" --scope extraction_patterns
```

### 4.2 Prompt Engineering Loop

Use `/prompt-lab` to optimize VLM prompts:
```bash
# Test table description prompt
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/prompt-lab
./run.sh eval --prompt table_description_v1 --model deepseek

# Iterate based on results
./run.sh optimize --prompt table_description_v1
```

### 4.3 Automated Regression Testing

Set up nightly regression using `/debug-pdf`:
```bash
# Batch analyze known failure cases
./run.sh batch known_failures.txt --output regression_report.json

# Track pattern distribution over time
```

---

## Quality Gates

### Mandatory Checks Before Merge

1. **Test Collection**: `pytest tests/ --collect-only` collects 500+ tests
2. **Step Imports**: All 14 pipeline steps import without errors
3. **Sanity Functions**: All 21 sanity() functions return 0
4. **Core Smoke**: `make smokes-cli` exits with code 0

### CI/CD Integration

```yaml
# .github/workflows/extractor-ci.yml
jobs:
  test:
    steps:
      - run: pytest tests/pipeline/steps/test_cli_factories_all_steps.py
      - run: pytest tests/ --collect-only
      - run: make smokes-cli
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Test count | 516 | 550+ |
| Pipeline step coverage | 100% | 100% |
| Format parity (vs HTML) | 87% PDF | 90% PDF |
| Failure pattern detection | 82% | 95% |
| Skill sanity pass rate | 100% | 100% |

---

## Execution Order

1. **Phase 1**: Verify remaining tasks (TASK-009 to TASK-026)
2. **Phase 2**: Run skill integration tests
3. **Phase 3**: Add missing test coverage
4. **Phase 4**: Set up continuous improvement loop

---

## Appendix: File Locations

| Component | Path |
|-----------|------|
| Extractor Project | `/home/graham/workspace/experiments/extractor` |
| Pipeline Steps | `src/extractor/pipeline/steps/` |
| Tests | `tests/` |
| Skills | `/home/graham/workspace/experiments/pi-mono/.pi/skills/` |
| Task File | `01_TASKS.md` |
| Context | `CONTEXT.md` |
