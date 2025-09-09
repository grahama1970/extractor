# Stage 8: One Section = One Sub-Agent Instance

## The Correct Understanding

Each section JSON gets its own Claude Code instance! This is maximum parallelism.

## Step 1: Create Individual Section Files

```bash
$ python section_enhancer_orchestrator.py create-sections sections.json

Creating individual section files...
Created 50 section files:
- /tmp/sections/section_001.json
- /tmp/sections/section_002.json
- /tmp/sections/section_003.json
- /tmp/sections/section_004.json
- /tmp/sections/section_005.json
...
- /tmp/sections/section_050.json
```

## Step 2: Spawn 50 Sub-Agents (10 at a time)

### First Batch of 10
```markdown
## Spawning Section Enhancement Sub-Agents (Batch 1/5)

Spawning 10 concurrent sub-agents:

Use the section-enhancer sub-agent to process /tmp/sections/section_001.json
Use the section-enhancer sub-agent to process /tmp/sections/section_002.json
Use the section-enhancer sub-agent to process /tmp/sections/section_003.json
Use the section-enhancer sub-agent to process /tmp/sections/section_004.json
Use the section-enhancer sub-agent to process /tmp/sections/section_005.json
Use the section-enhancer sub-agent to process /tmp/sections/section_006.json
Use the section-enhancer sub-agent to process /tmp/sections/section_007.json
Use the section-enhancer sub-agent to process /tmp/sections/section_008.json
Use the section-enhancer sub-agent to process /tmp/sections/section_009.json
Use the section-enhancer sub-agent to process /tmp/sections/section_010.json

Waiting for batch 1 to complete...
```

### After Batch 1 Completes, Next 10
```markdown
## Spawning Section Enhancement Sub-Agents (Batch 2/5)

Spawning next 10 concurrent sub-agents:

Use the section-enhancer sub-agent to process /tmp/sections/section_011.json
Use the section-enhancer sub-agent to process /tmp/sections/section_012.json
...
Use the section-enhancer sub-agent to process /tmp/sections/section_020.json
```

## What Each Sub-Agent Does

Each section-enhancer sub-agent processes ONE section:

```json
// section_004.json - Input to one sub-agent
{
  "section_id": "004",
  "blocks": [...],
  "metadata": {
    "recommended_tools": [
      {
        "tool": "text_cleaning",
        "command": "python text_cleaning.py merge-contiguous section_004.json",
        "reason": "Split header detected"
      },
      {
        "tool": "camelot_extractor",
        "command": "python camelot_extractor.py extract-tables doc.pdf --page 42",
        "reason": "Low table confidence"
      }
    ]
  }
}
```

The sub-agent:
1. Reads its ONE section
2. Executes the recommended tools
3. Writes enhanced result
4. Exits

## The Complete Architecture

```
Main Agent (PDF Orchestrator)
    │
    ├── Create 50 individual section JSONs
    │
    ├── Batch 1: Spawn 10 Claude instances
    │   ├── Sub-Agent 1 → section_001.json → section_001_enhanced.json
    │   ├── Sub-Agent 2 → section_002.json → section_002_enhanced.json
    │   └── ... (8 more)
    │
    ├── Batch 2: Spawn 10 Claude instances
    │   ├── Sub-Agent 11 → section_011.json → section_011_enhanced.json
    │   └── ... (9 more)
    │
    └── Continue until all 50 sections processed
```

## Why One Section Per Sub-Agent?

1. **Maximum Parallelism**: Each section processed independently
2. **Isolation**: One section failure doesn't affect others
3. **Simple Sub-Agents**: Each only needs to understand one section
4. **Clear Output**: One input file → one output file
5. **Resource Management**: Spawn 10 at a time to avoid overwhelming system

## The Sub-Agent is Very Simple

```markdown
---
name: section-enhancer
description: "Enhances a single PDF section based on metadata recommendations"
tools: Read, Write, Bash
---

# Section Enhancement Sub-Agent

I enhance ONE section based on its metadata.

1. Read the section JSON
2. Execute each recommended tool in metadata.recommended_tools
3. Write the enhanced section
4. Done!
```

## Example: 200-Page Document

- 200 sections = 200 individual JSON files
- Spawn in batches of 10
- 20 batches total
- Each batch takes ~30 seconds
- Total time: ~10 minutes (vs hours sequentially)

## Key Insight

This is the most granular parallelism possible:
- **One section = One Claude instance**
- **No shared context between sections**
- **Pure parallel processing**
- **Managed in batches of 10** to control resource usage

This explains why metadata enrichment is so critical - each sub-agent gets everything it needs in its single section JSON!