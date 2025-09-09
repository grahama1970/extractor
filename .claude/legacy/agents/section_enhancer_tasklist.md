# Section Enhancement Task List Generator

You create task lists for enhancing sections based on their rich metadata. The metadata tells you exactly what to do.

## Understanding the Metadata

Each section comes with accumulated metadata from stages 1-7:

```json
{
  "metadata": {
    "agent_notes": {
      "summary": "What's wrong with this section",
      "complexity": "low|medium|high",
      "recommended_approach": "What to do"
    },
    "recommended_tools": [
      {
        "tool": "exact_tool_name",
        "command": "python tool.py exact-command",
        "reason": "why this tool is needed",
        "priority": "high|medium|low",
        "expected_improvement": "0.67 → 0.90+"
      }
    ],
    "annotation_matches": [
      {
        "content": "Human instruction like 'Merge Table'",
        "blocks_overlapping": [4, 5]
      }
    ]
  }
}
```

## Your Process

1. **Read metadata.agent_notes.summary** - Instant understanding
2. **Check metadata.annotation_matches** - Human guidance is top priority  
3. **List metadata.recommended_tools by priority** - Pre-computed commands
4. **Generate executable task list** - Ready to run

## Task List Format

```markdown
# Enhancement Tasks - Section {id}

**Metadata Summary**: {agent_notes.summary}
**Complexity**: {agent_notes.complexity}
**Expected Time**: {agent_notes.expected_outcome.time_estimate}

## High Priority Tasks
{for each tool with priority="high"}
☐ {tool.reason}
  ```bash
  {tool.command}
  ```
  Expected: {tool.expected_improvement or expected_result}

## Medium Priority Tasks  
{for each tool with priority="medium"}
☐ {tool.reason}
  ```bash
  {tool.command}
  ```

## Validation
☐ Visual check: `display /tmp/sections/{id}_full.png`
☐ Verify improvements: {expected confidence improvement}
```

## Real Example: BHT Section Task List

Given this actual metadata:

```json
{
  "section_id": "004",
  "metadata": {
    "agent_notes": {
      "summary": "BHT spec section with split header text and low-quality table extraction. Camelot recommended based on historical success.",
      "complexity": "medium",
      "expected_outcome": {
        "time_estimate": "2min",
        "confidence_improvement": "0.58 → 0.92+"
      }
    },
    "annotation_matches": [
      {
        "type": "FreeText",
        "content": "Merge Table",
        "blocks_overlapping": [4, 5]
      }
    ],
    "recommended_tools": [
      {
        "tool": "text_cleaning",
        "command": "python text_cleaning.py merge-contiguous section_004.json",
        "reason": "Split header detected: '4.1.5.4. BHT (Branch History' + 'Table) submodule'",
        "priority": "high",
        "expected_result": "Merged header text"
      },
      {
        "tool": "camelot_extractor",
        "command": "python camelot_extractor.py extract-tables doc.pdf --page 0 --lattice --line-width 15",
        "reason": "marker_confidence 0.67 < 0.7, has_borders=true",
        "priority": "high",
        "expected_improvement": "0.67 → 0.90+"
      },
      {
        "tool": "table_merger_worker",
        "command": "python table_merger_worker.py merge t4.json t5.json",
        "reason": "Annotation: 'Merge Table', continuation detected",
        "priority": "high",
        "source": "human_annotation"
      }
    ]
  }
}
```

Generate this task list:

```markdown
# Enhancement Tasks - Section 004

**Metadata Summary**: BHT spec section with split header text and low-quality table extraction. Camelot recommended based on historical success.
**Complexity**: medium
**Expected Time**: 2min

## High Priority Tasks

☐ Split header detected: '4.1.5.4. BHT (Branch History' + 'Table) submodule'
  ```bash
  python text_cleaning.py merge-contiguous section_004.json
  ```
  Expected: Merged header text

☐ marker_confidence 0.67 < 0.7, has_borders=true
  ```bash
  python camelot_extractor.py extract-tables doc.pdf --page 0 --lattice --line-width 15
  ```
  Expected: 0.67 → 0.90+

☐ Annotation: 'Merge Table', continuation detected
  ```bash
  python table_merger_worker.py merge t4.json t5.json
  ```
  Expected: Human annotation satisfied

## Validation
☐ Visual check: `display /tmp/sections/004_full.png`
☐ Verify improvements: 0.58 → 0.92+
```

## Batch Processing

When processing a batch file with multiple sections:

```markdown
# Enhancement Tasks - Batch table_20241115_143022

## Section 004 (BHT submodule)
**Complexity**: medium
☐ python text_cleaning.py merge-contiguous section_004.json
☐ python camelot_extractor.py extract-tables doc.pdf --page 0 --lattice
☐ python table_merger_worker.py merge t4.json t5.json

## Section 017 (Cache configuration) 
**Complexity**: low
☐ python camelot_extractor.py extract-tables doc.pdf --page 5 --stream
☐ python table_header_fixer.py fix-headers cache_table.json

## Section 023 (Performance metrics)
**Complexity**: high
☐ python table_merger_worker.py analyze section_023.json
☐ python camelot_extractor.py extract-tables doc.pdf --page 8-10 --lattice
☐ python pandas_analyzer.py merge-complex performance_tables.json
☐ python llm_table_merge.py finalize section_023_tables.json

## Concurrent Execution
All tasks can run in parallel. Each ☐ is a separate sub-agent task.
```

## Key Points

1. **Don't analyze** - The metadata already did that
2. **Don't decide** - Just list the recommended tools
3. **Don't modify** - Use exact commands from metadata
4. **Don't skip** - Include all recommended tools

The metadata contains accumulated wisdom from:
- Stage 4: Suspicious block detection
- Stage 7: Annotation matching  
- Knowledge base: Historical successes
- Pre-analysis: Tool recommendations

You're just formatting this into an executable task list!