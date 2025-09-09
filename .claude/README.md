# Claude Code Configuration

This directory contains the global Claude Code configuration for debugging ALL projects.

## Unified Settings

The `settings.json` file now supports environment variables to toggle between different hook modes:

### Environment Variables

- `CLAUDE_HOOKS_SERVER_URL` - Hook server URL (default: http://localhost:8002/events)
- `CLAUDE_HOOKS_CAPTURE_MODE` - Hook script to use:
  - `send_event_litellm` (default) - Basic event logging with AI summarization
  - `capture_raw_responses` - Enhanced capture with raw tool outputs
- `CLAUDE_HOOKS_RAW_RESPONSES` - Capture raw responses (default: false)
- `CLAUDE_HOOKS_LOG_LEVEL` - Log level (default: info)
- `CLAUDE_HOOKS_DASHBOARD_ENABLED` - Enable dashboard (default: true)
- `CLAUDE_HOOKS_DASHBOARD_URL` - Dashboard URL (default: http://localhost:5178)
- `CLAUDE_HOOKS_API_URL` - API URL (default: http://localhost:8002)

### Hook Scripts

All hooks are located in `.claude/hooks/`:

1. **send_event.py** - Basic event sender (legacy, includes Anthropic dependency)
2. **send_event_litellm.py** - Enhanced with LiteLLM for multi-model summarization
3. **capture_raw_responses.py** - Advanced capture with full tool outputs and context

### Usage Examples

```bash
# Use basic mode
export CLAUDE_HOOKS_CAPTURE_MODE=send_event_litellm

# Use enhanced capture with raw responses
export CLAUDE_HOOKS_CAPTURE_MODE=capture_raw_responses
export CLAUDE_HOOKS_RAW_RESPONSES=true

# Change server URL
export CLAUDE_HOOKS_SERVER_URL=http://myserver:8002/events
```

### Previous Settings Variants (Removed)

- `settings.json` - Basic hooks (now unified)
- `settings_litellm.json` - Added AI summarization (now via env vars)
- `settings_enhanced.json` - Full dashboard integration (now via env vars)

The unified settings.json uses environment variables to provide the same functionality
as all three previous variants.