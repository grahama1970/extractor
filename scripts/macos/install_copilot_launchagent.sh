#!/usr/bin/env bash
set -euo pipefail

# Usage: REMOTE_HOST=1.2.3.4 REMOTE_USER=robert scripts/macos/install_copilot_launchagent.sh

REMOTE_HOST=${REMOTE_HOST:-}
REMOTE_USER=${REMOTE_USER:-}
SSH_OPTS=${SSH_OPTS:-"-i ~/.ssh/id_ed25519_comet"}

if [[ -z "$REMOTE_HOST" || -z "$REMOTE_USER" ]]; then
  echo "Set REMOTE_HOST and REMOTE_USER" >&2
  exit 2
fi

PLIST_LOCAL="scripts/macos/com.extractor.copilot.watch.plist"

echo "[install] Ensuring LaunchAgents directory exists…"
ssh ${SSH_OPTS} -tt "${REMOTE_USER}@${REMOTE_HOST}" 'mkdir -p "$HOME/Library/LaunchAgents"' </dev/null

echo "[install] Copying LaunchAgent plist…"
scp ${SSH_OPTS} -q "${PLIST_LOCAL}" "${REMOTE_USER}@${REMOTE_HOST}:~/Library/LaunchAgents/com.extractor.copilot.watch.plist"

echo "[install] Loading agent (user domain)…"
ssh ${SSH_OPTS} -tt "${REMOTE_USER}@${REMOTE_HOST}" \
  'launchctl unload "$HOME/Library/LaunchAgents/com.extractor.copilot.watch.plist" 2>/dev/null || true; \
   launchctl load -w "$HOME/Library/LaunchAgents/com.extractor.copilot.watch.plist" || true'

echo "[install] Done. To verify, touch the watched file: \n  printf %s Test > $HOME/automation/copilot_prompt.txt"
