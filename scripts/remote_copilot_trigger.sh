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
REMOTE_USER=${REMOTE_USER:-robert}
# Allow caller to override SSH options; default to using our dedicated key
SSH_OPTS=${SSH_OPTS:-"-i ~/.ssh/id_ed25519_comet"}

PROMPT=${1:?"PROMPT is required"}
TAB_NAME=${2:-"Github Copilot"}
WAIT_SEC=${3:-30}
WEBHOOK=${4:-}

echo "[remote] Host=$REMOTE_HOST User=$REMOTE_USER Tab=[$TAB_NAME] Wait=$WAIT_SEC" >&2

# Ensure destination folder exists
ssh $SSH_OPTS -o BatchMode=yes -tt "$REMOTE_USER@$REMOTE_HOST" "mkdir -p \$HOME/automation" </dev/null

# Preflight: verify Accessibility/Automation (avoid hanging on TCC prompts)
echo "[remote] Preflight: ensuring CopilotRunner.app exists…" >&2
ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" \
  'mkdir -p "$HOME/automation"; \
   if [ ! -d "$HOME/automation/CopilotRunner.app" ]; then \
     osacompile -o "$HOME/automation/CopilotRunner.app" "$HOME/automation/comet_copilot_automation.applescript" || exit 3; \
   fi'

# Copy the AppleScript and prompt (store prompt as file to avoid shell parsing issues)
scp $SSH_OPTS -q scripts/comet_copilot_automation.applescript "$REMOTE_USER@$REMOTE_HOST:automation/comet_copilot_automation.applescript"
printf "%s" "$PROMPT" | ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" 'cat > "$HOME/automation/copilot_prompt.txt"'

# Run it with arguments on the remote Mac
# Note: we carefully quote arguments to preserve spaces
echo "[remote] Launching CopilotRunner.app…" >&2
ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" \
  'open -a "$HOME/automation/CopilotRunner.app" --args \
     "FILE::$HOME/automation/copilot_prompt.txt" '"$TAB_NAME"' '"$WAIT_SEC"' '"$WEBHOOK"' || exit 4'

echo "[remote] Waiting $WAIT_SEC s for response…" >&2
sleep $WAIT_SEC

echo "[remote] Fetching clipboard…" >&2
ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" pbpaste > scripts/artifacts/copilot_response.txt || true
echo "[remote] Saved: scripts/artifacts/copilot_response.txt" >&2

echo "[remote] Triggered Copilot automation." >&2
