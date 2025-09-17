#!/usr/bin/env bash
set -euo pipefail
codex exec -C /home/graham/workspace/experiments/extractor --dangerously-bypass-approvals-and-sandbox - < /home/graham/workspace/experiments/extractor/workspace/runs/20250913-143819/instances/codex_01_mul_shift_add/prompt.md
codex exec -C /home/graham/workspace/experiments/extractor --dangerously-bypass-approvals-and-sandbox - < /home/graham/workspace/experiments/extractor/workspace/runs/20250913-143819/instances/codex_02_mul_karatsuba/prompt.md
codex exec -C /home/graham/workspace/experiments/extractor --dangerously-bypass-approvals-and-sandbox - < /home/graham/workspace/experiments/extractor/workspace/runs/20250913-143819/instances/codex_03_mul_chunked/prompt.md
