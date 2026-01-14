# Extractor Skill

**Mission**: Make Digital Twin creation seamless, collaborative, and fast for human-agent pairs.

## Core Philosophy

> Every engineering/scientific PDF needs a Digital Synthetic Twin.
> There is NO one-size-fits-all PDF extraction solution.
> Neither human nor agent alone can figure it out - collaboration is required.

The extractor is **NOT** a magic black-box. It is a calibration tool where:

1. **Human** provides domain knowledge (what requirements look like, what tables matter).
2. **Agent** provides technical execution (regex tuning, chaos injection, verification automation).
3. **Twin** bridges the gap - a synthetic PDF with known ground truth that calibrates the pipeline.

## Workflow

```
Human: "I need to extract requirements from this 80-page spec."
Agent: "I'll create a Twin first. Let me analyze the PDF style..."
Agent: [Creates 5-page synthetic PDF with similar structure + known content]
Agent: [Runs pipeline on Twin, compares to Ground Truth]
Agent: "Found issues: ligatures breaking REQ-IDs. Tuning config..."
Agent: [Iterates until Twin extraction is clean]
Agent: "Twin passes. Ready for real data."
Human: "Proceed."
```

## Interface

### `extractor verify <fixture>`

Runs the calibration loop on an existing fixture.

- `--auto-tune`: Automatically propose/apply config fixes on failure.

### `extractor extract <pdf>`

Runs extraction on a real PDF.

- `--strict` (default): Requires a valid Twin. If missing, prompts user.
- `--fast`: Skips Twin check (risky, for exploration only).

### `extractor twin <pdf> --pages N --errors [list]`

**(TODO)** Creates a new Twin fixture based on the target PDF's style.

- `--pages N`: Number of pages to generate.
- `--errors`: Chaos to inject (ligatures, hyphenation, split_tables, etc.).

## File Structure

```
.agent/skills/extractor/
├── SKILL.md      # This file
├── cli.py        # Typer CLI entry point
└── logic.py      # Core orchestration logic
```

## Dependencies

- `tools/tasks_loop/fixtures/schema.yml` (Global Fixture Spec)
- `tools/tasks_loop/fixtures/twin_registry.yml` (Twin Catalog)
- `tools/tasks_loop/auto_tune.py` (Repair Loop)
