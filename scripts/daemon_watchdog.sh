#!/bin/bash
# Daemon Watchdog - Monitors continuous_learning_daemon and restarts if stalled
#
# Run with: nohup ./scripts/daemon_watchdog.sh &
# Or install as systemd service for production

set -e

DAEMON_SCRIPT="scripts/continuous_learning_daemon.py"
LOG_FILE="$HOME/.pi/continuous-learning/daemon.log"
WATCHDOG_LOG="$HOME/.pi/continuous-learning/watchdog.log"
STALL_THRESHOLD=300  # 5 minutes without log activity = stalled
CHECK_INTERVAL=60    # Check every 60 seconds

cd "$(dirname "$0")/.."
source .venv/bin/activate

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$WATCHDOG_LOG"
}

is_daemon_running() {
    pgrep -f "continuous_learning_daemon.py start" > /dev/null 2>&1
}

get_log_age() {
    if [[ -f "$LOG_FILE" ]]; then
        local last_mod=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
        local now=$(date +%s)
        echo $((now - last_mod))
    else
        echo 999999  # Very old if no log
    fi
}

restart_daemon() {
    log "Restarting daemon..."
    pkill -9 -f "continuous_learning_daemon.py" 2>/dev/null || true
    sleep 2
    nohup python "$DAEMON_SCRIPT" start >> "$WATCHDOG_LOG" 2>&1 &
    sleep 3
    if is_daemon_running; then
        log "Daemon restarted successfully (PID: $(pgrep -f 'continuous_learning_daemon.py start'))"
    else
        log "ERROR: Daemon failed to restart!"
    fi
}

log "Watchdog starting - monitoring $DAEMON_SCRIPT"
log "Stall threshold: ${STALL_THRESHOLD}s, Check interval: ${CHECK_INTERVAL}s"

while true; do
    if ! is_daemon_running; then
        log "Daemon not running - starting..."
        restart_daemon
    else
        log_age=$(get_log_age)
        if [[ $log_age -gt $STALL_THRESHOLD ]]; then
            log "STALL DETECTED: Log unchanged for ${log_age}s (threshold: ${STALL_THRESHOLD}s)"
            restart_daemon
        else
            # Only log every 5 minutes to reduce noise
            if [[ $(($(date +%s) % 300)) -lt $CHECK_INTERVAL ]]; then
                log "Daemon healthy - log age: ${log_age}s"
            fi
        fi
    fi
    sleep $CHECK_INTERVAL
done
