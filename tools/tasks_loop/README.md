# tasks_loop - Twin-First PDF Extraction

> **Every engineering/scientific PDF needs a Digital Synthetic Twin.**
> There is NO one-size-fits-all PDF extraction solution.
> Neither human nor agent alone can figure it out - collaboration is required.

## Core Philosophy

The extractor is **NOT** a magic black-box. It is a calibration system where:

| Actor     | Contribution                                                              |
| --------- | ------------------------------------------------------------------------- |
| **Human** | Domain knowledge (what requirements look like, what tables matter)        |
| **Agent** | Technical execution (regex tuning, chaos injection, verification)         |
| **Twin**  | Bridge between intent and reality - synthetic PDF with known ground truth |

**Without a Twin, extraction will fail.** The Twin calibrates the pipeline before real data is processed.

## Quick Start

```bash
# 1. Create a Twin fixture
mkdir fixtures/my_project
# Create SPEC.md with your expectations

# 2. Compile contracts
python utils/compile_contracts.py --fixture my_project

# 3. Verify Twin
python3 .agent/skills/extractor/cli.py verify my_project

# 4. Extract real PDF (only after Twin passes)
python3 .agent/skills/extractor/cli.py extract /path/to/real.pdf --strict
```

## SPEC.md Format (Single Source of Truth)

All contracts and configs are compiled from `SPEC.md`. This is the **one point of collaboration**.

```yaml
---
fixture: synthesis_messy_BHT
pdf: tools/tasks_loop/fixtures/synthesis_messy_BHT/source.pdf

# Agent behavior
agent_config:
  allow_auto_tune: true
  strict_calibration: true
  category: engineering_spec

# Extraction config (compiled to runtime profile)
config:
  requirement_patterns:
    id_prefixes: ["REQ-", "SYS-"]
    tables_are_requirements: false

# Step contracts
steps:
  s08:
    name: Requirements (LLM)
    expected:
      requirement_count: 2
---
# Human notes here
```

## Chaos Catalog (Common PDF Extraction Errors)

Twins should inject these errors to stress-test extraction:

| Error             | Description                                 | Default |
| ----------------- | ------------------------------------------- | ------- | --- |
| `hyphenation`     | Words split across lines (`require-\nment`) | ✅      |
| `ligatures`       | Unicode substitution (`fi` → `ﬁ`)           | ✅      |
| `split_tables`    | Tables spanning multiple pages              | ✅      |
| `trapped_headers` | Data rows mimicking section headers         | ✅      |
| `mojibake`        | Encoding corruption (`é` → `Ã©`)            | ❌      |
| `ocr_artifacts`   | Character confusion (`                      | `→`I`)  | ❌  |
| `invisible_text`  | Zero opacity or clipped regions             | ❌      |
| `nested_columns`  | Multi-column layouts                        | ❌      |

## Directory Structure

```
tools/tasks_loop/
├── README.md
├── auto_tune.py              # Repair loop (proposes fixes)
│
├── fixtures/
│   ├── schema.yml            # Global Fixture Spec (validates all SPEC.md)
│   ├── twin_registry.yml     # Maps categories to Twin fixtures
│   └── {fixture_name}/
│       ├── SPEC.md           # Single Source of Truth
│       ├── source.pdf        # Synthetic Twin PDF
│       ├── source_expected.json  # Ground Truth
│       └── contracts/        # Compiled from SPEC.md
│
├── gates/                    # Per-step validation gates
├── sanity/                   # Environment sanity checks
└── utils/
    ├── compile_contracts.py  # SPEC.md → contracts + config
    ├── create_fixture_pdf.py # Rich PDF builder
    └── generate_complex_fixture.py  # Quick messy fixture
```

## Twin-Driven Calibration Cycle

```
┌─────────────────────────────────────────────────────────┐
│  1. ANALYZE: Human describes PDF complexity             │
│  2. GENERATE: Agent creates Twin with chaos injection   │
│  3. EXTRACT: Pipeline runs on Twin                      │
│  4. COMPARE: Actual vs Expected (Ground Truth)          │
│  5. TUNE: Agent proposes config changes                 │
│  6. REPEAT: Loop until Twin passes                      │
│  7. APPLY: Run calibrated pipeline on Real PDF          │
└─────────────────────────────────────────────────────────┘
```

## Gate Exit Codes

| Code | Meaning                     |
| ---- | --------------------------- |
| 0    | PASS                        |
| 1    | FAIL                        |
| 42   | CLARIFY (needs human input) |

## Agent Skill Interface

```bash
# Verify a Twin fixture
python3 .agent/skills/extractor/cli.py verify <fixture> [--auto-tune]

# Extract real PDF (Twin required)
python3 .agent/skills/extractor/cli.py extract <pdf> [--strict|--fast]
```
