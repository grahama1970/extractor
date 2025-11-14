#!/usr/bin/env bash
#
# Update CONTEXT.md by combining recent git state with a headless Codex call.
#
# Usage:
#   scripts/update_context_headless.sh [SESSION_ID]
#
# Env:
#   CODEX_CLI   Optional, defaults to "codex". Set to whatever CLI you use.
#               e.g., CODEX_CLI="codex-cli" or similar.
#
# Notes:
#   - Must be run inside a git repo.
#   - Writes CONTEXT.md at the repo root.
#   - You may need to adjust the CLI flags (-p, --output-format, --session)
#     to match your actual Codex/OpenAI/LLM wrapper.

set -euo pipefail

SESSION_ID="${1:-default}"
CODEX_CLI="${CODEX_CLI:-codex}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not inside a git repository." >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
STATUS="$(git status --short 2>/dev/null || true)"
RECENT_COMMITS="$(git log -5 --oneline 2>/dev/null || echo "no commits")"

# Try a small window of commits for diff; fall back if history is shallow.
if git rev-parse HEAD~3 >/dev/null 2>&1; then
  DIFF_STAT="$(git diff --stat HEAD~3..HEAD 2>/dev/null || true)"
elif git rev-parse HEAD~1 >/dev/null 2>&1; then
  DIFF_STAT="$(git diff --stat HEAD~1..HEAD 2>/dev/null || true)"
else
  DIFF_STAT="$(git diff --stat 2>/dev/null || true)"
fi

PROMPT_FILE="$(mktemp "${TMPDIR:-/tmp}/codex_prompt.XXXXXX")"

cat >"$PROMPT_FILE" <<EOF_INNER
You are my coding-session scribe.

Using ONLY the git snapshot and information below, generate a single markdown
document that will be written to CONTEXT.md in the project root. Keep it under
~150 lines. Do not include any explanations outside the markdown; the entire
response must be valid markdown starting at the first line.

Follow this structure exactly:

# CONTEXT — <short project name or focus>

_Last updated: $(date -Iseconds) · Branch: $BRANCH_

## 1. Active goal
- In 1–3 bullets, infer what I'm currently trying to do in this repo based on
  commit messages and the diff summary.

## 2. Repos / branches
- Repo root: $REPO_ROOT
- Branch: $BRANCH

## 3. Recent work
- Summarize the main changes indicated by the recent commits and diff summary.
- Mention any files or directories that appear central to the recent work.

## 4. TODO (next 60–90 minutes)
- [ ] 3–6 concrete, executable next actions derived from the snapshot.
- [ ] Prefer specific tasks (e.g., "add tests for X", "wire Y into Z") over
      vague ones.

## 5. Commands to re-run
```bash
# Fill in 2–6 commands that are likely useful to rerun:
# (e.g., pytest ..., make ..., uv run ..., docker compose ..., etc.)
```

## 6. How to restart this thread
- Suggest one short “next prompt” that I can paste into a fresh session so the
  assistant can pick up from this CONTEXT.md.

---

Git snapshot for you to base this on:

[git status --short]
$STATUS

[git log -5 --oneline]
$RECENT_COMMITS

[git diff --stat (recent changes)]
$DIFF_STAT
EOF_INNER

# NOTE: Adjust these flags to match your actual CLI.
# Many CLIs use: -p / --prompt and --output-format markdown
# and support a --session or similar for conversation continuity.
"$CODEX_CLI" \
  --session "$SESSION_ID" \
  -p "$(cat "$PROMPT_FILE")" \
  --output-format markdown \
  > "$REPO_ROOT/CONTEXT.md"

echo "Wrote CONTEXT.md in $REPO_ROOT"

rm -f "$PROMPT_FILE"
