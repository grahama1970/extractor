.PHONY: healthcheck verify-env pipeline-health dev-backend dev-web dev-proto dev-all lint format test typecheck

# Verify full network access, no filesystem sandbox, and ArangoDB connectivity
healthcheck: verify-env

verify-env:
	bash scripts/verify_environment.sh

# Run full pipeline CLI verification (real network + Arango)
pipeline-health:
	bash scripts/verify_pipeline_cli.sh

# ----------------------
# Developer convenience
# ----------------------

dev-backend:
	. .venv/bin/activate && set -a && [ -f .env ] && . .env && set +a && \
	python -m extractor.core.scripts.server --host 127.0.0.1 --port 8000

dev-web:
	cd tools/gold_annotator_web && npm install && \
	NEXT_PUBLIC_API_PROXY=$${NEXT_PUBLIC_API_PROXY:-http://localhost:8000} npm run dev

dev-proto:
	cd prototypes/tabbed/html && npm install && \
	VITE_API_PROXY=$${VITE_API_PROXY:-http://localhost:8000} npm run dev

# Run backend + Next.js together (press Ctrl+C to stop)
dev-all:
	@echo "Starting backend (8000) and Next.js (app dev) ..."; \
	( \
	  (. .venv/bin/activate && set -a && [ -f .env ] && . .env && set +a && \
	   python -m extractor.core.scripts.server --host 127.0.0.1 --port 8000) & \
	); \
	BACKEND_PID=$$!; \
	( cd tools/gold_annotator_web && npm install && NEXT_PUBLIC_API_PROXY=$${NEXT_PUBLIC_API_PROXY:-http://localhost:8000} npm run dev ) & \
	WEB_PID=$$!; \
	trap 'kill $$BACKEND_PID $$WEB_PID 2>/dev/null || true' INT TERM; \
	wait

lint:
	. .venv/bin/activate && ruff check src/extractor tests

format:
	. .venv/bin/activate && black src tests scripts

test:
	. .venv/bin/activate && pytest -q

typecheck:
	. .venv/bin/activate && mypy src/extractor/core
