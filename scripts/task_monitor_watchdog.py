#!/usr/bin/env python3
"""
Task Monitor Watchdog for PDF Corpus Extraction

Monitors the continuous_learning_daemon and:
1. Updates task-monitor state every 30 seconds
2. Detects stalls (no progress for 5+ minutes)
3. Stops and debugs if error rate exceeds threshold
4. Auto-restarts daemon on stall
"""
import os
import sys
import json
import time
import subprocess
import re
from pathlib import Path
from datetime import datetime, timedelta

import httpx
from loguru import logger

# Configuration
DAEMON_LOG = Path.home() / ".pi" / "continuous-learning" / "daemon.log"
DAEMON_STATE = Path.home() / ".pi" / "continuous-learning" / "state.json"
TASK_MONITOR_API = "http://localhost:8765"
TASK_NAME = "pdf-corpus-extraction"

CHECK_INTERVAL = 30  # seconds
STALL_THRESHOLD = 300  # 5 minutes without progress = stall
ERROR_THRESHOLD = 0.20  # 20% error rate = stop and debug
TOTAL_PDFS = 8481

# Track state
last_processed = 0
last_activity = time.time()
stall_count = 0


def get_daemon_stats() -> dict:
    """Parse daemon state file for current stats."""
    if not DAEMON_STATE.exists():
        return {"processed": 0, "failures": 0, "tables": 0}

    try:
        state = json.loads(DAEMON_STATE.read_text())
        stats = state.get("stats", {})
        return {
            "processed": stats.get("total_processed", 0),
            "failures": stats.get("total_failures", 0),
            "tables": stats.get("total_tables", 0),
            "sections": stats.get("total_sections", 0),
        }
    except Exception as e:
        logger.error(f"Failed to read state: {e}")
        return {"processed": 0, "failures": 0, "tables": 0}


def get_log_last_modified() -> float:
    """Get timestamp of last log modification."""
    if DAEMON_LOG.exists():
        return DAEMON_LOG.stat().st_mtime
    return 0


def is_daemon_running() -> bool:
    """Check if daemon process is running."""
    result = subprocess.run(
        ["pgrep", "-f", "continuous_learning_daemon.py start"],
        capture_output=True
    )
    return result.returncode == 0


def restart_daemon():
    """Restart the daemon."""
    logger.warning("Restarting daemon...")
    subprocess.run(["pkill", "-9", "-f", "continuous_learning_daemon.py"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(
        [sys.executable, "scripts/continuous_learning_daemon.py", "start"],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    if is_daemon_running():
        logger.info("Daemon restarted successfully")
    else:
        logger.error("Daemon failed to restart!")


def update_task_monitor(stats: dict):
    """Push stats to task-monitor API."""
    try:
        payload = {
            "processed": stats["processed"],
            "total": TOTAL_PDFS,
            "failures": stats["failures"],
            "rate": stats.get("rate", 0),
            "eta_seconds": stats.get("eta_seconds", 0),
        }
        resp = httpx.post(
            f"{TASK_MONITOR_API}/tasks/{TASK_NAME}/state",
            json=payload,
            timeout=5.0
        )
        if resp.status_code == 200:
            logger.debug(f"Updated task-monitor: {stats['processed']}/{TOTAL_PDFS}")
    except Exception as e:
        logger.debug(f"Task-monitor update failed (API may not be running): {e}")


def check_and_update():
    """Main watchdog check."""
    global last_processed, last_activity, stall_count

    stats = get_daemon_stats()
    processed = stats["processed"]
    failures = stats["failures"]

    # Calculate rate
    if processed > last_processed:
        last_activity = time.time()
        stall_count = 0

    idle_time = time.time() - last_activity

    # Check for stall
    if idle_time > STALL_THRESHOLD:
        stall_count += 1
        logger.warning(f"STALL DETECTED: No progress for {idle_time:.0f}s (count: {stall_count})")

        if not is_daemon_running():
            logger.error("Daemon not running - restarting")
            restart_daemon()
        elif stall_count >= 3:
            logger.error("Multiple stalls detected - force restarting daemon")
            restart_daemon()
            stall_count = 0

    # Check error rate
    if processed > 100:  # Only check after warmup
        error_rate = failures / processed
        if error_rate > ERROR_THRESHOLD:
            logger.error(f"ERROR RATE TOO HIGH: {error_rate:.1%} ({failures}/{processed})")
            logger.error("Stopping for investigation - check logs")
            # Don't auto-restart, need human review
            return False

    # Calculate ETA
    remaining = TOTAL_PDFS - processed
    elapsed_since_start = time.time() - (last_activity - idle_time) if idle_time < 60 else 60
    rate = (processed - last_processed) / max(CHECK_INTERVAL, 1) if processed > last_processed else 0
    eta_seconds = remaining / rate if rate > 0 else 0

    stats["rate"] = rate
    stats["eta_seconds"] = eta_seconds

    # Update task-monitor
    update_task_monitor(stats)

    # Log status
    logger.info(
        f"Status: {processed}/{TOTAL_PDFS} ({processed/TOTAL_PDFS*100:.1f}%) | "
        f"Failures: {failures} ({failures/max(processed,1)*100:.1f}%) | "
        f"Tables: {stats['tables']} | "
        f"Idle: {idle_time:.0f}s"
    )

    last_processed = processed
    return True


def main():
    """Run watchdog loop."""
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        Path.home() / ".pi" / "continuous-learning" / "watchdog.log",
        rotation="10 MB",
        level="DEBUG"
    )

    logger.info("=" * 60)
    logger.info("Task Monitor Watchdog Starting")
    logger.info(f"Monitoring: {DAEMON_LOG}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s, Stall threshold: {STALL_THRESHOLD}s")
    logger.info("=" * 60)

    # Ensure daemon is running
    if not is_daemon_running():
        logger.warning("Daemon not running - starting it")
        restart_daemon()

    while True:
        try:
            if not check_and_update():
                logger.error("Watchdog stopping due to high error rate")
                break
        except Exception as e:
            logger.error(f"Watchdog error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
