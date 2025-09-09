# PDF Extraction Task List Orchestration - Code Review Summary

**Review Date:** July 28, 2025  
**Reviewer:** Moonshot Kimi-K2 Model via Code Reviewer Sub-Agent

## Executive Summary

The code review reveals **CRITICAL VIOLATIONS** of the fundamental principle that "AFTER MARKER EXTRACTION, ALL DECISIONS MUST BE MADE BY SUB-AGENT PROMPTS, NOT CODE LOGIC." The implementation contains regex patterns, heuristics, and conditional logic that directly contradict the task list orchestration approach.

## Critical Findings

### 1. ❌ Suspicious Detector Using Patterns Instead of Prompts

**File:** `src/extractor/core/subagents/suspicious_detector.py`

**Violations Found:**
```python
# VIOLATION: Using regex patterns for decision making
HEADER_PATTERNS = {
    "ends_with_comma": (r',$', 0.9),
    "starts_with_as_for": (r'^(As|For|And|But|Or)\s', 0.8),
    "all_lowercase": (r'^[a-z\s]+$', 0.7),
    "very_short": (lambda text: len(text.strip()) < 3, 0.85),
}
```

**Impact:** This is exactly the anti-pattern warned against. The system is using hardcoded regex patterns to identify suspicious blocks instead of delegating to the `pdf-suspicious-detector` sub-agent for semantic analysis.

### 2. ❌ Not Achieving 80%+ Suspicious Detection Rate

**Current Behavior:** The suspicious detector only marks blocks that match specific patterns (e.g., headers ending with commas, starting with "As/For/And").

**Required Behavior:** Should mark 80%+ of ALL blocks as suspicious for sub-agent validation.

**Impact:** Most blocks are passing through without validation, defeating the purpose of semantic understanding.

### 3. ❌ Code-Based Decision Making

**Violations Found:**
- Conditional logic determining block types based on patterns
- If/else statements making extraction decisions
- Hardcoded rules like `len(text) < 3` determining suspicion

**Required:** All decisions should be made by sub-agent prompts, not code logic.

## What's Working Correctly

### ✅ Task List Definition
The `pdf_extraction_tasklist.py` correctly defines the 14-step static task list with proper prompts:
```python
{
    "agent": "pdf-suspicious-detector",
    "prompt": "Use your pdf-suspicious-detector sub-agent to analyze {{raw_blocks}} and identify ALL blocks that need validation (expect 80%+ to need help)",
}
```

### ✅ Task Orchestration Structure
The `tasklist_orchestrator.py` has the correct structure for executing prompts sequentially.

## Required Fixes

### Fix 1: Replace Pattern-Based Suspicious Detection

**Before (Current - WRONG):**
```python
if re.search(r'^(As|For|And|But|Or)\s', text):
    mark_suspicious(block)
```

**After (Required - CORRECT):**
```python
prompt = f"""
Analyze this block and determine if it needs validation:
- Block type: {block_type}
- Text: {text}
- Context: {context}

Mark as suspicious if there's ANY uncertainty about structure, type, or content.
We expect 80%+ of blocks to need validation.
"""
result = await call_subagent("pdf-suspicious-detector", prompt)
```

### Fix 2: Implement 80%+ Suspicious Rate

Instead of selective pattern matching, the system should:
1. Send ALL blocks to the suspicious detector sub-agent
2. The sub-agent should mark 80%+ as needing validation
3. Only blocks with extremely high confidence should pass through

### Fix 3: Remove All Heuristics

Remove from codebase:
- All regex patterns for decision making
- All hardcoded rules (length checks, pattern matching)
- All conditional logic making extraction decisions

## Implementation Gap Analysis

| Component | Current State | Required State | Gap |
|-----------|--------------|----------------|-----|
| Suspicious Detection | Pattern-based with regex | Prompt-based semantic analysis | Major - Complete rewrite needed |
| Detection Rate | ~20% marked suspicious | 80%+ marked suspicious | Major - Logic inversion needed |
| Decision Making | Code-based with if/else | Sub-agent prompts only | Major - Remove all logic |
| Task Execution | Mixed code/prompts | Pure prompt orchestration | Moderate - Structure exists |

## Next Steps

1. **Immediate:** Rewrite `suspicious_detector.py` to use prompts exclusively
2. **Urgent:** Remove all regex patterns and heuristics from the codebase
3. **Critical:** Ensure 80%+ suspicious detection rate through prompt engineering
4. **Important:** Verify all 14 sub-agents are called via prompts, not code

## Conclusion

The current implementation violates the core architectural principle of task list orchestration. While the task list structure is correct, the actual execution still relies heavily on code-based patterns and heuristics. This must be completely refactored to achieve the intended semantic understanding through sub-agent prompts.

**Accuracy Claim Assessment:** The 92% accuracy claim cannot be valid given these violations. True semantic understanding requires delegating ALL decisions to sub-agents, not using regex patterns.