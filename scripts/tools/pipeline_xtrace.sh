#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# pipeline_xtrace.sh
# Array-safe runner that captures per-stage stdout/stderr and emits a JSON summary.
# Usage:
#   scripts/tools/pipeline_xtrace.sh OUT_DIR label1 cmd1 arg... :: label2 cmd2 arg... ::
# Example:
#   scripts/tools/pipeline_xtrace.sh data/results/xtrace \
#     "01_annotations" python -m extractor.pipeline.steps.01_annotation_processor run "file.pdf" -o out :: \
#     "07_reflow" python -m extractor.pipeline.steps.07_reflow_section run --sections s.json -o out ::
#
# Notes:
# - Use :: as the delimiter between stages.
# - Each stage is defined by: LABEL CMD ARGS...
# - Produces:
#     OUT_DIR/xtrace_<timestamp>/summary.json
#     OUT_DIR/xtrace_<timestamp>/<NN_LABEL>/{stage.out,stage.err,exit_code}

out_root="${1:-}"
if [[ -z "${out_root}" ]]; then
  echo "usage: $0 OUT_DIR label cmd args... :: label cmd args... ::" >&2
  exit 2
fi
shift

ts="$(date +%Y%m%d_%H%M%S)"
run_dir="${out_root%/}/xtrace_${ts}"
mkdir -p "${run_dir}"

stages_json="[]"
stage_index=0
FAIL_FAST=${FAIL_FAST:-0}
STOP=0

append_stage_json() {
  local label="$1"
  local start_s="$2"
  local end_s="$3"
  local exit_code="$4"
  local dir="$5"
  python - "$stages_json" "$label" "$start_s" "$end_s" "$exit_code" "$dir" <<'PY' >"${run_dir}/.tmp_stages.json"
import json,sys
arr=json.loads(sys.argv[1])
label=sys.argv[2]; start_s=int(sys.argv[3]); end_s=int(sys.argv[4]); code=int(sys.argv[5]); d=sys.argv[6]
arr.append({
  "label": label,
  "start_s": start_s,
  "end_s": end_s,
  "duration_ms": (end_s-start_s)*1000,
  "exit_code": code,
  "dir": d,
})
print(json.dumps(arr, ensure_ascii=False, indent=2))
PY
  stages_json="$(cat "${run_dir}/.tmp_stages.json")"
  rm -f "${run_dir}/.tmp_stages.json"
}

run_one_stage() {
  local label="$1"; shift
  stage_index=$((stage_index+1))
  local idx
  printf -v idx "%02d" "${stage_index}"
  local sdir="${run_dir}/${idx}_$(echo "${label}" | tr ' /' '__')"
  mkdir -p "${sdir}"

  local start_s end_s code
  start_s="$(date +%s)"
  if ("$@" >"${sdir}/stage.out" 2>"${sdir}/stage.err"); then
    code=0
  else
    code=$?
  fi
  echo -n "${code}" >"${sdir}/exit_code"
  end_s="$(date +%s)"
  append_stage_json "${label}" "${start_s}" "${end_s}" "${code}" "${sdir}"
  if [[ "$FAIL_FAST" == "1" && $code -ne 0 ]]; then
    STOP=1
  fi
  return "${code}"
}

# Parse arguments into stages using :: delimiter
current_label=""
current_cmd=()

flush_stage_if_any() {
  if [[ -n "${current_label}" && ${#current_cmd[@]} -gt 0 ]]; then
    if [[ "$STOP" != "1" ]]; then
      run_one_stage "${current_label}" "${current_cmd[@]}" || true
    fi
    current_label=""
    current_cmd=()
  fi
}

while (($#)); do
  tok="$1"; shift
  if [[ "${tok}" == "::" ]]; then
    flush_stage_if_any
    continue
  fi
  if [[ -z "${current_label}" ]]; then
    current_label="${tok}"
  else
    current_cmd+=("${tok}")
  fi
done
flush_stage_if_any

XT_STAGES="${stages_json}" XT_RUN_DIR="${run_dir}" \
  python - <<'PY' >"${run_dir}/summary.json"
import json,os
stages=json.loads(os.environ["XT_STAGES"]) if os.environ.get("XT_STAGES") else []
overall=0 if all(e.get("exit_code",0)==0 for e in stages) else 1
print(json.dumps({"run_dir": os.environ.get("XT_RUN_DIR",""), "stages": stages, "overall_exit_code": overall}, ensure_ascii=False, indent=2))
PY

echo "summary: ${run_dir}/summary.json"
exit 0
