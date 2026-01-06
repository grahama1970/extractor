# Surf

The CLI for AI agents to control Chrome. Zero config, agent-agnostic, battle-tested.

```bash
surf go "https://example.com"
surf read
surf click e5
surf snap
```

## Why Surf

Browser automation for AI agents is harder than it looks. Most tools require complex setup, tie you to specific AI providers, or break on real-world pages.

Surf takes a different approach:

**Agent-Agnostic** - Pure CLI commands over Unix socket. Works with Claude Code, GPT, Gemini, Cursor, custom agents, shell scripts - anything that can run commands.

**Zero Config** - Install the extension, run commands. No MCP servers to configure, no relay processes, no subscriptions.

**Battle-Tested** - Built by reverse-engineering production browser extensions and methodically working through agent-hostile pages like Discord settings. Falls back gracefully when CDP fails.

**Smart Defaults** - Screenshots auto-resize to 1200px (saves tokens). Actions auto-capture screenshots (saves round-trips). Errors on restricted pages warn instead of fail.

**AI Without API Keys** - Query ChatGPT and Gemini using your browser's logged-in session. No API keys, no rate limits, no cost.

## Comparison

| Feature | Surf | Manus | Claude Extension | DevTools MCP | dev-browser |
|---------|------|-------|------------------|--------------|-------------|
| Agent-agnostic | Yes | No (Manus only) | No (Claude only) | Partial | No (Claude skill) |
| Zero config | Yes | No (subscription) | No (subscription) | No (MCP setup) | No (relay server) |
| Local-only | Yes | No (cloud) | Partial | Yes | Partial |
| CLI interface | Yes | No | No | No | No |
| Free | Yes | No | No | Yes | Yes |
| AI via browser cookies | Yes | No | No | No | No |

## Installation

### Quick Start

```bash
# 1. Install globally
npm install -g surf-cli

# 2. Load extension in Chrome
#    - Open chrome://extensions
#    - Enable "Developer mode"
#    - Click "Load unpacked"
#    - Paste the path from: surf extension-path

# 3. Install native host (copy extension ID from chrome://extensions)
surf install <extension-id>

# 4. Restart Chrome and test
surf tab.list
```

### Multi-Browser Support

```bash
surf install <extension-id>                    # Chrome (default)
surf install <extension-id> --browser brave    # Brave
surf install <extension-id> --browser all      # All supported browsers
```

Supported: `chrome`, `chromium`, `brave`, `edge`, `arc`

### Uninstall

```bash
surf uninstall                  # Chrome only
surf uninstall --all            # All browsers + wrapper files
```

### Development Setup

```bash
git clone https://github.com/nicobailon/surf-cli.git
cd surf-cli
npm install
npm run build
# Then load dist/ as unpacked extension
```

## Usage

```bash
surf <command> [args] [options]
surf --help                    # Basic help
surf --help-full               # All 50+ commands
surf <command> --help          # Command details
surf --find <query>            # Search commands
```

### Navigation

```bash
surf go "https://example.com"
surf back
surf forward
surf tab.reload --hard
```

### Reading Pages

```bash
surf read                           # Accessibility tree with element refs
surf page.text                      # Raw text content
surf page.state                     # Modals, loading state, scroll position
```

Element refs (`e1`, `e2`, `e3`...) are stable identifiers from the accessibility tree - semantic, predictable, and resilient to DOM changes.

### Interaction

```bash
surf click e5                       # Click by element ref
surf click --selector ".btn"        # Click by CSS selector
surf click 100 200                  # Click by coordinates
surf type "hello" --submit          # Type and press Enter
surf type "email@example.com" --ref e12  # Type into specific element
surf key Escape                     # Press key
surf scroll.bottom                  # Scroll to bottom
```

### Screenshots

Screenshots are optimized for AI consumption by default:

```bash
surf screenshot --output /tmp/shot.png      # Auto-resized to 1200px max
surf screenshot --full --output /tmp/hd.png # Full resolution
surf screenshot --annotate --output /tmp/labeled.png  # With element labels
surf screenshot --fullpage --output /tmp/full.png     # Entire page
surf snap                                   # Quick save to /tmp
```

Actions like `click`, `type`, and `scroll` automatically capture a screenshot after execution - no extra command needed.

### Tabs

```bash
surf tab.list
surf tab.new "https://example.com"
surf tab.switch 123
surf tab.close 123
surf tab.name "dashboard"           # Name current tab
surf tab.switch "dashboard"         # Switch by name
surf tab.group --name "Work" --color blue
```

### AI Queries (No API Keys)

Query AI models using your browser's logged-in session:

```bash
surf chatgpt "explain this code"
surf chatgpt "summarize" --with-page     # Include page context
surf chatgpt "analyze" --model gpt-4o    # Specify model

# Coming soon
surf gemini "explain this"
surf gemini --generate-image "a robot surfing"
```

Requires being logged into chatgpt.com or gemini.google.com in Chrome.

### Waiting

```bash
surf wait 2                         # Wait 2 seconds
surf wait.element ".loaded"         # Wait for element
surf wait.network                   # Wait for network idle
surf wait.url "/dashboard"          # Wait for URL pattern
```

### Other

```bash
surf js "return document.title"     # Execute JavaScript
surf search "login"                 # Find text in page
surf cookie.list                    # List cookies
surf zoom 1.5                       # Set zoom to 150%
surf console                        # Read console messages
surf network                        # Read network requests
```

## Global Options

```bash
--tab-id <id>     # Target specific tab
--json            # Output raw JSON
--soft-fail       # Warn instead of error (exit 0) on restricted pages
--no-screenshot   # Skip auto-screenshot after actions
--full            # Full resolution screenshots (skip resize)
```

## Socket API

For programmatic integration, send JSON to `/tmp/surf.sock`:

```bash
echo '{"type":"tool_request","method":"execute_tool","params":{"tool":"tab.list","args":{}},"id":"1"}' | nc -U /tmp/surf.sock
```

## Command Groups

| Group | Commands |
|-------|----------|
| `tab.*` | `list`, `new`, `switch`, `close`, `name`, `unname`, `named`, `group`, `ungroup`, `groups`, `reload` |
| `scroll.*` | `top`, `bottom`, `to`, `info` |
| `page.*` | `read`, `text`, `state` |
| `wait.*` | `element`, `network`, `url`, `dom`, `load` |
| `cookie.*` | `list`, `get`, `set`, `clear` |
| `bookmark.*` | `add`, `remove`, `list` |
| `history.*` | `list`, `search` |
| `dialog.*` | `accept`, `dismiss`, `info` |
| `emulate.*` | `network`, `cpu`, `geo` |

## Aliases

| Alias | Command |
|-------|---------|
| `snap` | `screenshot` |
| `read` | `page.read` |
| `find` | `search` |
| `go` | `navigate` |

## How It Works

```
CLI (surf) → Unix Socket → Native Host → Chrome Extension → CDP/Scripting API
```

Surf uses Chrome DevTools Protocol for most operations, with automatic fallback to `chrome.scripting` API when CDP is unavailable (restricted pages, certain contexts). Screenshots fall back to `captureVisibleTab` when CDP capture fails.

## Limitations

- Cannot automate `chrome://` pages or the Chrome Web Store (Chrome restriction)
- First CDP operation on a new tab takes ~100-500ms (debugger attachment)
- Some operations on restricted pages return warnings instead of results

## Development

```bash
npm run dev       # Watch mode
npm run build     # Production build
```

After changes:
- **Extension** (`src/`): Reload at `chrome://extensions`
- **Host** (`native/`): Restart `node native/host.cjs`

## License

MIT
