#!/usr/bin/env bash
set -euo pipefail

# Mac → Ubuntu local port forwards for app & DevTools (CDP).

UBUNTU_HOST="${UBUNTU_HOST:-192.168.86.49}"
UBUNTU_USER="${UBUNTU_USER:-graham}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_wsl2}"

# Preferred local ports (will auto-fallback if busy). Use uncommon defaults.
PREF_LOCAL_APP_PORT="${LOCAL_APP_PORT:-18404}"
PREF_LOCAL_CDP_PORT="${LOCAL_CDP_PORT:-18944}"

# Remote endpoints on Ubuntu (Chrome should bind CDP to 127.0.0.1)
REMOTE_APP_HOST="${REMOTE_APP_HOST:-127.0.0.1}"
REMOTE_APP_PORT="${REMOTE_APP_PORT:-3012}"
REMOTE_CDP_HOST="${REMOTE_CDP_HOST:-127.0.0.1}"
REMOTE_CDP_PORT="${REMOTE_CDP_PORT:-9222}"

# -----------------------------------------------------------------------------
log() { printf "\033[1;35m[mac_tunnel]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[mac_tunnel]\033[0m %s\n" "$*" >&2; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || { err "Missing dependency: $1"; exit 1; }; }

need_cmd ssh
need_cmd lsof
# curl/jq optional
command -v curl >/dev/null 2>&1 || log "TIP: install curl for health checks (brew install curl)"
command -v jq   >/dev/null 2>&1 || log "TIP: install jq for nicer CDP info (brew install jq)"

port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

show_listener_owner() {
  local port="$1"
  if port_in_use "$port"; then
    log "Port $port already in use by:"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN || true
  fi
}

# Choose a free port not in the avoid set. Tries preferred, then scans 20000-60999.
find_free_port_not_in() {
  local preferred="$1"; shift
  local -a avoid=( "$@" )
  local p

  port_ok() {
    local q="$1"
    for a in "${avoid[@]}"; do
      [[ "$q" == "$a" ]] && return 1
    done
    ! port_in_use "$q"
  }

  if port_ok "$preferred"; then
    echo "$preferred"; return 0
  fi

  # Use jot if available (macOS), else seq
  if command -v jot >/dev/null 2>&1; then
    for p in $(jot 40999 20000 60999); do
      if port_ok "$p"; then echo "$p"; return 0; fi
    done
  else
    for p in $(seq 20000 60999); do
      if port_ok "$p"; then echo "$p"; return 0; fi
    done
  fi

  return 1
}

# Optional: check remote host:port is reachable over SSH (requires 'nc' remotely)
remote_reachable() {
  local host="$1" port="$2"
  ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes "${UBUNTU_USER}@${UBUNTU_HOST}" \
    "command -v nc >/dev/null 2>&1 && nc -z -w 2 $host $port" >/dev/null 2>&1
}

# -----------------------------------------------------------------------------
log "Selecting local ports…"

LOCAL_APP_PORT="$(find_free_port_not_in "$PREF_LOCAL_APP_PORT")" \
  || { err "No free local ports found for APP."; exit 1; }

LOCAL_CDP_PORT="$(find_free_port_not_in "$PREF_LOCAL_CDP_PORT" "$LOCAL_APP_PORT")" \
  || { err "No free local ports found for CDP."; exit 1; }

# Extra guard: ensure they differ
if [[ "$LOCAL_APP_PORT" == "$LOCAL_CDP_PORT" ]]; then
  err "Local ports collided ($LOCAL_APP_PORT). Aborting."
  exit 1
fi

# If preferreds were busy, mention it; also show who owns them for diagnostics.
if [[ "$LOCAL_APP_PORT" != "$PREF_LOCAL_APP_PORT" ]]; then
  log "Preferred LOCAL_APP_PORT=$PREF_LOCAL_APP_PORT was busy; using $LOCAL_APP_PORT"
  show_listener_owner "$PREF_LOCAL_APP_PORT" || true
fi
if [[ "$LOCAL_CDP_PORT" != "$PREF_LOCAL_CDP_PORT" ]]; then
  log "Preferred LOCAL_CDP_PORT=$PREF_LOCAL_CDP_PORT was busy; using $LOCAL_CDP_PORT"
  show_listener_owner "$PREF_LOCAL_CDP_PORT" || true
fi

