source .venv/bin/activate && set -a && source .env && set +a STAGE03_TEXT_ONLY=0 \
uv run scripts/smokes/pipeline/smoke_api_external_annotations.py \
--pdf data/input/pipeline/BHT_CV32A65X_reqs.pdf \
--port 8002 \
--mode live