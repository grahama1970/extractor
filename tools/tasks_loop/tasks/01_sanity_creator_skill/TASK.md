# Task: Create sanity-creator Skill + Sanity Scripts for pi-mono Skills

---
task_id: 01_sanity_creator_skill
title: "Sanity-Creator Skill & Missing Sanity Scripts"
status: pending
priority: high

acceptance:
  - `sanity-creator` skill exists in pi-mono with working run.sh
  - sanity-creator can generate sanity scripts using brave-search + Context7
  - All high-priority skills have verified sanity scripts
  - orchestrate SKILL.md documents how to invoke sanity-creator

gate: gates/gate_sanity_creator.py
expected:
  sanity_creator_exists: true
  all_high_priority_sanity_pass: true
---

## Goal

Create a `sanity-creator` skill that generates API sanity scripts, then use it to create
missing sanity scripts for pi-mono skills with non-standard dependencies.

## Background

The sanity-first task pattern requires verified sanity scripts for non-standard APIs
BEFORE implementation begins. Currently, agents must manually create these scripts.
A dedicated skill will:

1. Use brave-search (free) to find usage patterns
2. Use Context7 to get library documentation
3. Generate a sanity script from template
4. Verify the script passes

---

## Crucial Dependencies

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| `typer` | CLI framework | N/A (standard) | ✓ standard |
| brave-search skill | `search.py` | N/A (existing skill) | ✓ existing |
| context7 skill | `context7.py` | N/A (existing skill) | ✓ existing |

**Standard libraries (no sanity needed)**: json, pathlib, typing, subprocess

### Research Commands

```bash
# How to use Context7 API
python /home/graham/workspace/experiments/pi-mono/.pi/skills/context7/context7.py search requests "session api"

# How to use brave-search
python /home/graham/workspace/experiments/pi-mono/.pi/skills/brave-search/brave_search.py web "python requests session example"
```

---

## Questions/Blockers

> **BLOCKED** until resolved:

- [x] Should sanity-creator be separate skill or part of orchestrate?
  **RESOLVED**: Separate skill - single responsibility, can be used independently

- [ ] Where should generated sanity scripts be placed?
  **PROPOSAL**: In the skill's own directory as `sanity.sh` or `sanity/` folder

- [ ] Should sanity-creator auto-commit generated scripts?
  **PROPOSAL**: No - human should review and commit

---

## Implementation Plan

### Task 1: Create sanity-creator Skill Structure

Create `/home/graham/workspace/experiments/pi-mono/.pi/skills/sanity-creator/`:

```
sanity-creator/
├── SKILL.md          # Skill documentation
├── run.sh            # Entry point
├── sanity_creator.py # Main logic
├── templates/        # Script templates
│   ├── python_api.py.template
│   └── cli_tool.sh.template
└── sanity.sh         # Self-test
```

### Task 2: Implement Core Logic

```python
# sanity_creator.py
def create_sanity_script(
    library: str,
    api_method: str,
    output_path: Path,
    context7_id: Optional[str] = None,
) -> Dict:
    """
    1. Research library with brave-search
    2. Get docs with Context7 (if library ID known)
    3. Generate sanity script from template
    4. Attempt to run script
    5. Return status + script path
    """
```

### Task 3: Create Missing Sanity Scripts

**HIGH PRIORITY** (have crucial non-standard dependencies):

| Skill | Dependencies | Context7 ID |
|-------|--------------|-------------|
| episodic-archiver | python-arango, embeddings | /ArangoDB/arangodb |
| edge-verifier | python-arango, scillm | /ArangoDB/arangodb |
| youtube-transcripts | youtube-transcript-api, yt-dlp | N/A |
| interview | textual | /textualize/textual |

**MEDIUM PRIORITY** (self-contained but should verify auto-install):

| Skill | Dependencies | Notes |
|-------|--------------|-------|
| treesitter | uvx auto-install | Just verify uvx works |
| fetcher | uv run auto-install | Verify fetch + playwright |
| pdf-fixture | uv run auto-install | Verify PDF generation |

**LOW PRIORITY** (meta/infra skills):

| Skill | Notes |
|-------|-------|
| orchestrate | Meta skill, no external APIs |
| assess | Analysis skill |
| skills-sync | Sync utility |
| runpod-ops | Infra operations |

### Task 4: Update orchestrate SKILL.md

Add section documenting how to invoke sanity-creator during PHASE 1:

```markdown
## Sanity Script Generation

During task collaboration, if non-standard APIs are identified:

\`\`\`bash
# Generate sanity script for a library
.pi/skills/sanity-creator/run.sh create \\
  --library camelot \\
  --method "read_pdf" \\
  --context7-id /camelot-dev/camelot \\
  --output tools/tasks_loop/sanity/camelot.py
\`\`\`
```

---

## Agent Instructions

1. **Task 1-2**: Create the sanity-creator skill infrastructure
2. **Task 3**: Use the skill to generate sanity scripts for HIGH PRIORITY skills
3. **Task 4**: Update orchestrate documentation
4. Run all generated sanity scripts to verify they pass
5. Do NOT auto-commit - leave for human review

## Related Files

- `/home/graham/workspace/experiments/pi-mono/.pi/skills/orchestrate/SKILL.md` - Orchestrate skill
- `/home/graham/workspace/experiments/extractor/tools/tasks_loop/sanity/TEMPLATE.py` - Sanity template
- `/home/graham/workspace/experiments/extractor/tools/tasks_loop/sanity/camelot_table_extraction.py` - Example

## Success Criteria

```bash
# Sanity-creator exists and works
.pi/skills/sanity-creator/sanity.sh  # Should pass

# All high-priority skills have sanity scripts that pass
.pi/skills/episodic-archiver/sanity.sh  # Should pass
.pi/skills/edge-verifier/sanity.sh      # Should pass
.pi/skills/youtube-transcripts/sanity.sh # Should pass
.pi/skills/interview/sanity.sh          # Should pass
```