log "Planned tunnels:"
log "  http://localhost:${LOCAL_APP_PORT}  →  ${REMOTE_APP_HOST}:${REMOTE_APP_PORT} @ ${UBUNTU_USER}@${UBUNTU_HOST}"
log "  http://localhost:${LOCAL_CDP_PORT}  →  ${REMOTE_CDP_HOST}:${REMOTE_CDP_PORT} @ ${UBUNTU_USER}@${UBUNTU_HOST}"

# Optional pre-flight checks (non-fatal if 'nc' missing remotely)
if remote_reachable "$REMOTE_APP_HOST" "$REMOTE_APP_PORT"; then
  log "Remote app ${REMOTE_APP_HOST}:${REMOTE_APP_PORT} looks reachable."
else
  log "WARN: Could not verify ${REMOTE_APP_HOST}:${REMOTE_APP_PORT} (nc missing or closed). Continuing…"
fi
if remote_reachable "$REMOTE_CDP_HOST" "$REMOTE_CDP_PORT"; then
  log "Remote CDP ${REMOTE_CDP_HOST}:${REMOTE_CDP_PORT} looks reachable."
else
  log "WARN: Could not verify ${REMOTE_CDP_HOST}:${REMOTE_CDP_PORT}. Continuing…"
fi

# -----------------------------------------------------------------------------
# Start SSH tunnels with robust options
SSH_OPTS=(
  -i "$SSH_KEY"
  -N                           # no remote command
  -o ExitOnForwardFailure=yes  # fail if any -L can't bind
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
  -o TCPKeepAlive=yes
  -o ConnectTimeout=10
  -o BatchMode=yes
)

# If you trust the host and want non-interactive first run, uncomment:
# SSH_OPTS+=(-o StrictHostKeyChecking=accept-new)

# Clean shutdown
SSH_PID=""
cleanup() {
  local code=$?
  if [[ -n "${SSH_PID:-}" ]] && kill -0 "$SSH_PID" 2>/dev/null; then
    log "Shutting down SSH tunnel (pid $SSH_PID)…"
    kill "$SSH_PID" 2>/dev/null || true
    wait "$SSH_PID" 2>/dev/null || true
  fi
  exit "$code"
}
trap cleanup INT TERM EXIT

# Launch
log "Establishing SSH tunnels…"
set +e
ssh "${SSH_OPTS[@]}" \
  -L "${LOCAL_APP_PORT}:${REMOTE_APP_HOST}:${REMOTE_APP_PORT}" \
  -L "${LOCAL_CDP_PORT}:${REMOTE_CDP_HOST}:${REMOTE_CDP_PORT}" \
  "${UBUNTU_USER}@${UBUNTU_HOST}" &
SSH_PID=$!
set -e

# Give SSH a moment to bind or fail
sleep 0.8

if ! kill -0 "$SSH_PID" 2>/dev/null; then
  err "SSH process exited early (bind failure or auth issue)."
  exit 1
fi

# -----------------------------------------------------------------------------
# Health checks (non-fatal)
check_url() {
  local url="$1" tries="${2:-30}" delay="${3:-0.3}"
  command -v curl >/dev/null 2>&1 || return 0
  for _ in $(seq 1 "$tries"); do
    curl -fs "$url" >/dev/null 2>&1 && return 0
    sleep "$delay"
  done
  return 1
}

if check_url "http://localhost:${LOCAL_APP_PORT}"; then
  log "App tunnel OK → http://localhost:${LOCAL_APP_PORT}"
else
  log "WARN: App not responding yet at http://localhost:${LOCAL_APP_PORT}"
fi

if check_url "http://localhost:${LOCAL_CDP_PORT}/json/version"; then
  log "CDP tunnel OK → http://localhost:${LOCAL_CDP_PORT}/json/version"
  if command -v jq >/dev/null 2>&1; then
    curl -s "http://localhost:${LOCAL_CDP_PORT}/json/version" | jq '{Browser, webSocketDebuggerUrl}' || true
    log "Targets:"
    curl -s "http://localhost:${LOCAL_CDP_PORT}/json/list" | jq -r '.[].title' || true
  else
    curl -s "http://localhost:${LOCAL_CDP_PORT}/json/version" || true
  fi
  log "Chrome → chrome://inspect → Configure… → add localhost:${LOCAL_CDP_PORT} → Inspect"
else
  log "WARN: DevTools not responding yet at http://localhost:${LOCAL_CDP_PORT}"
fi

# Block and keep the tunnels up
wait "$SSH_PID"
