#!/usr/bin/env bash
set -euo pipefail
DB="${DB:-lean4_prod}"
HINTS="${HINTS:-}"
FLAT10="${FLAT10:-}"
: "${ARANGODB_URL:?Set ARANGODB_URL}"
: "${ARANGODB_USERNAME:?Set ARANGODB_USERNAME}"
: "${ARANGODB_PASSWORD:?Set ARANGODB_PASSWORD}"

log_dir=${LOG_DIR:-aql_out}
mkdir -p "$log_dir"

make arango-bootstrap DB="$DB"
if [[ -n "$HINTS" ]]; then
  make graph-oneclick DB="$DB" HINTS="$HINTS"
elif [[ -n "$FLAT10" ]]; then
  make graph-oneclick DB="$DB" FLAT10="$FLAT10"
else
  echo "Provide HINTS=edge_hints.json or FLAT10=flat10.json" >&2
  exit 2
fi
make graph-metrics DB="$DB" | tee "$log_dir/metrics_$(date +%F).json"
