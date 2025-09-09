# Clipboard Feature Documentation

## Overview

The `--clipboard` option allows you to copy the generated code review bundle directly to your clipboard, making it easy to paste into other applications without AI review.

## Usage

```bash
# Copy bundle to clipboard
python generate_code_review_bundle.py config.json --clipboard

# Quiet mode (no output except clipboard)
python generate_code_review_bundle.py config.json --clipboard --quiet

# With file output AND clipboard
python generate_code_review_bundle.py config.json --output-file bundle.md --clipboard
```

## Implementation Details

### Primary Method: pyperclip
The script first attempts to use `pyperclip`, which works on:
- macOS (using pbcopy)
- Windows (using Windows clipboard API)
- Linux with X11 (using xclip/xsel)

### Fallback Method: OSC 52
When pyperclip fails (common on headless Linux servers), the script falls back to OSC 52 escape sequences. This works with terminals that support OSC 52:
- iTerm2
- kitty
- tmux (with proper configuration)
- Modern terminal emulators

The OSC 52 method encodes the content in base64 and sends it via an escape sequence:
```
\033]52;c;{base64_content}\a
```

## Installation

```bash
# Install pyperclip
uv add pyperclip

# For Linux X11 support (optional)
sudo apt-get install xclip
# or
sudo apt-get install xsel
```

## Behavior

1. **Overrides AI Review**: When `--clipboard` is used, it takes precedence over `--ai-review`
2. **Content Generation**: The bundle is generated normally but copied to clipboard instead of AI review
3. **File Output**: You can still save to a file while also copying to clipboard
4. **Error Handling**: If clipboard copy fails, the script exits with error code 1

## Example Workflow

```bash
# Generate bundle and copy to clipboard
python generate_code_review_bundle.py generate_code_config_embedded.json --clipboard

# Then paste into your favorite AI tool (ChatGPT, Claude, etc.)
# Or paste into a document for manual review
```

## Troubleshooting

### Linux Without X11
If you see: "Pyperclip could not find a copy/paste mechanism"
- The script will automatically fall back to OSC 52
- Ensure your terminal supports OSC 52
- Check tmux configuration if using tmux

### OSC 52 Not Working
Some terminals may have OSC 52 disabled for security:
- iTerm2: Preferences → General → Selection → "Applications in terminal may access clipboard"
- tmux: Add to `.tmux.conf`: `set -g set-clipboard on`

### Large Content
Very large bundles may exceed clipboard limits:
- System clipboard limits vary by OS
- OSC 52 has a 100KB limit in some terminals
- Consider using file output for very large bundles

## Benefits

1. **Flexibility**: Use any AI tool, not just LiteLLM-supported models
2. **Cost Control**: Review costs before sending to expensive models
3. **Privacy**: Keep sensitive code local, paste only when ready
4. **Integration**: Easy integration with other tools and workflows