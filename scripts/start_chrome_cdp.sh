#!/bin/bash
# Start Chrome with CDP (Chrome DevTools Protocol) for smoke tests
# Usage: ./scripts/start_chrome_cdp.sh [port]
#
# This enables Puppeteer-based smoke tests to connect via:
#   BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser
#   BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:9222/json/version

set -e

CDP_PORT="${1:-9222}"
CHROME_USER_DATA="${CHROME_USER_DATA:-/tmp/chrome-cdp-profile}"

# Find Chrome executable
find_chrome() {
    for cmd in google-chrome google-chrome-stable chromium chromium-browser; do
        if command -v "$cmd" &> /dev/null; then
            echo "$cmd"
            return 0
        fi
    done
    # macOS
    if [[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
        echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return 0
    fi
    return 1
}

CHROME=$(find_chrome) || {
    echo "Error: Chrome not found. Install Google Chrome or Chromium." >&2
    exit 1
}

# Check if CDP port is already in use
if curl -s "http://127.0.0.1:${CDP_PORT}/json/version" &>/dev/null; then
    echo "Chrome CDP already running on port ${CDP_PORT}"
    curl -s "http://127.0.0.1:${CDP_PORT}/json/version" | head -5
    exit 0
fi

echo "Starting Chrome with CDP on port ${CDP_PORT}..."
echo "  Chrome: $CHROME"
echo "  Profile: $CHROME_USER_DATA"

# Start Chrome with remote debugging
"$CHROME" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$CHROME_USER_DATA" \
    --no-first-run \
    --no-default-browser-check \
    --disable-background-networking \
    --disable-client-side-phishing-detection \
    --disable-default-apps \
    --disable-extensions \
    --disable-hang-monitor \
    --disable-popup-blocking \
    --disable-prompt-on-repost \
    --disable-sync \
    --disable-translate \
    --metrics-recording-only \
    --safebrowsing-disable-auto-update \
    --window-size=1280,900 \
    "about:blank" &

CHROME_PID=$!
echo "$CHROME_PID" > /tmp/chrome-cdp.pid

# Wait for CDP to be ready
echo "Waiting for CDP endpoint..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:${CDP_PORT}/json/version" &>/dev/null; then
        echo ""
        echo "Chrome CDP ready!"
        echo "  Discovery URL: http://127.0.0.1:${CDP_PORT}/json/version"
        echo "  PID: $CHROME_PID (saved to /tmp/chrome-cdp.pid)"
        echo ""
        echo "Run smoke tests with:"
        echo "  BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:${CDP_PORT}/json/version make smokes"
        echo ""
        echo "Stop Chrome with:"
        echo "  kill \$(cat /tmp/chrome-cdp.pid)"
        exit 0
    fi
    sleep 0.5
    printf "."
done

echo ""
echo "Error: Chrome CDP did not start within 15 seconds" >&2
kill "$CHROME_PID" 2>/dev/null || true
exit 1
