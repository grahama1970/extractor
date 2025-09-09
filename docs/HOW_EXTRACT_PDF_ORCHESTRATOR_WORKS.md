# How the Extract-PDF Orchestrator Works

## Overview

The extract-pdf.md agent is an **orchestrator** that coordinates a complex PDF extraction pipeline through worker scripts and sub-agents. It does not execute commands directly - instead, it manages a workflow where different types of tasks are delegated to appropriate execution mechanisms.

## Key Concepts

### 1. Types of Tasks

The orchestrator manages three distinct types of tasks:

#### a) **Python Commands (Direct Execution)**
These are executed directly by the orchestrator using Python worker scripts:
- `extract-pipeline extract-annotations doc.pdf -o annotations.json`
- `marker-pdf clean.pdf --output blocks.json`
- `extract-pipeline build-sections fixed.json -o sections.json`
- `pdf-tools section-image doc.pdf sections.json -o section.png`

These commands run Python scripts that process data and produce output files.

#### b) **Agent Tasks (Sub-Agent Delegation)**
These tasks are marked with `[Agent task: ...]` and involve spawning sub-agents:
- `[Agent task: analyze annotations.json]` - Semantic interpretation
- `[Agent task: use pdf_block_fixer_prompt.md on batches]` - Batch processing
- `[Agent task: use section_enhancer_tasklist.md on batches]` - Enhancement

These tasks require Claude instances to analyze data and make decisions.

#### c) **Knowledge Base Queries**
- `knowledge-architect search "pdf extraction patterns"`
- `knowledge-architect store final.json --type "extraction_result"`

These interact with the ArangoDB knowledge base for pattern learning.

### 2. Execution Model

The orchestrator follows a **checklist-based execution model**:

```
☐ 1. Extract annotations → Python command
☐ 2. Interpret annotations → Agent task
☐ 3. Create clean PDF → Python command
☐ 4. Check knowledge base → Knowledge query
☐ 5. Run marker extraction → Python command
☐ 5.5. If suspicious blocks exist:
   ☐ a. Create batches → Python command
   ☐ b. Spawn sub-agents → Agent task
   ☐ c. Apply ALL fixes → Python command
```

Each checkbox represents a discrete step that can be:
- Executed (Python commands)
- Delegated (Agent tasks)
- Queried (Knowledge base)

## Stage 5.5 and Stage 8: Concurrent Processing

### Stage 5.5: Block Fixing

When suspicious blocks are detected:

1. **Batch Creation** (Python):
   ```python
   worker = PDFBlockFixerWorker()
   batch_result = worker.create_suspicious_batches(marker_output_path)
   # Creates: /tmp/pdf_batches/batch_000.json, batch_001.json, etc.
   ```

2. **Sub-Agent Spawning** (Agent Task):
   - The orchestrator would instruct: "Use pdf_block_fixer_prompt.md on each batch file"
   - This spawns multiple Claude instances, one per batch
   - Each sub-agent analyzes its batch and creates decisions:
     ```json
     {
       "uuid": "abc-123",
       "action": "merge_with_next",
       "new_text": "4.1.5.4. BHT (Branch History Table) submodule"
     }
     ```

3. **Fix Application** (Python):
   ```python
   worker.apply_fixes_with_jq(original_file, all_decisions.json)
   ```

### Stage 8: Section Enhancement

Similar pattern but more complex:

1. **Content-Aware Batch Creation** (Python):
   ```python
   orchestrator = SectionEnhancerOrchestrator()
   orchestrator.create_section_batches(sections.json)
   # Creates batches by content type:
   # - batch_text_20250131_143022.json (20 text sections)
   # - batch_table_20250131_143023.json (5 table sections)
   # - batch_math_20250131_143024.json (10 math sections)
   ```

2. **Concurrent Sub-Agent Processing** (Agent Task):
   - Different prompts for different content types:
     - `section_enhancer_text_only.md` for text batches
     - `section_enhancer_concise.md` for table batches
     - `section_enhancer_math_focused.md` for math batches
   - Each sub-agent has access to ALL worker tools but focuses on relevant ones
   - Example: A table-focused agent would prioritize camelot, pandas_analyzer, table_merger

3. **Enhancement Application** (Python):
   ```python
   orchestrator.apply_enhancements_with_jq(original_sections.json)
   ```

## How "Spawning Sub-Agents" Works

When the orchestrator encounters an agent task like "spawn sub-agents", it means:

1. **Batch Files Are Created**: Python workers create JSON files with work units
2. **Prompts Guide Processing**: Specialized markdown prompts (like pdf_block_fixer_prompt.md) tell sub-agents what to do
3. **Parallel Execution**: Multiple Claude instances can process batches concurrently
4. **Results Aggregation**: Python workers collect all decisions and apply them atomically

Example flow for 50 suspicious blocks:
```
50 blocks → 5 batches → 5 Claude sub-agents (concurrent) → 5 decision files → 1 merged fix
```

## Key Insights

### 1. **Orchestration vs Execution**
The orchestrator manages the workflow but doesn't execute tasks directly. It's like a project manager delegating to specialists.

### 2. **Python for Deterministic Tasks**
Tasks with clear algorithms (file I/O, data transformation, jq operations) are handled by Python workers.

### 3. **Claude for Judgment Tasks**
Tasks requiring interpretation, pattern recognition, or decision-making are delegated to Claude sub-agents.

### 4. **Batch Processing for Scale**
Large tasks are split into batches to enable:
- Parallel processing
- Token limit management
- Failure isolation

### 5. **Prompts as Task Specifications**
Markdown prompts like `pdf_block_fixer_prompt.md` serve as detailed task specifications for sub-agents, including:
- What to analyze
- How to make decisions
- Output format requirements

### 6. **UUID-Based Coordination**
Every block and section gets a UUID, enabling:
- Precise tracking across transformations
- Safe concurrent modifications
- Atomic updates via jq

## Example: Complete Flow for a PDF with Issues

1. **Extract annotations** → 14 annotations found
2. **Interpret annotations** → Claude analyzes: "merge_table", "section_header" markings
3. **Create clean PDF** → Remove annotation overlays
4. **Check knowledge** → Find similar PDFs processed successfully
5. **Run marker** → Extract 500 blocks, 50 marked suspicious
6. **Stage 5.5**:
   - Create 5 batches of ~10 suspicious blocks each
   - Spawn 5 Claude sub-agents with pdf_block_fixer_prompt.md
   - Each analyzes and creates decisions
   - Apply all decisions with jq → 450 clean blocks
7. **Build sections** → Organize into 30 hierarchical sections
8. **Create validation images** → Visual proof of structure
9. **Stage 8**:
   - Categorize sections: 20 text, 5 tables, 3 math, 2 mixed
   - Create 4 content-specific batches
   - Spawn 4 Claude sub-agents with specialized prompts
   - Each enhances its section type (clean text, fix tables, convert LaTeX)
   - Apply all enhancements → 30 enhanced sections
10. **Validate** → Compare against gold standard
11. **Add breadcrumbs** → Navigation paths like "1.2.3 > Subsystem > Details"
12. **Store patterns** → Save successful strategies for future use

## The Power of This Architecture

1. **Scalability**: Can process hundreds of sections/blocks in parallel
2. **Specialization**: Different agents for different content types
3. **Learning**: Every successful run improves future extractions
4. **Atomicity**: All-or-nothing updates prevent partial corruptions
5. **Transparency**: Every decision is tracked and can be audited

The orchestrator pattern allows complex multi-step pipelines to be managed declaratively while maintaining clear separation between coordination (orchestrator), execution (workers), and judgment (sub-agents).