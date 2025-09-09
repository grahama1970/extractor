# Section Enhancement - Concise Metadata-Driven Approach

You enhance sections using the pre-computed metadata. Everything you need is already analyzed.

## Quick Process

1. **Read agent notes** - Understand the situation
2. **Check recommendations** - See what tools are suggested
3. **Review visual assets** - Verify with your own eyes
4. **Execute minimal tools** - Apply only what's needed
5. **Document decision** - Explain what you did and why

## Input Format

Each section includes:
```json
{
  "metadata": {
    "agent_notes": {          // Pre-computed guidance
      "summary": "...",       // What's wrong
      "recommended_approach": {}, // What to do
      "gotchas": []          // What to watch for
    },
    "recommended_tools": [],  // Specific commands ready to run
    "visual_assets": {},      // Images already generated
    "knowledge_base": {}      // Historical successes
  }
}
```

## Decision Flow

```python
# 1. Quick assessment (5 seconds)
if metadata.agent_notes.complexity == "low" and metadata.recommended_tools[0].confidence > 0.85:
    # Trust the recommendation
    execute(metadata.recommended_tools[0].command)
    return enhanced_section

# 2. Visual check (10 seconds)  
elif metadata.agent_notes.complexity == "medium":
    # Look at the images
    view(metadata.visual_assets.table_images[0])
    
    if visual_confirms_issue:
        execute(metadata.recommended_tools[0].command)
    else:
        skip_with_reason("Visual shows acceptable quality")

# 3. Complex case (30 seconds)
else:
    # Review everything and make decision
    consider_all_recommendations()
    check_historical_patterns()
    apply_best_approach()
```

## Example Enhancement

### Input
```json
{
  "section_id": "004",
  "metadata": {
    "agent_notes": {
      "summary": "BHT spec table with split headers. Camelot will fix.",
      "complexity": "low",
      "expected_outcome": "0.65 → 0.91 confidence"
    },
    "recommended_tools": [{
      "command": "python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice",
      "confidence": 0.89
    }]
  }
}
```

### Your Process (15 seconds total)
1. Read notes: "Split headers, Camelot recommended"
2. Check confidence: 0.89 - high
3. Execute: `python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice`
4. Verify: Table extracted cleanly
5. Done

### Output
```json
{
  "actions_taken": [{
    "tool": "camelot_extractor",
    "reason": "Accepted high-confidence recommendation for split headers",
    "result": "success",
    "confidence": "0.65 → 0.91"
  }],
  "time_spent": "14 seconds",
  "enhanced_section": {...}
}
```

## When to Override Recommendations

Only override if:
1. **Visual shows different issue** than metadata indicates
2. **Annotation conflicts** with recommendation  
3. **Previous attempt failed** (check metadata.previous_attempts)

## Available Tools

If you need tools beyond recommendations, see `section_enhancer_cli_complete.md`.
Most sections need only the recommended tools.

## Key Points

- **Trust the metadata** - It's based on successful patterns
- **Be concise** - Most sections take <30 seconds
- **Document briefly** - One line explaining your decision
- **Quality over speed** - Better to skip uncertain enhancements

The metadata does the heavy lifting. You just make the final decision and execute.