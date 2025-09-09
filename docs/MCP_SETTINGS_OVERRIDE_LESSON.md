# Critical MCP Configuration Lesson - Settings Override Issue

## Problem
MCP servers failed to load - wasted 5 hours debugging with false leads from Claude.

## Root Cause
`settings.local.json` contained only environment variables but no `mcpServers` section:

```json
{
  "env": {
    "VIRTUAL_ENV": "$CLAUDE_PROJECT_DIR/.venv",
    "PATH": "/home/graham/.nvm/versions/node/v22.15.0/bin:$CLAUDE_PROJECT_DIR/.venv/bin:$PATH"
  }
}
```

This COMPLETELY OVERRIDES all MCP server definitions from parent config files, effectively clearing them out.

## Solution
Delete `settings.local.json` or ensure it includes the `mcpServers` section.

## Key Learning
**Settings files override COMPLETELY, not partially.** An incomplete `settings.local.json` with only env vars will CLEAR all MCP server definitions from parent configs.

## Settings Load Order
1. Global settings
2. Workspace settings  
3. Project settings (.claude/settings.json)
4. Local overrides (.claude/settings.local.json) **← THIS WINS**

## Correct Debug Order for MCP Issues
1. **FIRST** - Check if `settings.local.json` EXISTS and check its CONTENTS
2. Compare against working `.mcp.json.example` 
3. Understand the override hierarchy
4. Delete or fix incomplete local overrides

## What NOT to Do (What Claude Did Wrong)
- Generic "check your API keys" advice
- "Try restarting" suggestions
- Complex debugging commands  
- Everything EXCEPT looking at the actual config file

## Correct settings.local.json Format
If you need local overrides, include BOTH sections:

```json
{
  "env": {
    "VIRTUAL_ENV": "$CLAUDE_PROJECT_DIR/.venv",
    "PATH": "/home/graham/.nvm/versions/node/v22.15.0/bin:$CLAUDE_PROJECT_DIR/.venv/bin:$PATH"
  },
  "mcpServers": {
    // Must include all MCP server definitions here
    // or they will be cleared!
  }
}
```

## Time Wasted
5 hours due to not checking the obvious configuration file first.

---
Recorded: 2025-08-04