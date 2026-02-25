#!/usr/bin/env python3
"""
Corpus Building Watchdog - Monitors PDF downloads with task-monitor integration.

Uses the task-monitor adapter pattern for proper integration.
Runs every 30 seconds to track progress and auto-restart failed processes.

Usage:
    python corpus_watchdog.py start
    python corpus_watchdog.py status
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

# Configuration
CORPUS_ROOT = Path(os.getenv("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus"))
TARGET_PDFS = 10000
CHECK_INTERVAL = 30  # seconds
STALL_THRESHOLD = 300  # 5 minutes without progress

# State files
STATE_FILE = Path("/tmp/corpus_watchdog_state.json")
BATCH_STATE_FILE = Path("/tmp/corpus_batch_state.json")  # For task-monitor

app = typer.Typer()


def count_pdfs() -> int:
    """Count total PDFs in corpus."""
    if not CORPUS_ROOT.exists():
        return 0
    return sum(1 for _ in CORPUS_ROOT.rglob("*.pdf"))


def count_by_source() -> dict:
    """Count PDFs by source directory."""
    counts = {}
    if not CORPUS_ROOT.exists():
        return counts
    for subdir in CORPUS_ROOT.iterdir():
        if subdir.is_dir():
            count = sum(1 for _ in subdir.rglob("*.pdf"))
            if count > 0:
                counts[subdir.name] = count
    return counts


def is_process_running(name: str) -> bool:
    """Check if a process is running."""
    result = subprocess.run(["pgrep", "-f", name], capture_output=True)
    return result.returncode == 0


def get_download_progress() -> Optional[dict]:
    """Parse download log for current progress."""
    log_file = Path("/tmp/dl_all.log")
    if not log_file.exists():
        return None
    try:
        lines = log_file.read_text().strip().split("\n")[-10:]
        for line in reversed(lines):
            if "Progress:" in line:
                match = re.search(r"Progress: (\d+)/(\d+) \((\d+) downloaded\)", line)
                if match:
                    return {
                        "current": int(match.group(1)),
                        "source_total": int(match.group(2)),
                        "downloaded": int(match.group(3)),
                    }
            # Check for source header
            if "Downloading from" in line:
                match = re.search(r"Downloading from (\w+)", line)
                if match:
                    return {"source": match.group(1), "current": 0, "source_total": 0}
    except Exception:
        pass
    return None


def update_task_monitor_state(total: int, progress: Optional[dict]):
    """Update task-monitor compatible state file."""
    elapsed = time.time() - state.get("start_time", time.time())
    rate = total / elapsed * 3600 if elapsed > 0 else 0  # PDFs per hour

    eta_hours = (TARGET_PDFS - total) / rate if rate > 0 else 0

    batch_state = {
        "name": "corpus-builder",
        "total": TARGET_PDFS,
        "completed": total,
        "failed": 0,
        "rate": f"{rate:.0f}/hr",
        "eta": f"{eta_hours:.1f}h",
        "current_item": progress.get("source", "unknown") if progress else "unknown",
        "updated_at": datetime.now().isoformat(),
        "details": {
            "source_progress": f"{progress['current']}/{progress['source_total']}" if progress else "N/A",
            "downloaded_this_source": progress.get("downloaded", 0) if progress else 0,
        }
    }

    BATCH_STATE_FILE.write_text(json.dumps(batch_state, indent=2))


def restart_downloads():
    """Restart corpus builder if stopped."""
    print(f"[{datetime.now():%H:%M:%S}] Restarting corpus builder...")
    subprocess.Popen(
        [sys.executable, "scripts/corpus_builder.py", "download", "--source", "all", "--count", "4000"],
        cwd="/home/graham/workspace/experiments/extractor",
        stdout=open("/tmp/dl_all.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


# Global state
state = {}


def load_state():
    """Load watchdog state."""
    global state
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            state = {}
    if "start_time" not in state:
        state["start_time"] = time.time()
    if "last_count" not in state:
        state["last_count"] = 0
    if "last_progress_time" not in state:
        state["last_progress_time"] = time.time()
    return state


def save_state():
    """Save watchdog state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


@app.command()
def start():
    """Start the watchdog loop."""
    load_state()

    print("=" * 60)
    print(f"Corpus Watchdog Starting")
    print(f"Target: {TARGET_PDFS} PDFs | Check interval: {CHECK_INTERVAL}s")
    print("=" * 60)

    while True:
        try:
            # Count PDFs
            total = count_pdfs()
            progress = get_download_progress()

            # Check for new progress
            if total > state["last_count"]:
                gained = total - state["last_count"]
                state["last_count"] = total
                state["last_progress_time"] = time.time()
                print(f"\n[{datetime.now():%H:%M:%S}] +{gained} PDFs → {total}/{TARGET_PDFS} ({total*100//TARGET_PDFS}%)")

            # Check for stall
            stall_time = time.time() - state["last_progress_time"]
            if stall_time > STALL_THRESHOLD:
                print(f"\n[{datetime.now():%H:%M:%S}] ⚠️ STALL: {stall_time:.0f}s without progress")

                # Auto-restart if downloads stopped
                if not is_process_running("corpus_builder.py") and total < TARGET_PDFS:
                    restart_downloads()
                    state["last_progress_time"] = time.time()

            # Update task-monitor state
            update_task_monitor_state(total, progress)
            save_state()

            # Check if done
            if total >= TARGET_PDFS:
                print(f"\n🎉 TARGET REACHED: {total} PDFs")
                break

            # Status line
            dl_status = "🟢" if is_process_running("corpus_builder.py") else "🔴"
            src = progress.get("source", "?") if progress else "?"
            src_prog = f"{progress['current']}/{progress['source_total']}" if progress and progress.get('source_total') else "?"

            print(f"\r{dl_status} {total}/{TARGET_PDFS} ({total*100//TARGET_PDFS}%) | Source: {src} {src_prog}", end="", flush=True)

        except KeyboardInterrupt:
            print("\nWatchdog stopped")
            break
        except Exception as e:
            print(f"\nError: {e}")

        time.sleep(CHECK_INTERVAL)


@app.command()
def status():
    """Show current status."""
    total = count_pdfs()
    by_source = count_by_source()
    progress = get_download_progress()

    dl_running = is_process_running("corpus_builder.py")
    learn_running = is_process_running("continuous_learning")
    watch_running = is_process_running("corpus_watchdog.py start")

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    CORPUS WATCHDOG STATUS                     ║
╠══════════════════════════════════════════════════════════════╣
║  PDFs:      {total:,} / {TARGET_PDFS:,} ({total*100//TARGET_PDFS}%)
║  Gap:       {TARGET_PDFS - total:,} remaining
╠══════════════════════════════════════════════════════════════╣
║  Downloads: {'🟢 RUNNING' if dl_running else '🔴 STOPPED'}
║  Learning:  {'🟢 RUNNING' if learn_running else '🔴 STOPPED'}
║  Watchdog:  {'🟢 RUNNING' if watch_running else '🔴 STOPPED'}
╠══════════════════════════════════════════════════════════════╣
║  By Source:                                                   """)
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1])[:8]:
        print(f"║    {src:15} {cnt:,}")
    print("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    app()
