#!/usr/bin/env bash
set -euo pipefail

# loop.sh - Retry loop for a single verify script
#
# Features (from pi-coordination):
# - Worker self-review before marking step complete
# - Context files for smarter recovery on retry
# - Structured artifacts per attempt
#
# Usage:
#   ./loop.sh --verify ./verify_s05.sh
#   ./loop.sh --verify ./verify_s05.sh --retries 5
#   AGENT=claude ./loop.sh --verify ./verify_s05.sh

VERIFY="./verify_s01.sh"
RETRIES="${RETRIES:-3}"
TAIL_LINES="${TAIL_LINES:-160}"
LOG="verify.log"
STATUS_FILE="${STATUS_FILE:-.loop_status.json}"
AGENT="${AGENT:-claude}"  # claude, codex, gemini
SELF_REVIEW="${SELF_REVIEW:-true}"  # Enable worker self-review
MAX_SELF_REVIEW_CYCLES="${MAX_SELF_REVIEW_CYCLES:-3}"

CLARIFY_CODE=42
EXIT_CLARIFY=3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Artifacts directory for structured output
ARTIFACTS_DIR="./artifacts"
mkdir -p "$ARTIFACTS_DIR"

usage() {
  cat <<EOF
usage: ./loop.sh [--verify PATH] [--retries N] [--agent NAME] [--no-self-review]

Options:
  --verify           Path to verifier script (default: ./verify_s01.sh)
  --retries          Max retries (default: 3)
  --agent            Agent to use: codex, claude, gemini (default: claude)
  --no-self-review   Disable self-review before completion

Env:
  TAIL_LINES   Number of log lines fed back to agent (default: 160)
  STATUS_FILE  Status JSON path (default: .loop_status.json)
  AGENT        Agent to use (default: claude)
  SELF_REVIEW  Enable worker self-review (default: true)
EOF
}

# Get step name from verify script path
get_step_name() {
  local verify="$1"
  basename "$verify" .sh | sed 's/verify_//'
}

# Write structured artifact for this attempt
write_artifact() {
  local step="$1"
  local attempt="$2"
  local input="$3"
  local output="$4"
  local status="$5"
  local timestamp
  timestamp="$(date -Iseconds)"
  
  local artifact_dir="$ARTIFACTS_DIR/${step}"
  mkdir -p "$artifact_dir"
  
  # Input prompt
  echo "$input" > "$artifact_dir/attempt-${attempt}_input.md"
  
  # Output (if any)
  if [[ -n "$output" ]]; then
    echo "$output" > "$artifact_dir/attempt-${attempt}_output.md"
  fi
  
  # Meta JSON
  cat > "$artifact_dir/attempt-${attempt}_meta.json" <<JSON
{
  "step": "$step",
  "attempt": $attempt,
  "timestamp": "$timestamp",
  "status": "$status",
  "agent": "$AGENT",
  "verify_script": "$VERIFY"
}
JSON
}

# Write/update context.md for recovery
write_context() {
  local step="$1"
  local attempt="$2"
  local status="$3"
  local fail_reason="$4"
  
  local context_file="$ARTIFACTS_DIR/${step}/context.md"
  mkdir -p "$(dirname "$context_file")"
  
  cat > "$context_file" <<MD
# Context for $step

## Current Status
- Status: $status
- Attempts: $attempt
- Last attempt: $(date -Iseconds)

## What Was Attempted
$(tail -n 50 "$LOG" 2>/dev/null || echo "No log available")

## Failure Reason
$fail_reason

## Continuation Notes
If retrying, do NOT redo work already completed. Focus on fixing the specific failure.
MD
}

# Read context for smart retry
read_context() {
  local step="$1"
  local context_file="$ARTIFACTS_DIR/${step}/context.md"
  
  if [[ -f "$context_file" ]]; then
    cat "$context_file"
  else
    echo "No previous context available."
  fi
}

write_status() {
  local status="$1"
  local exit_code="$2"
  local attempts="$3"
  local clarify_json="$4"
  cat > "$STATUS_FILE" <<JSON
{
  "status": "$status",
  "exit_code": $exit_code,
  "verify": "$VERIFY",
  "agent": "$AGENT",
  "attempts_used": $attempts,
  "log_path": "$LOG",
  "artifacts_dir": "$ARTIFACTS_DIR/$(get_step_name "$VERIFY")",
  "clarify_lines": $clarify_json
}
JSON
}

run_agent() {
  local prompt="$1"
  local agent_log="agent_run.log"
  
  case "$AGENT" in
    codex)
      codex exec --full-auto "$prompt" 2>&1 | tee "$agent_log" || true
      ;;
    claude)
      # Claude headless call with JSON output and logging
      claude --dangerously-skip-permissions --output-format json -p "$prompt" 2>&1 | tee "$agent_log" || true
      ;;
    gemini)
      # Placeholder for gemini CLI
      echo "WARN: gemini agent not yet implemented" >&2
      ;;
    *)
      echo "ERROR: unknown agent: $AGENT" >&2
      return 1
      ;;
  esac
}

