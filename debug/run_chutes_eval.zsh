#!/usr/bin/env zsh
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
INPUT_JSON=${REPO_ROOT}/data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json
PDF_DIR=${REPO_ROOT}/data/results/pipeline/tmp_pdf
OUTPUT_ROOT=${REPO_ROOT}/data/results/pipeline/chutes_eval_openai

LIMIT=${1:-6}
TIMEOUT=${2:-600}
DPI=${3:-150}
CONCURRENCY=${4:-1}

MODELS=(
  "openai/chutes/Qwen2.5-VL-7B-Instruct|Qwen/Qwen2.5-VL-7B-Instruct"
  "openai/chutes/Qwen2.5-VL-14B-Instruct|Qwen/Qwen2.5-VL-14B-Instruct"
  "openai/chutes/Qwen2.5-VL-32B-Instruct|Qwen/Qwen2.5-VL-32B-Instruct"
)

python_bin=${REPO_ROOT}/.venv/bin/python
if [[ ! -x ${python_bin} ]]; then
  echo "Python virtualenv not found at ${python_bin}" >&2
  exit 1
fi

for entry in ${MODELS[@]}; do
  alias_name=${entry%%|*}
  remote_name=${entry##*|}
  slug=${alias_name#openai/chutes/}
  slug=${slug//\//-}
  outdir=${OUTPUT_ROOT}/${slug:l}

  echo "\n=== Evaluating ${alias_name} (remote ${remote_name}) ==="

  rm -rf "${outdir}"

  cmd=(
    "source ${REPO_ROOT}/.venv/bin/activate"
    "set -a; if [ -f '${REPO_ROOT}/.env' ]; then . '${REPO_ROOT}/.env'; fi; set +a"
    "STAGE03_MODEL='${alias_name}' CHUTES_MODEL='${alias_name}' CHUTES_REMOTE_MODEL='${remote_name}' CHUTES_PROVIDER='${CHUTES_PROVIDER:-openai}' python -m extractor.pipeline.steps.03_suspicious_headers run ${INPUT_JSON} --pdf-dir ${PDF_DIR} --limit ${LIMIT} --timeout ${TIMEOUT} --dpi ${DPI} -c ${CONCURRENCY} -o ${outdir}"
  )

  joined=$(printf " && %s" "${cmd[@]}")
  joined=${joined#" && "}

  if ! bash -lc "${joined}"; then
    echo "Run failed for ${alias_name}. See ${outdir}/03_suspicious_headers/stage_03_suspicious_headers.log" >&2
  else
    metrics=${outdir}/03_suspicious_headers/json_output/03_metrics.json
    if [[ -f ${metrics} ]]; then
      echo "Metrics: ${metrics}"
    fi
  fi

done
