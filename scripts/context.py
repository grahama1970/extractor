#!/usr/bin/env python3
"""Generate CONTEXT.md via headless Codex invocation.

This script gathers the current git snapshot, auto-selects the Codex session
associated with the repo (by scanning ~/.codex/sessions for transcripts that
mention the repo root), and writes CONTEXT.md in the repo root using a single
Codex CLI call. The session id is used for metadata only; newer Codex CLIs no
longer accept a --session flag.

Usage:
    scripts/context.py [--session SESSION_ID]

Environment variables:
    CODEX_CLI        CLI executable to invoke (default: "codex").
    CODEX_HOME       Base directory for Codex data (default: "$HOME/.codex").
    CODEX_SESSION_ID Overrides auto-discovered session ID (metadata only).
    CODEX_CONTEXT_TIMEOUT_SECONDS  Timeout for codex exec (default: 300; 0 disables).
    CODEX_CONTEXT_LOG_DIR          Directory for codex exec logs (default: "<repo>/logs").
    CODEX_CONTEXT_DISABLE          Skip context generation when set (1/true/yes).
"""

from __future__ import annotations

import argparse
import os
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def run_git(*args: str, check: bool = True) -> str:
    """Run a git command and return stdout stripped."""
    result = subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_object_exists(ref: str) -> bool:
    """Check if a Git object exists for the given reference."""
    try:
        run_git("rev-parse", ref, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def discover_session(repo_root: str, requested: Optional[str]) -> str:
    """Discover the active session from environment or default configuration."""
    if requested:
        return requested

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.is_dir():
        return "default"

    def latest(path_list: list[Path]) -> Optional[Path]:
        """Return the most recently modified path from a list."""
        return max(path_list, key=lambda p: p.stat().st_mtime) if path_list else None

    candidates = []
    for session_file in sessions_dir.glob("*.json"):
        try:
            if repo_root in session_file.read_text(errors="ignore"):
                candidates.append(session_file)
        except OSError:
            continue

    chosen = latest(candidates) or latest(list(sessions_dir.glob("*.json")))
    return chosen.stem if chosen else "default"


def gather_git_snapshot() -> dict[str, str]:
    """Gather current Git repository snapshot details."""
    repo_root = run_git("rev-parse", "--show-toplevel")
    branch = run_git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    status = run_git("status", "--short")
    commits = run_git("log", "-5", "--oneline") or "no commits"

    if git_object_exists("HEAD~3"):
        diff_stat = run_git("diff", "--stat", "HEAD~3..HEAD")
    elif git_object_exists("HEAD~1"):
        diff_stat = run_git("diff", "--stat", "HEAD~1..HEAD")
    else:
        diff_stat = run_git("diff", "--stat")

    return {
        "repo_root": repo_root,
        "branch": branch,
        "status": status or "(clean)",
        "commits": commits,
        "diff": diff_stat or "(no recent diff)",
    }


def build_prompt(snapshot: dict[str, str], session_id: str) -> str:
    """Build a formatted prompt string using a git snapshot and session ID."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""You are my coding-session scribe.

Use only the git snapshot provided below to generate CONTEXT.md at the repo root.
The response must be markdown (no fenced code wrapper), under ~150 lines, with
this structure:

# CONTEXT — <short project name or focus>

_Last updated: {timestamp} · Branch: {snapshot['branch']} · Session: {session_id}_

## 1. Active goal
- Infer the current objective from commits and diffs.

## 2. Repo / branch
- Repo root: {snapshot['repo_root']}
- Branch: {snapshot['branch']}

## 3. Recent work
- Summaries of notable changes/files from status/log/diff.

## 4. TODO (next 60–90 minutes)
- [ ] 3–6 concrete tasks derived from the snapshot.

## 5. Commands to re-run
```bash
# List 2–6 useful commands (tests, builds, scripts, etc.).
```

## 6. How to restart this thread
- Provide one short “next prompt” I can use to resume this session.

---

[git status --short]
{snapshot['status']}

[git log -5 --oneline]
{snapshot['commits']}

[git diff --stat]
{snapshot['diff']}
"""


def tail_file(path: Path, max_lines: int = 80) -> str:
    """Return last lines from file path, up to max_lines, or empty string on error."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            tail = deque(handle, maxlen=max_lines)
        return "".join(tail).rstrip()
    except OSError:
        return ""


def call_codex(prompt: str, session_id: str, output_path: Path) -> None:
    """Execute Codex CLI with prompt and session ID, saving output to specified path."""
    codex_cli = os.environ.get("CODEX_CLI", "codex")
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = Path(os.environ.get("CODEX_CONTEXT_LOG_DIR", out_dir / "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = out_dir / f".context_{session_id}.md"
    log_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"context_codex_{session_id}_{log_stamp}.log"
    timeout_s = int(os.environ.get("CODEX_CONTEXT_TIMEOUT_SECONDS", "300"))
    cmd = [
        codex_cli,
        "exec",
        "--sandbox",
        "read-only",
        "--output-last-message",
        str(tmp_path),
    ]
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"started_at={datetime.now(timezone.utc).isoformat()}\n")
        log_file.write(f"cmd={' '.join(cmd)}\n")
        log_file.write(f"timeout_seconds={timeout_s}\n")
        log_file.flush()
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=log_file,
            text=True,
        )
        try:
            proc.communicate(input=prompt, timeout=timeout_s if timeout_s > 0 else None)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(f"Codex CLI timed out after {timeout_s}s. Log: {log_path}")
    if proc.returncode != 0:
        tail = tail_file(log_path)
        msg = f"Codex CLI failed (exit {proc.returncode}). Log: {log_path}"
        if tail:
            msg = f"{msg}\n--- log tail ---\n{tail}"
        raise RuntimeError(msg)
    if not tmp_path.exists():
        raise RuntimeError(
            f"Codex CLI did not produce output (missing output file). Log: {log_path}"
        )
    output_path.write_text(tmp_path.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        tmp_path.unlink()
    except OSError:
        pass


def main() -> None:
    """Generate CONTEXT.md via Codex CLI."""
    if os.environ.get("CODEX_CONTEXT_DISABLE", "").lower() in {"1", "true", "yes", "y"}:
        print("Skipping CONTEXT.md generation (CODEX_CONTEXT_DISABLE=1).")
        return
    parser = argparse.ArgumentParser(description="Generate CONTEXT.md via Codex CLI")
    parser.add_argument("--session", dest="session", help="Override session id", default=None)
    args = parser.parse_args()

    snapshot = gather_git_snapshot()
    requested_session = args.session or os.environ.get("CODEX_SESSION_ID")
    session_id = discover_session(snapshot["repo_root"], requested_session)

    prompt = build_prompt(snapshot, session_id)
    output_path = Path(snapshot["repo_root"]) / "CONTEXT.md"
    call_codex(prompt, session_id, output_path)
    print(f"Wrote CONTEXT.md using session {session_id}")


if __name__ == "__main__":
    main()
