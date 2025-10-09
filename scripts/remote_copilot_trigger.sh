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
SSH_OPTS=${SSH_OPTS:-"-i ~/.ssh/id_ed25519_comet"}

# Args: inline string or -f file
PROMPT_ARG=${1:-}
if [[ -z "${PROMPT_ARG}" ]]; then
  echo "ERROR: Provide a prompt string, or -f <file>." >&2
  exit 2
fi
if [[ "${PROMPT_ARG}" == "-f" ]]; then
  LOCAL_PROMPT_FILE=${2:-}
  if [[ -z "${LOCAL_PROMPT_FILE}" || ! -f "${LOCAL_PROMPT_FILE}" ]]; then
    echo "ERROR: -f specified but local prompt file not found: ${LOCAL_PROMPT_FILE}" >&2
    exit 2
  fi
  shift 2
  PROMPT_SRC="file"
else
  shift 1
  PROMPT_SRC="inline"
fi
TAB_NAME=${1:-"Github Copilot"}
WAIT_SEC=${2:-120}

echo "[remote] Host=$REMOTE_HOST User=$REMOTE_USER Tab=[$TAB_NAME] Timeout=$WAIT_SEC" >&2

# Ensure destination folder exists
ssh $SSH_OPTS -o BatchMode=yes -tt "$REMOTE_USER@$REMOTE_HOST" "mkdir -p \$HOME/automation" </dev/null

# Preflight: verify Accessibility/Automation (avoid hanging on TCC prompts)
echo "[remote] Preflight: ensuring CopilotRunner.app exists…" >&2
ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" \
  'mkdir -p "$HOME/automation"; \
   if [ ! -d "$HOME/automation/CopilotRunner.app" ]; then \
     osacompile -o "$HOME/automation/CopilotRunner.app" "$HOME/automation/comet_copilot_automation.applescript" || exit 3; \
   fi'

# Copy the AppleScript and prompt file
scp $SSH_OPTS -q scripts/comet_copilot_automation.applescript "$REMOTE_USER@$REMOTE_HOST:automation/comet_copilot_automation.applescript"
if [[ "$PROMPT_SRC" == "file" ]]; then
  scp $SSH_OPTS -q "$LOCAL_PROMPT_FILE" "$REMOTE_USER@$REMOTE_HOST:automation/copilot_prompt.txt"
else
  printf "%s" "$PROMPT_ARG" | ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" 'cat > "$HOME/automation/copilot_prompt.txt"'
fi
printf "%s" "$TAB_NAME" | ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" 'cat > "$HOME/automation/copilot_tab.txt"'

# Run it with arguments on the remote Mac
# Note: we carefully quote arguments to preserve spaces
echo "[remote] Launching CopilotRunner.app…" >&2
ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" \
  'open -a "$HOME/automation/CopilotRunner.app" --args \
     "FILE::$HOME/automation/copilot_prompt.txt" '"$TAB_NAME"' '"$WAIT_SEC"' '"$WEBHOOK"' || exit 4'

echo "[remote] Waiting for completion flag (timeout: $WAIT_SEC s)…" >&2
SECONDS_WAITED=0
while (( SECONDS_WAITED < WAIT_SEC )); do
  if ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" 'test -f "$HOME/automation/copilot_done.flag"' >/dev/null 2>&1; then
    break
  fi
  if ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" 'test -f "$HOME/automation/copilot_error.flag"' >/dev/null 2>&1; then
    echo "ERROR: Remote error flag present:" >&2
    ssh $SSH_OPTS -tt "$REMOTE_USER@$REMOTE_HOST" 'cat "$HOME/automation/copilot_error.flag"' >&2 || true
    exit 1
  fi
  sleep 1
  SECONDS_WAITED=$((SECONDS_WAITED + 1))
done

if (( SECONDS_WAITED >= WAIT_SEC )); then
  echo "ERROR: Timeout waiting for completion" >&2
  exit 1
fi

echo "[remote] Fetching response file…" >&2
mkdir -p scripts/artifacts
scp $SSH_OPTS -q "$REMOTE_USER@$REMOTE_HOST:automation/copilot_response.txt" scripts/artifacts/copilot_response.txt || true
echo "[remote] Saved: scripts/artifacts/copilot_response.txt" >&2

echo "[remote] Triggered Copilot automation." >&2
