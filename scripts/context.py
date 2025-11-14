#!/usr/bin/env python3
"""Generate CONTEXT.md via headless Codex invocation.

This script gathers the current git snapshot, auto-selects the Codex session
associated with the repo (by scanning ~/.codex/sessions for transcripts that
mention the repo root), and writes CONTEXT.md in the repo root using a single
Codex CLI call.

Usage:
    scripts/context.py [--session SESSION_ID]

Environment variables:
    CODEX_CLI        CLI executable to invoke (default: "codex").
    CODEX_HOME       Base directory for Codex data (default: "$HOME/.codex").
    CODEX_SESSION_ID Overrides auto-discovered session ID.
"""

from __future__ import annotations

import argparse
import os
import subprocess
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
    try:
        run_git("rev-parse", ref, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def discover_session(repo_root: str, requested: Optional[str]) -> str:
    if requested:
        return requested

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.is_dir():
        return "default"

    def latest(path_list: list[Path]) -> Optional[Path]:
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


def call_codex(prompt: str, session_id: str, output_path: Path) -> None:
    codex_cli = os.environ.get("CODEX_CLI", "codex")
    result = subprocess.run(
        [codex_cli, "--session", session_id, "-p", prompt, "--output-format", "markdown"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Codex CLI failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    output_path.write_text(result.stdout)


def main() -> None:
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
