# Detailed Claude CLI Problem Report

## Environment
- **OS**: Linux 6.8.0-57-generic
- **Installation**: Bun (path: /home/graham/.bun/bin/claude)
- **Credentials**: Valid OAuth tokens in ~/.claude/.credentials.json
- **API Key**: Not set (removed from environment per --dangerously-skip-permissions requirements)

## Problem Description
The Claude CLI hangs indefinitely on EVERY command, including:
- `claude --version` 
- `claude -p "test"`
- `claude -p --dangerously-skip-permissions "test"`
- Any other claude command

## What Happens
1. Command is executed
2. Process starts but produces NO output
3. Process hangs forever (tested up to 5 minutes)
4. Must be killed with Ctrl+C or timeout

## Debugging Attempts
1. **Checked credentials**: Valid OAuth tokens present, not expired
2. **Environment variables**: Removed ANTHROPIC_API_KEY as required
3. **MCP config**: Using valid .mcp.json at project root
4. **Timeout increases**: Set to 5 minutes, still hangs
5. **Verbose mode**: Added --verbose flag, no output at all
6. **Direct subprocess test**: Hangs even when called directly

## Code Context
The pipeline uses ClaudeProcessor class in:
`/home/graham/workspace/experiments/extractor/src/extractor/pipeline/poc/utils/claude_processor.py`

Key command construction:
```python
cmd = [self.claude_bin, '-p', '--dangerously-skip-permissions']
if verbose:
    cmd.append('--verbose')
cmd.extend(['--output-format', 'json'])
if self.mcp_config_path:
    cmd.extend(['--mcp-config', str(self.mcp_config_path)])
```

## Impact
Three critical pipeline steps fail:
1. **POC 01**: Cannot analyze PDF annotations (13 images)
2. **POC 03**: Cannot identify/fix misclassified blocks
3. **POC 05**: Cannot enhance section structures

Without Claude, the pipeline produces worthless output.

## Research Findings
- This matches GitHub issue #5010 on anthropics/claude-code
- Affects WSL2 Debian and Bun installations particularly
- No user-side fix available
- CLI never gets far enough to check auth or make API calls

## What We Need
Either:
1. A fix from Anthropic for the CLI hanging issue
2. Diagnostic steps to understand WHY it's hanging
3. An alternative installation method that works

The pipeline is completely non-functional without Claude CLI.