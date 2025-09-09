# Claude CLI Fix - Working Solution

## Problem
Claude CLI hangs when run through Bun wrapper (known bug #5010).

## Solution
Use Node.js directly to run Claude CLI.

## How to Apply the Fix

### Option 1: Temporary Fix (Current Session)
```bash
export CLAUDE_BIN="node /home/graham/.bun/install/global/node_modules/@anthropic-ai/claude-code/cli.js"
```

### Option 2: Permanent Fix
Add the above line to your `~/.bashrc` or `~/.zshrc`

### Option 3: Use the Setup Script
```bash
source ./setup_claude_fix.sh
```

## Why This Works
- The ClaudeProcessor already checks for `CLAUDE_BIN` environment variable
- If set, it uses that instead of the default `claude` command
- Node.js can run the CLI directly without the Bun wrapper issues

## No Code Changes Needed
The existing `claude_processor.py` already has this code:
```python
self.claude_bin = os.environ.get('CLAUDE_BIN', 'claude')
```

So by setting the environment variable, the pipeline will automatically use Node.