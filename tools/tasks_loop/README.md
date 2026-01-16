# tasks_loop - Preset-First PDF Extraction

> **Every engineering/scientific PDF needs a calibrated Preset.**
> There is NO one-size-fits-all PDF extraction solution.
> Neither human nor agent alone can figure it out - collaboration is required.

## Core Principle: Protected Context

**Every task, bug, or preset gets its own isolated context window.**

This means:

- Fresh start for each issue
- No pollution from previous attempts
- Focused iteration until gate passes
- Artifacts recorded per attempt

## Terminology

| Term        | Definition                                        | Who Uses It         |
| :---------- | :------------------------------------------------ | :------------------ |
| **Preset**  | Extraction configuration for a document type      | Everyone            |
| **Task**    | New feature or enhancement to implement           | Developers          |
| **Bug**     | Issue to fix with reproduction steps              | Developers          |
| **Fixture** | Test case with synthetic PDF and expected outputs | Pipeline developers |
| **Gate**    | Validation script that checks outputs             | CI/Automation       |

## Directory Structure

```
tools/tasks_loop/
├── README.md                 # This file
├── loop.sh                   # Retry loop for ANY gate
│
├── tasks/                    # Feature work
│   ├── TEMPLATE.md           # Copy for new tasks
│   └── {task_id}/
│       ├── TASK.md           # Goal, acceptance criteria
│       └── artifacts/        # Attempts, logs
│
├── bugs/                     # Bug fixes
│   ├── TEMPLATE.md           # Copy for new bugs
│   └── {bug_id}/
│       ├── BUG.md            # Reproduction, expected vs actual
│       └── artifacts/        # Attempts, logs
│
├── fixtures/                 # Preset test cases
│   ├── preset_registry.yml   # Maps presets to fixtures
│   ├── schema.yml            # Validates SPEC.md files
│   └── {preset_name}/
│       ├── SPEC.md           # Preset specification
│       ├── source.pdf        # Synthetic test PDF
│       └── contracts/        # Compiled from SPEC.md
│
├── gates/                    # Validation scripts
│   ├── gate_s00.py           # Step 00 validation
│   ├── gate_s01.py           # Step 01 validation
│   └── ...
│
└── utils/
    ├── compile_contracts.py  # SPEC.md → contracts
    └── create_fixture_pdf.py # Generate synthetic PDF
```

## The Three Workflows

### 1. Preset Calibration (PDF Extraction)

```bash
# Auto-detect preset and extract
python3 .agents/skills/extractor/cli.py extract paper.pdf

# Force specific preset
python3 .agents/skills/extractor/cli.py extract paper.pdf --preset arxiv

# Force extraction mode
python3 .agents/skills/extractor/cli.py extract paper.pdf --mode accurate
```

### 2. Task Implementation (New Features)

```bash
# 1. Create task
cp tasks/TEMPLATE.md tasks/add_formula_detection/TASK.md
# Edit TASK.md with goal and acceptance criteria

# 2. Create gate (or use existing)
# gates/gate_formula_detection.py

# 3. Run loop until gate passes
./loop.sh --verify gates/gate_formula_detection.py --agent claude
```

### 3. Bug Fixing

```bash
# 1. Create bug report
cp bugs/TEMPLATE.md bugs/s02_silent_failure/BUG.md
# Edit BUG.md with reproduction steps

# 2. Create gate that verifies fix
# gates/gate_s02_error_handling.py

# 3. Run loop until gate passes
./loop.sh --verify gates/gate_s02_error_handling.py --agent claude
```

## How loop.sh Works

```
┌─────────────────────────────────────────────────────────┐
│  1. RUN GATE: ./verify_script.sh                        │
│  2. IF PASS: Done (self-review optional)                │
│  3. IF FAIL: Feed failure tail to agent                 │
│  4. AGENT: Makes focused fix                            │
│  5. REPEAT: Until pass or max retries                   │
│  6. ARTIFACTS: Each attempt logged in artifacts/        │
└─────────────────────────────────────────────────────────┘
```

**Key Features:**

- `--retries N` - Max retry attempts (default: 3)
- `--agent NAME` - Which agent to use (claude, codex, gemini)
- `--no-self-review` - Skip self-review before completion
- Artifacts saved per attempt for debugging

## Gate Exit Codes

| Code | Meaning                     | Action           |
| ---- | --------------------------- | ---------------- |
| 0    | PASS                        | Done             |
| 1    | FAIL                        | Retry with agent |
| 42   | CLARIFY (needs human input) | Stop and ask     |

## Creating a New Preset

When Step 00 can't match a PDF to an existing preset:

1. **Create Fixture**: `mkdir fixtures/my_preset`
2. **Add SPEC.md**: Define expected outputs for each step
3. **Add source.pdf**: Synthetic PDF with known content
4. **Compile contracts**: `python utils/compile_contracts.py --fixture my_preset`
5. **Run gates**: `python gates/gate_s00.py --fixture my_preset`
6. **Update PRESET_REGISTRY**: Add detection rules in `src/extractor/core/presets.py`

## SPEC.md Format

```yaml
---
fixture: arxiv_archetype
pdf: tools/tasks_loop/fixtures/arxiv_archetype/source.pdf

profile:
  domain: scientific
  layout: double
  elements:
    formulas: true

steps:
  s00:
    name: "Profile Detector"
    expected:
      domain: scientific
      route: accurate
  s04:
    name: "Section Builder"
    expected:
      section_count: 5
---
# Human notes about this preset
```

## Best Practices

### For Tasks

- One task per context window
- Clear acceptance criteria in TASK.md
- Gate must be automated (no manual verification)
- Keep changes minimal and focused

### For Bugs

- Include reproduction steps
- Specify expected vs actual behavior
- Gate verifies the fix, not just "no crash"
- Don't fix unrelated issues in same context

### For Presets

- Synthetic PDF should test edge cases
- SPEC.md is single source of truth
- Compile contracts after any SPEC.md change
- Run gates before pushing changes