# Self-review: agent reviews its own work before marking complete
run_self_review() {
  local step="$1"
  echo "🔍 Running self-review for $step..."
  
  local review_prompt="
You just made changes to fix $VERIFY. Before marking complete, review with fresh eyes:

1. Did you make the minimal change needed?
2. Are there any obvious issues or regressions?
3. Does the fix address the root cause?

If no issues found, respond with: 'No issues found.'
If issues found, fix them now.

Recent changes:
$(git diff --stat 2>/dev/null || echo "No git diff available")
"
  
  for cycle in $(seq 1 "$MAX_SELF_REVIEW_CYCLES"); do
    echo "Self-review cycle $cycle/$MAX_SELF_REVIEW_CYCLES"
    
    local review_output
    review_output=$(run_agent "$review_prompt" 2>&1)
    
    if echo "$review_output" | grep -qi "no issues found"; then
      echo "✅ Self-review passed"
      return 0
    fi
    
    echo "⚠️ Self-review found issues, agent is fixing..."
  done
  
  echo "⚠️ Max self-review cycles reached, proceeding anyway"
  return 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify) VERIFY="$2"; shift 2;;
    --retries) RETRIES="$2"; shift 2;;
    --agent) AGENT="$2"; shift 2;;
    --no-self-review) SELF_REVIEW="false"; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown arg: $1" >&2; usage; exit 2;;
  esac
done

STEP_NAME="$(get_step_name "$VERIFY")"

# Check agent CLI is available
case "$AGENT" in
  codex)
    if ! command -v codex >/dev/null 2>&1; then
      echo "ERROR: codex CLI not found. Install/auth codex, or use --agent claude" >&2
      write_status "ERROR" 2 0 "[]"
      exit 2
    fi
    ;;
  claude)
    if ! command -v claude >/dev/null 2>&1; then
      echo "ERROR: claude CLI not found. Install claude CLI or use --agent codex" >&2
      write_status "ERROR" 2 0 "[]"
      exit 2
    fi
    ;;
esac

attempt=0
for i in $(seq 1 "$RETRIES"); do
  attempt="$i"
  echo "== verify attempt $i/$RETRIES (agent: $AGENT, step: $STEP_NAME) =="

  set +e
  bash -lc "$VERIFY" 2>&1 | tee "$LOG"
  rc="${PIPESTATUS[0]}"
  set -e

  if [[ "$rc" -eq 0 ]]; then
    # Gate passed - run self-review before marking complete
    if [[ "$SELF_REVIEW" == "true" ]]; then
      run_self_review "$STEP_NAME"
    fi
    
    echo "✅ PASS: gate satisfied"
    echo "LOOP_STATUS=PASS"
    write_artifact "$STEP_NAME" "$attempt" "" "$(cat "$LOG")" "PASS"
    write_status "PASS" 0 "$attempt" "[]"
    exit 0
  fi

  if [[ "$rc" -eq "$CLARIFY_CODE" ]]; then
    echo "🛑 Clarification requested. Stopping."
    echo "LOOP_STATUS=CLARIFY"
    mapfile -t lines < <(grep '^CLARIFY:' "$LOG" || true)
    printf '%s\n' "${lines[@]}" || true

    # JSON encode clarify lines
    clarify_json="[]"
    if [[ "${#lines[@]}" -gt 0 ]]; then
      clarify_json="["
      first=1
      for l in "${lines[@]}"; do
        esc="${l//\\/\\\\}"
        esc="${esc//\"/\\\"}"
        esc="${esc//$'\n'/}"
        if [[ "$first" -eq 1 ]]; then
          clarify_json="${clarify_json}\"${esc}\""
          first=0
        else
          clarify_json="${clarify_json}, \"${esc}\""
        fi
      done
      clarify_json="${clarify_json}]"
    fi

    write_artifact "$STEP_NAME" "$attempt" "" "$(cat "$LOG")" "CLARIFY"
    write_context "$STEP_NAME" "$attempt" "CLARIFY" "Clarification requested"
    write_status "CLARIFY" "$EXIT_CLARIFY" "$attempt" "$clarify_json"
    exit "$EXIT_CLARIFY"
  fi

  echo "❌ FAIL (rc=$rc): feeding failure tail into $AGENT"
  FAIL_TAIL="$(tail -n "$TAIL_LINES" "$LOG" || true)"
  
  # Write failure artifact and context
  write_artifact "$STEP_NAME" "$attempt" "Attempt $attempt failed" "$(cat "$LOG")" "FAIL"
  write_context "$STEP_NAME" "$attempt" "FAIL" "$FAIL_TAIL"
  
  # Get previous context for smarter retry
  PREV_CONTEXT="$(read_context "$STEP_NAME")"

  PROMPT="
You are a repo-scoped coding agent.

Goal: make $VERIFY pass.

Rules:
- DO NOT edit verifier scripts (verify_*.sh) or gate scripts (gates/gate_*.py) unless explicitly instructed
- Make minimal, localized changes to the pipeline step code
- The runner will re-run $VERIFY after you finish

## Previous Context (do NOT redo completed work)
$PREV_CONTEXT

## Latest failure tail:
$FAIL_TAIL
"

  write_artifact "$STEP_NAME" "$attempt" "$PROMPT" "" "AGENT_INVOKED"
  run_agent "$PROMPT"

  echo ""
done

echo "🚫 Exhausted $RETRIES retries; gate still failing."
echo "LOOP_STATUS=FAIL"
write_context "$STEP_NAME" "$attempt" "FAIL" "Exhausted $RETRIES retries"
write_status "FAIL" 1 "$attempt" "[]"
exit 1
