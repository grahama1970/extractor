#!/usr/bin/env bash
set -euo pipefail

# Run Task 1 then Task 2 using the contract loop.
# Stops immediately on FAIL or CLARIFY.
#
# Writes a durable status file a supervising process (human, CI, or "main agent")
# can read:
#   .run_all_status.json
#
# Exit codes:
#   0 = all tasks PASS
#   1 = at least one task FAIL (after retries)
#   2 = harness/env error
#   3 = clarification requested (stopped)
#
# You can override retries and tail lines via environment:
#   RETRIES=3 TAIL_LINES=200 ./run_all.sh
#
# You can override status file paths:
#   RUN_ALL_STATUS_FILE=.run_all_status.json STATUS_FILE=.loop_status.json ./run_all.sh

RETRIES="${RETRIES:-3}"
RUN_ALL_STATUS_FILE="${RUN_ALL_STATUS_FILE:-.run_all_status.json}"

TASKS=(
  "./verify_task1.sh"
  "./verify_task2.sh"
)

now_iso() {
  python3 - <<'PY'
import datetime
print(datetime.datetime.now(datetime.timezone.utc).isoformat())
PY
}

write_run_all_status() {
  python3 - <<PY
import json, os
status_path = os.environ.get("RUN_ALL_STATUS_FILE", ".run_all_status.json")
data = json.loads(os.environ["RUN_ALL_STATUS_JSON"])
with open(status_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
PY
}

# Initialize status
RUN_ALL_STATUS_JSON="$(python3 - <<PY
import json, os
tasks = ${TASKS[@]@Q}
print(json.dumps({
  "status": "RUNNING",
  "started_at": os.environ.get("STARTED_AT"),
  "finished_at": None,
  "retries": int(os.environ.get("RETRIES", "3")),
  "tasks": []
}))
PY
)"
export RUN_ALL_STATUS_JSON
export RUN_ALL_STATUS_FILE
export STARTED_AT="$(now_iso)"
export RETRIES

# rewrite with started_at set
RUN_ALL_STATUS_JSON="$(python3 - <<'PY'
import json, os
p = os.environ["RUN_ALL_STATUS_JSON"]
d = json.loads(p)
d["started_at"] = os.environ.get("STARTED_AT")
print(json.dumps(d))
PY
)"
export RUN_ALL_STATUS_JSON
write_run_all_status

overall_exit=0

for verify in "${TASKS[@]}"; do
  echo "== run_all: $verify =="

  # Run loop for this verifier
  set +e
  ./loop.sh --verify "$verify" --retries "$RETRIES"
  rc=$?
  set -e

  # Read per-task loop status
  loop_status_path="${STATUS_FILE:-.loop_status.json}"
  loop_status="$(cat "$loop_status_path" 2>/dev/null || echo '{}')"

  # Append to run_all status
  RUN_ALL_STATUS_JSON="$(python3 - <<'PY'
import json, os, sys
run_all = json.loads(os.environ["RUN_ALL_STATUS_JSON"])
loop_status = json.loads(os.environ.get("LOOP_STATUS_JSON", "{}"))
verify = os.environ["VERIFY_PATH"]
rc = int(os.environ["RC"])
entry = {
  "verify": verify,
  "rc": rc,
  "loop_status": loop_status,
}
run_all["tasks"].append(entry)
print(json.dumps(run_all))
PY
)"
  export RUN_ALL_STATUS_JSON
  export LOOP_STATUS_JSON="$loop_status"
  export VERIFY_PATH="$verify"
  export RC="$rc"
  write_run_all_status

  if [[ "$rc" -ne 0 ]]; then
    overall_exit="$rc"
    break
  fi
done

export FINISHED_AT="$(now_iso)"

# Finalize status
RUN_ALL_STATUS_JSON="$(python3 - <<'PY'
import json, os
d = json.loads(os.environ["RUN_ALL_STATUS_JSON"])
d["finished_at"] = os.environ.get("FINISHED_AT")
# Determine overall status
tasks = d.get("tasks", [])
if not tasks:
    d["status"] = "FAIL"
else:
    last_rc = tasks[-1]["rc"]
    if last_rc == 0 and all(t["rc"] == 0 for t in tasks):
        d["status"] = "PASS"
    elif last_rc == 3:
        d["status"] = "CLARIFY"
    elif last_rc == 2:
        d["status"] = "ERROR"
    else:
        d["status"] = "FAIL"
print(json.dumps(d))
PY
)"
export RUN_ALL_STATUS_JSON
write_run_all_status

# Print summary hint
echo ""
echo "run_all finished with rc=$overall_exit"
echo "Status file: $RUN_ALL_STATUS_FILE"
echo "Last loop status: ${STATUS_FILE:-.loop_status.json}"

echo "RUN_ALL_STATUS=$(python3 -c 'import json; print(json.load(open(\"$RUN_ALL_STATUS_FILE\")).get(\"status\", \"UNKNOWN\"))')"
echo "RUN_ALL_RC=$overall_exit"
exit "$overall_exit"
