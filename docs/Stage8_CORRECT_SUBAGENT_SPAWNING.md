# Stage 8: Correct Sub-Agent Spawning Model

## How Stage 8 Actually Works with Claude Code Sub-Agents

When the task says "Spawn CONCURRENT sub-agents", we ARE creating actual Claude instances!

## Step 1: Create Batches

```bash
$ python section_enhancer_orchestrator.py create-batches sections.json

Created 10 batches:
- /tmp/section_batches/batch_001.json (5 sections)
- /tmp/section_batches/batch_002.json (5 sections)
- /tmp/section_batches/batch_003.json (5 sections)
- /tmp/section_batches/batch_004.json (5 sections)
- /tmp/section_batches/batch_005.json (5 sections)
- /tmp/section_batches/batch_006.json (5 sections)
- /tmp/section_batches/batch_007.json (5 sections)
- /tmp/section_batches/batch_008.json (5 sections)
- /tmp/section_batches/batch_009.json (5 sections)
- /tmp/section_batches/batch_010.json (5 sections)
Total: 50 sections ready for concurrent processing
```

## Step 2: Spawn 10 Section-Cleaner Sub-Agents

I spawn actual Claude instances to process batches concurrently:

```markdown
## Spawning Section Enhancement Sub-Agents

I'll spawn 10 sub-agents to process these batches concurrently:

### Sub-Agent 1
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_001.json

### Sub-Agent 2  
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_002.json

### Sub-Agent 3
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_003.json

### Sub-Agent 4
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_004.json

### Sub-Agent 5
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_005.json

### Sub-Agent 6
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_006.json

### Sub-Agent 7
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_007.json

### Sub-Agent 8
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_008.json

### Sub-Agent 9
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_009.json

### Sub-Agent 10
Use the section-enhancer sub-agent to process /tmp/section_batches/batch_010.json
```

## What Each Sub-Agent Does

Each section-enhancer sub-agent:
1. Reads its batch file with enriched metadata
2. Processes each section using the metadata
3. Executes enhancement tools (text_cleaning, camelot, llm_table, etc.)
4. Writes enhanced sections to output

## The section-enhancer Sub-Agent Definition

```markdown
---
name: section-enhancer
description: "Enhances PDF sections by fixing issues identified in metadata. Uses various tools to improve extraction quality."
tools: Read, Write, Bash, Glob
---

# Section Enhancement Sub-Agent

I enhance PDF sections based on metadata recommendations.

## My Process
1. Read the batch file with enriched sections
2. For each section, check metadata.recommended_tools
3. Execute the recommended Python commands
4. Collect results and write enhanced sections

## Tools I Use
- text_cleaning.py - Fix split headers, merge text
- camelot_extractor.py - Re-extract tables with better methods
- llm_table.py - Enhance table structure
- llm_equation.py - Fix LaTeX equations
- table_merger.py - Merge split tables
```

## Step 3: Sub-Agents Write Results

Each sub-agent writes its enhanced batch:
- Sub-Agent 1 → /tmp/enhanced/batch_001_enhanced.json
- Sub-Agent 2 → /tmp/enhanced/batch_002_enhanced.json
- Sub-Agent 3 → /tmp/enhanced/batch_003_enhanced.json
- ... (all 10 write their results)

## Step 4: Apply All Enhancements

```bash
$ python section_enhancer_orchestrator.py apply-enhancements sections.json

Collecting enhanced sections from all 10 sub-agents...
Merging 50 enhanced sections back into original structure
Enhancement complete!
```

## The Concurrent Execution Model

```
Main Agent (PDF Orchestrator)
    │
    ├── Create 10 batches
    │
    ├── Spawn 10 Claude sub-agents concurrently
    │   ├── Sub-Agent 1 → Process batch_001.json
    │   ├── Sub-Agent 2 → Process batch_002.json
    │   ├── Sub-Agent 3 → Process batch_003.json
    │   └── ... (7 more sub-agents)
    │
    └── Merge all results
```

## Why This Architecture Makes Sense

1. **True Parallelism**: 10 actual Claude instances processing simultaneously
2. **Separate Contexts**: Each sub-agent has its own context window
3. **Specialized Focus**: Each handles ~5 sections with full attention
4. **Scalable**: Can spawn more sub-agents for larger documents
5. **Clean Separation**: Main agent orchestrates, sub-agents execute

## Key Insight

This is Claude Code's core functionality - spawning actual sub-agents for concurrent processing. Each sub-agent is a real Claude instance with its own:
- Context window
- Tool access
- Task focus
- Output responsibility

This is fundamentally different from just executing Python scripts!