# Code Reviewer Sub-Agent Update Summary

## Overview

Updated the code_reviewer.md sub-agent to properly use the `generate_code_review_bundle.py` script as recommended in the Claude Code documentation for sub-agents.

## Changes Made

### 1. Added Sub-Agent Header
- Added proper YAML frontmatter with name and description
- This follows the standard sub-agent format

### 2. Referenced Primary Tool
- Clearly stated that the primary tool is `/home/graham/workspace/experiments/extractor/.claude/agents/core/generate_code_review_bundle.py`
- This makes it explicit which script should be used for code reviews

### 3. Updated Integration Section
- Replaced generic integration examples with specific usage of `generate_code_review_bundle.py`
- Added command-line examples for all major use cases:
  - Basic bundle generation
  - AI-powered reviews
  - Clipboard copying for manual review
  - Git information inclusion

### 4. Added Workflow Examples
- Created step-by-step workflow showing how to:
  1. Create configuration files
  2. Create review prompts
  3. Generate review bundles
- Provided real bash commands that can be executed

### 5. Added Script Location Section
- Created dedicated section emphasizing the script location
- Added quick usage examples
- Documented output locations:
  - AI reviews go to `docs/code_reviews/`
  - Temporary files go to `tmp/responses/`
  - Clipboard option for when no API key is available

### 6. Enhanced Remember Section
- Added reminder to use `generate_code_review_bundle.py` as primary tool
- Added note about using --clipboard when AI review fails

## Benefits

1. **Clarity**: The sub-agent now clearly states which tool to use
2. **Usability**: Provides concrete examples that can be copied and run
3. **Fallback Options**: Documents what to do when API keys are missing
4. **Best Practices**: Follows Claude Code documentation recommendations

## Usage Example

```bash
# Create a review config
cat > /tmp/review_config.json << 'EOF'
{
    "code_review_prompt_file": "prompts/review.md",
    "files_to_review": [
        {"path": "src/main.py", "rationale": "Core logic"}
    ]
}
EOF

# Create prompt
echo "Review for quality and security issues" > prompts/review.md

# Generate review
python /home/graham/workspace/experiments/extractor/.claude/agents/core/generate_code_review_bundle.py \
  /tmp/review_config.json --ai-review
```

This update ensures the code reviewer sub-agent follows best practices and uses the dedicated bundling script for all code review operations.