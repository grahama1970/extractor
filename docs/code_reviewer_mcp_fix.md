# Code-Reviewer MCP Fix Documentation

## Issue Identified
The code-reviewer MCP tool is not working because it's not configured in the current Claude session's MCP server list.

## Root Cause
When you run `mcp__code-reviewer__review_cli`, Claude returns "Not connected" because the MCP server is not loaded in the current session. This is a configuration issue, not a code issue.

## Solution

### Option 1: Configure MCP in Claude Desktop (Recommended)
Add the code-reviewer MCP to your Claude Desktop configuration:

1. Open Claude Desktop settings
2. Go to the Developer section
3. Add the following to your MCP server configuration:

```json
{
  "code-reviewer": {
    "command": "node",
    "args": [
      "/home/graham/.claude/mcp/code-reviewer/index.js"
    ],
    "env": {
      "PYTHONPATH": "/home/graham/.claude:/home/graham/.claude/mcp/code-reviewer"
    }
  }
}
```

### Option 2: Use Direct Python Script
Since the MCP is just a wrapper around the Python code-reviewer, you can use it directly:

```python
import sys
import json
from pathlib import Path

# Add the code-reviewer to path
sys.path.insert(0, '/home/graham/.claude/workers')
from code_reviewer_bundler import CodeReviewBundler

# Create config
config = {
    "project_name": "extractor",
    "code_review_prompt_file": "/path/to/prompt.md",
    "files_to_review": [
        {"path": "src/file1.py", "rationale": "Main implementation"},
        {"path": "src/file2.py", "rationale": "Supporting module"}
    ],
    "model": "moonshot/kimi-k2-turbo-preview"
}

# Run review
bundler = CodeReviewBundler()
result = await bundler.perform_full_review(config)
print(json.dumps(result, indent=2))
```

### Option 3: Use the Worker Script Directly
The code-reviewer has a Typer CLI interface that can be used directly:

```bash
cd /home/graham/.claude/workers
python code_reviewer.py review --config-path /path/to/config.json
```

## What We Found
1. ✅ The code-reviewer MCP server files exist and are properly structured
2. ✅ The Node.js wrapper (index.js) starts without errors
3. ✅ The Python adapter (mcp_adapter.py) has been fixed to handle Path conversions
4. ❌ The MCP is not configured in the current Claude session

## Verification
The MCP server itself is working correctly:
- `/home/graham/.claude/mcp/code-reviewer/index.js` exists and runs
- The Python adapter has proper Path object conversions
- The underlying code_reviewer.py worker is functional

The issue is purely configuration - the MCP needs to be added to Claude's active MCP server list for the `mcp__code-reviewer__*` tools to work.

## Alternative Approach Used
Since the MCP wasn't available in the session, we successfully:
1. Used the Python code-reviewer directly by importing it
2. Created the proper configuration format
3. Successfully sent the code review to Kimi-k2
4. Received and implemented the recommendations

This proves the underlying code-reviewer functionality is working correctly.