#!/usr/bin/env bash
set -euo pipefail

# Remote runner for Comet + GitHub Copilot automation via AppleScript
# Usage:
#   REMOTE_HOST=100.84.184.37 REMOTE_USER=graham \
#   ./scripts/remote_copilot_trigger.sh \
#     "What kind of?" \
#     "Github Copilot" \
#     30 \
#     "https://hooks.slack.com/services/XXX/YYY/ZZZ"  # optional

REMOTE_HOST=${REMOTE_HOST:-100.84.184.37}
REMOTE_USER=${REMOTE_USER:-${USER:-graham}}

PROMPT=${1:?"PROMPT is required"}
TAB_NAME=${2:-"Github Copilot"}
WAIT_SEC=${3:-30}
WEBHOOK=${4:-}

echo "[remote] Host=$REMOTE_HOST User=$REMOTE_USER Tab=[$TAB_NAME] Wait=$WAIT_SEC" >&2

# Ensure destination folder exists
ssh -o BatchMode=yes -tt "$REMOTE_USER@$REMOTE_HOST" "mkdir -p \$HOME/automation" </dev/null

# Copy the AppleScript
scp -q scripts/comet_copilot_automation.applescript "$REMOTE_USER@$REMOTE_HOST:automation/comet_copilot_automation.applescript"

# Run it with arguments on the remote Mac
# Note: we carefully quote arguments to preserve spaces
ssh -tt "$REMOTE_USER@$REMOTE_HOST" \
  osascript "\$HOME/automation/comet_copilot_automation.applescript" \
    "$PROMPT" "$TAB_NAME" "$WAIT_SEC" "$WEBHOOK"

echo "[remote] Triggered Copilot automation." >&2

