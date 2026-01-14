#!/usr/bin/env bash
set -euo pipefail

VERIFY="./verify_task1.sh"
RETRIES=3
TAIL_LINES="${TAIL_LINES:-160}"
LOG="verify.log"
STATUS_FILE="${STATUS_FILE:-.loop_status.json}"

CLARIFY_CODE_FROM_GATES=42
EXIT_CLARIFY_STOP=3

usage() {
  cat <<EOF
usage: ./loop.sh [--verify PATH] [--retries N]

Options:
  --verify   Path to verifier script (default: ./verify_task1.sh)
  --retries  Max retries (default: 3)

Env:
  TAIL_LINES   Number of log lines fed back to the agent (default: 160)
  STATUS_FILE  Status JSON path (default: .loop_status.json)
EOF
}

write_status() {
  local status="$1"
  local exit_code="$2"
  local attempts="$3"
  local clarify_lines_json="$4"
  cat > "$STATUS_FILE" <<JSON
{
  "status": "$status",
  "exit_code": $exit_code,
  "verify": "$VERIFY",
  "attempts_used": $attempts,
  "log_path": "$LOG",
  "clarify_lines": $clarify_lines_json
}
JSON
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify) VERIFY="$2"; shift 2;;
    --retries) RETRIES="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: codex CLI not found on PATH. Install/auth codex, or run $VERIFY manually." >&2
  write_status "FAIL" 2 0 "[]"
  exit 2
fi

attempt=0
for i in $(seq 1 "$RETRIES"); do
  attempt="$i"
  echo "== verify attempt $i/$RETRIES =="

  set +e
  bash -lc "$VERIFY" 2>&1 | tee "$LOG"
  rc="${PIPESTATUS[0]}"
  set -e

  if [[ "$rc" -eq 0 ]]; then
    echo "✅ PASS: contract satisfied"
echo "LOOP_STATUS=PASS"
    write_status "PASS" 0 "$attempt" "[]"
    exit 0
  fi

  if [[ "$rc" -eq "$CLARIFY_CODE_FROM_GATES" ]]; then
    echo "🛑 Clarification requested by contract. Stopping."
echo "LOOP_STATUS=CLARIFY"
    mapfile -t lines < <(grep '^CLARIFY:' "$LOG" || true)
    printf '%s
' "${lines[@]}" || true

    # JSON encode clarify lines minimally
    clarify_json="[]"
    if [[ "${#lines[@]}" -gt 0 ]]; then
      clarify_json="["
      first=1
      for l in "${lines[@]}"; do
        esc="${l//\/\\}"
        esc="${esc//"/\"}"
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

    write_status "CLARIFY" "$EXIT_CLARIFY_STOP" "$attempt" "$clarify_json"
    exit "$EXIT_CLARIFY_STOP"
  fi

  echo "❌ FAIL (rc=$rc): feeding failure tail into a fresh codex exec run"
  FAIL_TAIL="$(tail -n "$TAIL_LINES" "$LOG" || true)"

  codex exec --full-auto "
You are a repo-scoped coding agent.

Goal: make $VERIFY pass.

Rules:
- DO NOT edit verifier scripts (verify_*.sh) or gate scripts unless explicitly instructed
- Make minimal, localized changes
- The runner will re-run $VERIFY after you finish

Latest failure tail:
$FAIL_TAIL
" || true

  echo ""
done

echo "🚫 Exhausted $RETRIES retries; contract still failing."
echo "LOOP_STATUS=FAIL"
write_status "FAIL" 1 "$attempt" "[]"
exit 1
