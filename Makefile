BASE_URL ?= http://127.0.0.1:8080
CDP_URL  ?= http://127.0.0.1:3000/json/version
PY       ?= .venv/bin/python

# Live scenario runner (mirrors LiteLLM/CodeWorld)
.PHONY: run-scenarios
run-scenarios:
	python scenarios/run_all.py

.PHONY: run-scenarios-ux
run-scenarios-ux:
	SCENARIOS_FILTER=ux_ python scenarios/run_all.py

.PHONY: run-scenarios-pipeline
run-scenarios-pipeline:
	SCENARIOS_FILTER=pipeline_ python scenarios/run_all.py

.PHONY: run-extractor-scenarios
run-extractor-scenarios:
	PYTHONPATH=src python scenarios/extractors/run_all.py

.PHONY: bundle-extractor-artifacts
bundle-extractor-artifacts:
	@echo "Artifacts root: $${SCENARIOS_ARTIFACT_ROOT:-scripts/artifacts}"
	@find $${SCENARIOS_ARTIFACT_ROOT:-scripts/artifacts} -maxdepth 3 -type f \( -name '*.json' -o -name '*.png' \) | sort

.PHONY: pipeline
pipeline:
	python scenarios/pipeline/run_pipeline_all.py

.PHONY: pipeline-smoke
pipeline-smoke:
	SCENARIOS_FILTER=pipeline_api_health,pipeline_step_10_export_flattened,pipeline_step_11_graph_db python scenarios/run_all.py


.PHONY: coco-export smoke-tabbed-api help setup setup-smokes smokes-python dev stop lint fmt type test api-smokes ux-health smokes ci scaffold smoke-issue \
		gamified-e2e gamified-all gamified-all-fast gamified-codex gamified-cli \
		smoke-07-reflow-min bundle-tabbed state-of-project

.PHONY: smoke-parity-gold
smoke-parity-gold:
	PYTHONPATH=src python scripts/smokes/pipeline/smoke_parity_canonical.py \
	  --flat data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json
	python scripts/smokes/pipeline/smoke_parity_clean.py \
	  --pdf-flat data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json \
	  --clean-flat data/input/parity_hand/reflat.json data/input/parity_hand/reflat_docx.json data/input/parity_hand/reflat_md.json data/input/parity_hand/reflat_rst.json data/input/parity_hand/reflat_epub.json \
	  --ignore-ext pptx,xlsx
	@echo "Info report (non-blocking):" && \
	python scripts/smokes/pipeline/smoke_parity_report.py \
	  --refs data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json \
	  --candidates data/input/parity_hand/reflat_pptx.json data/input/parity_hand/reflat_xlsx.json

.PHONY: smoke-parity-xml
smoke-parity-xml:
	PYTHONPATH=src python scripts/smokes/pipeline/smoke_parity_xml.py

.PHONY: smoke-parity-all
smoke-parity-all: smoke-parity-gold smoke-parity-xml

help:
	@echo "Common targets:"
	@echo "  make setup         # create venv + install dev deps (uv if available)"
	@echo "  make dev           # start backend + vite (scripts/dev.sh)"
	@echo "  make stop          # kill 8080/8001"
	@echo "  make lint fmt type test  # fast gates"
	@echo "  make api-smokes    # API-only smokes (no browser)"
	@echo "  make ux-health     # basic UX health gate (CDP)"
	@echo "  make smokes        # full UX smokes (requires live servers + CDP)"
	@echo "  make ci            # local CI gate (server checks + full suite)"
	@echo "  make scaffold ISSUE=007 TITLE=\"label button\"  # scaffold issue + smoke"
	@echo "  make smoke-issue ISSUE=007                        # run that issue smoke"
	@echo "  make run-01-05 PDF=... OUT=...                    # run pipeline steps 01→05 into OUT"
	@echo "  make annotate-from-results OUT=... [TABLES_AS=json|markdown|box] [EXPORT_PAGES=1]  # annotate with sidecars"
	@echo "  make annotate-run-01-05 PDF=... OUT=... [TABLES_AS=json] [EXPORT_PAGES=1]        # run 01→05 then annotate"
	@echo "  make bundle-annotated SLUG=...                    # tar.gz annotated PDF + pages + sidecars"
	@echo "  make gamified-e2e  # run gamified e2e smoke (Codex path, fast)"
	@echo "  make gamified-all  # run all gamified smokes"
	@echo "  make gamified-codex# run Codex exec smoke (requires codex)"
	@echo "  make gamified-cli  # optional CLI-runner for gamified smokes"
	@echo "  make gamified-weblog # Test FastAPI web log server (proto dashboard + ingest)"
	@echo "  make gamified-e2e-web # Start backend on a free port, run Codex, assert /proto/dashboard"
	@echo "  make gamified-ui-smoke # Run Puppeteer smoke against running dashboard (BASE_URL required)"
	@echo "  make lessons-setup   # ensure ArangoDB collections/view for lessons (ARANGO_URL/DB/USER/PASS)"
	@echo "  make lessons-add TITLE=... PROBLEM=... PLAYBOOK=... TAGS=cdp,proxy SCOPE=tabbed"
	@echo "  make lessons-search Q=cdp TAGS=proxy,dev  # BM25 search"
	@echo "  make lessons-recall Q='cdp puppeteer hang' TAGS=cdp SCOPE=tabbed  # agent recall"
	@echo "  make lessons-recall-last  # derive query from latest scripts/artifacts/*.log"
	@echo "  make lessons-seed-demo COUNT=50 SCOPE=tabbed  # seed demo lessons"
	@echo "  make lessons-delete-demo [BATCH=...]          # delete demo lessons (optionally by batch)"
	@echo "  make lessons-status-report                    # generate MD summary from pytest JSON"
	@echo "  make lessons-http-smokes                      # run HTTP-only endpoint tests (server must be running)"
	@echo "  make lessons-recall-diff Q='...' [SCOPE=...] # show BM25 vs Fused side-by-side"
	@echo "  make lessons-delete KEY=...  # or TITLE=... SCOPE=..."
	@echo "  make lessons-link FROM_KEY=... TO_KEY=... RATIONALE='...' WEIGHT=0.7  # or use FROM_TITLE/FROM_SCOPE and TO_TITLE/TO_SCOPE"
	@echo "  make lessons-related KEY=... [DIR=both|out|in]  # list neighbors"
	@echo "  make lessons-multihop KEY=... DEPTH=2 DIR=ANY K=5  # multi-hop traversal with weights"
	@echo "  make setup-smokes   # create lean venv with only smoke/runtime deps"
	@echo "  make smokes-python  # run Python-only smokes with PYTHONPATH=src"
	@echo "  make quick-pipeline # run 01→09 & 14 with gold checks; skip heavy 10–11"
	@echo "  make pipeline-full  # run all stages (01→14) end-to-end (requires keys/DB)"
	@echo "  make ci-live        # self-hosted: run live LLM pipeline + verify (OUT=data/results/pipeline_live)"
	@echo "  make smokes-pipeline-offline  # run offline pipeline smokes (no DB/LLM)"
	@echo "  make run-all-offline         # run run_all offline on fixture PDF"
	@echo "  make smokes-pipeline-db      # run DB-backed Stage 10→12 smokes (Arango required)"
	@echo "  make arango-clean-db         # drop test DB (ARANGO_DATABASE)"
	@echo "  make smokes-pipeline-happy   # single-command happy-path run + gold validation"
	@echo "  make steps-happy             # run happy path on BHT and print report/summary paths"
	@echo "  make smokes-pipeline-skip01  # happy-path with external annotations (skip Stage 01)"
	@echo "  make smokes-pipeline-api-upsert  # run extract + upsert API smoke (Arango required)"
	@echo "  make smokes-pipeline-api-chat    # run chat smoke (after upsert)"
	@echo "  make smoke-ui-extract-load       # UI smoke (server must be running)"
	@echo "  make smoke-ui-extract-load-cdp   # UI CDP smoke (Chrome --remote-debugging-port=9222)"
	@echo "  make ux-autofix                   # Detect Vite overlay via CDP/Puppeteer and auto-fix JSX"
	@echo "  make lint-ruff-extractor         # Run Ruff only on extractor src/ (focused)"
	@echo "  make smoke-parity-gold           # deterministic parity (canonical flat vs clean artifacts)"
	@echo "  make smokes-api-external     # API bridge: run-external with UI boxes"
	@echo "  make extract-fast PDF=... OUT=... # quick text-only PDF dump (PyMuPDF)"
	@echo "  make bootstrap-smokes # Install minimal deps to run smokes (venv + PYTHONPATH)"
	@echo "  make prompt-opt PROMPT=path.md        # Optimize a raw prompt"
	@echo "  make prompt-compile RESEARCH=path.md  # Compile research to a prompt (LLM)"
	@echo "  make prompt-run PROMPT=path.md        # Optimize then run Show & Tell (3 instances)"
	@echo "  make smoke-07-reflow-min  # minimal Stage 07 reflow smoke (results mode)"
	@echo "  make smoke-ui        # Playwright CDP console-error smoke"
	@echo "  make smoke-ui-strict # Same, exits non-zero and prints artifacts"
	@echo "  make pipeline-verify-invariants  # check global invariants (counts, etc.)"

setup:
	@if command -v uv >/dev/null 2>&1; then \
		uv venv; \
		. .venv/bin/activate && uv pip install -e .[dev]; \
	else \
		python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .[dev]; \
	fi

# Lean environment for Python smokes only (no heavy dev extras)
setup-smokes:
		python3 -m venv .venv && \
		. .venv/bin/activate && \
		python -m ensurepip --upgrade && \
		python -m pip install -U pip && \
		python -m pip install python-dotenv typer httpx loguru pillow urlextract strip_tags tqdm json-repair PyMuPDF camelot-py opencv-python-headless pandas tenacity && \
		python -m pip install torch --index-url https://download.pytorch.org/whl/cpu

# Optional: use uv to install only the minimal smokes extra
setup-smokes-uv:
	uv venv; \
	. .venv/bin/activate && uv pip install -e .[smokes]

dev:
	./scripts/dev.sh

stop:
	- fuser -k 8080/tcp 2>/dev/null || true
	- fuser -k 8001/tcp 2>/dev/null || true

# --- Pipeline 01→05 + Annotator helpers ---

.PHONY: run-01-05
run-01-05:
	@if [ -z "$(PDF)" ] || [ -z "$(OUT)" ]; then \
	  echo "Usage: make run-01-05 PDF=path/to/file.pdf OUT=data/results/pipeline_runs/slug"; exit 1; fi
	rm -rf "$(OUT)" && mkdir -p "$(OUT)/tmp_pdf"
	python src/extractor/pipeline/steps/01_annotation_processor.py run "$(PDF)" -o "$(OUT)"
	$(eval CLEAN:=$(shell jq -r .clean_pdf_path "$(OUT)/01_annotation_processor/json_output/01_annotations.json" 2>/dev/null))
	cp "$(CLEAN)" "$(OUT)/tmp_pdf/"
	python src/extractor/pipeline/steps/02_marker_extractor.py run "$(OUT)/tmp_pdf/$(notdir $(CLEAN))" -o "$(OUT)" --no-spawn
	python src/extractor/pipeline/steps/03_suspicious_headers.py run "$(OUT)/02_marker_extractor/json_output/02_marker_blocks.json" --pdf-dir "$(OUT)/tmp_pdf" -o "$(OUT)" --skip-llm
	python src/extractor/pipeline/steps/04_section_builder.py run "$(OUT)/03_suspicious_headers/json_output/03_verified_blocks.json" --pdf-dir "$(OUT)/tmp_pdf" -o "$(OUT)"
	python src/extractor/pipeline/steps/05_table_extractor.py run "$(OUT)/04_section_builder/json_output/04_sections.json" --pdf-dir "$(OUT)/tmp_pdf" -o "$(OUT)"
	@echo "[run-01-05] CLEAN=$(CLEAN)"

.PHONY: annotate-from-results
annotate-from-results:
	@if [ -z "$(RUN_DIR)" ]; then echo "Usage: make annotate-from-results RUN_DIR=... PDF=..."; exit 1; fi
	@if [ -z "$(PDF)" ] || [ ! -f "$(PDF)" ]; then echo "Set PDF=path/to/<stem>_clean.pdf"; exit 1; fi
	# Canonical single artifact for with_requirements: *_annotated.pdf (render_annotated_pdf.from-run)
	@rm -f scripts/artifacts/BHT_CV32A65X_with_requirements_annotated_*.pdf 2>/dev/null || true
	PYTHONPATH=$(PWD)/src \
	uv run python -m extractor.pipeline.tools.render_annotated_pdf from-run \
	  --pdf "$(PDF)" \
	  --run-dir "$(RUN_DIR)" \
	  --out scripts/artifacts/BHT_CV32A65X_with_requirements_annotated.pdf \
	  --sections-style stroke \
	  --fill-alpha 0.05 \
	  --export-pages \
	  --pages "1-3"
	@echo "[annotate-from-results] Wrote scripts/artifacts/BHT_CV32A65X_with_requirements_annotated.pdf and page PNGs"

.PHONY: smoke-stage02-figures
smoke-stage02-figures:
	@if [ -z "$(RUN_DIR)" ] && [ -z "$(JSON)" ]; then \
	  echo "Usage: make smoke-stage02-figures RUN_DIR=... [JSON=...] [MIN=1]"; exit 1; \
	fi
	uv run scripts/smokes/smoke_stage02_has_figures.py \
	  $$([ -n "$(JSON)" ] && echo --json "$(JSON)" || echo --run-dir "$(RUN_DIR)") \
	  --min $${MIN:-1}

.PHONY: smoke-annot-exist
smoke-annot-exist:
	@PYTHONPATH=$(PWD)/src python scripts/smokes/smoke_annotations_exist.py --pdf "$(PDF)"

.PHONY: annotate-run-01-05
annotate-run-01-05: run-01-05 annotate-from-results

.PHONY: bundle-annotated
bundle-annotated:
	@if [ -z "$(SLUG)" ]; then echo "Usage: make bundle-annotated SLUG=..."; exit 1; fi
	uv run scripts/tools/bundle_annotated_artifacts.py --slug "$(SLUG)"

lint:
	- ruff check .

fmt:
	- black --check .

type:
	- mypy src

test:
	- pytest -q

.PHONY: pipeline-verify-invariants
pipeline-verify-invariants:
	PYTHONPATH=$(PWD)/src \
	python scripts/tools/verify_invariants.py

# Deterministic pipeline contract test only (avoids unrelated suite failures)
.PHONY: test-contract-bht
test-contract-bht:
	PYTHONPATH=$(PWD)/src \
	pytest -q tests/contract/test_bht_06b_09a.py

api-smokes:
	BASE_URL=$(BASE_URL) node scripts/smokes/api_generate_model.mjs

coco-export:
	node scripts/smokes/api_coco_export.mjs


smoke-tabbed-api:
	@echo "[smoke-tabbed-api] Running Tabbed backend API smokes..."
	node scripts/smokes/api_tabbed_basic.mjs && 	node scripts/smokes/api_coco_export.mjs && 	node scripts/smokes/api_suggest_tables.mjs && 	node scripts/smokes/api_pipeline_job.mjs


ux-health:
	BASE_URL=$(BASE_URL) BROWSERLESS_DISCOVERY_URL=$(CDP_URL) node scripts/ux_check_cdp_auto.mjs

smokes:
	BASE_URL=$(BASE_URL) BROWSERLESS_DISCOVERY_URL=$(CDP_URL) node scripts/smokes/all.mjs

ci:
	BASE_URL=$(BASE_URL) BROWSERLESS_DISCOVERY_URL=$(CDP_URL) bash scripts/ci_local.sh

# --- Reports ---
state-of-project:
	@echo "Running State of Project auto-run…";
	PYTHONPATH=$(PWD)/src \
	uv run scripts/tools/state_of_project.py
	@echo "Updated docs/STATE_OF_PROJECT.md"

scaffold:
	node scripts/tools/scaffold_tabbed_issue.mjs --dir prototypes/tabbed/issues --id "$(ISSUE)" --title "$(TITLE)"

smoke-issue:
	BASE_URL=$(BASE_URL) node scripts/smokes/issue_$(ISSUE).mjs

# --- Gamified targets ---

PYTEST ?= pytest

gamified-e2e:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src GAMIFIED_FAST_BENCH=1 $(PYTEST) -q tests/smoke/gamified/test_prompt_to_web_logging.py

gamified-all:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src $(PYTEST) -q tests/smoke/gamified

gamified-all-fast:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src GAMIFIED_FAST_BENCH=1 $(PYTEST) -q tests/smoke/gamified

gamified-codex:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src RUN_CODEX_SMOKE=1 GAMIFIED_FAST_BENCH=1 $(PYTEST) -q tests/smoke/gamified/test_codex_exec_path.py

gamified-cli:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src python scripts/smokes/gamified/run_all.py

gamified-cli-uv:
	./scripts/gamified_cli_uv.py --help || true

gamified-status-uv:
	./scripts/gamified_status_uv.py --help || true

# Launch three Codex instances (mul_shift_add, mul_karatsuba, mul_chunked) and return results
gamified-3x:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src GAMIFIED_FAST_BENCH=1 $(PYTEST) -q tests/smoke/gamified/test_three_codex_instances.py

gamified-weblog:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src $(PYTEST) -q tests/smoke/gamified/test_web_log_server.py

gamified-e2e-web:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=./src GAMIFIED_FAST_BENCH=1 $(PYTEST) -q tests/smoke/gamified/test_weblog_e2e_codex.py

gamified-ui-smoke:
	cd prototypes/gamified/dashboard && npm run smoke:ui

.PHONY: coco-export smoke-tabbed-api gamified-show
gamified-show:
	./scripts/gamified_show_and_tell.py --codebase .

# --- Lessons (ArangoDB) ---
LESSON_TITLE ?=
LESSON_PROBLEM ?=
LESSON_PLAYBOOK ?=
LESSON_TAGS ?=
LESSON_SCOPE ?= tabbed

lessons-setup:
	. .venv/bin/activate 2>/dev/null || true; \
		.venv/bin/python -m pip install -q arango-python-driver typer >/dev/null 2>&1 || true; \
		.venv/bin/python scripts/lessons/setup.py

lessons-add:
	. .venv/bin/activate 2>/dev/null || true; \
		.venv/bin/python -m pip install -q arango-python-driver typer >/dev/null 2>&1 || true; \
		.venv/bin/python scripts/lessons/add.py --title "$(LESSON_TITLE)" --problem "$(LESSON_PROBLEM)" --playbook "$(LESSON_PLAYBOOK)" --tags "$(LESSON_TAGS)" --scope "$(LESSON_SCOPE)"

lessons-search:
	. .venv/bin/activate 2>/dev/null || true; \
		.venv/bin/python -m pip install -q arango-python-driver typer >/dev/null 2>&1 || true; \
		.venv/bin/python scripts/lessons/search.py --q "$(Q)" --tags "$(TAGS)"

lessons-recall:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
	uv run scripts/lessons/recall_agent.py --q "$(Q)" --tags "$(TAGS)" --scope "$(SCOPE)" --k $${K:-5}

lessons-recall-last:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		uv run scripts/lessons/recall_agent.py --from-latest-log --tags "$(TAGS)" --scope "$(SCOPE)" --k $${K:-5}

# --- Quick fast extract (PyMuPDF text-only) ---
.PHONY: extract-fast
extract-fast:
	. .venv/bin/activate 2>/dev/null || true; \
		$(PY) -m src.cli extract --mode fast $(PDF) $(OUT)

lessons-seed-demo:
	@if command -v lessons-seed >/dev/null 2>&1; then \
		ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		lessons-seed --count $${COUNT:-50} $$( [ -n "$(SCOPE)" ] && echo --scope "$(SCOPE)" || true ) $$( [ -n "$(BATCH)" ] && echo --batch "$(BATCH)" || true ); \
	else \
		PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		uv run scripts/lessons/seed_demo.py --count $${COUNT:-50} $$( [ -n "$(SCOPE)" ] && echo --scope "$(SCOPE)" || true ) $$( [ -n "$(BATCH)" ] && echo --batch "$(BATCH)" || true ); \
	fi

lessons-delete-demo:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
	uv run scripts/lessons/delete_demo.py $$( [ -n "$(BATCH)" ] && echo --demo-batch "$(BATCH)" || true )

lessons-delete:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
	uv run scripts/lessons/delete.py --key "$(KEY)" --title "$(TITLE)" --scope "$(SCOPE)"

lessons-link:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
	uv run scripts/lessons/link.py --from-key "$(FROM_KEY)" --to-key "$(TO_KEY)" --from-title "$(FROM_TITLE)" --from-scope "$(FROM_SCOPE)" --to-title "$(TO_TITLE)" --to-scope "$(TO_SCOPE)" --rationale "$(RATIONALE)" --weight $${WEIGHT:-0.5}

lessons-related:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
	uv run scripts/lessons/related.py --key "$(KEY)" --title "$(TITLE)" --scope "$(SCOPE)" --direction $${DIR:-both} --k $${K:-10}

lessons-multihop:
	PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
	uv run scripts/lessons/multihop.py --key "$(KEY)" --title "$(TITLE)" --scope "$(SCOPE)" --depth $${DEPTH:-2} --direction $${DIR:-ANY} --limit $${K:-5}

bootstrap-smokes:
	@echo "Ensuring venv and minimal smoke deps..."
	@if [ ! -d .venv ]; then python3 -m venv .venv; fi
	. .venv/bin/activate; \
		.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true; \
		.venv/bin/pip3 install --break-system-packages -q \
			pytest fastapi uvicorn httpx typer numpy requests python-dotenv pydantic-settings loguru tqdm starlette pydantic python-arango tenacity pyyaml litellm >/dev/null 2>&1 || true; \
		echo "Done. Use: source .venv/bin/activate && export PYTHONPATH=./src"

.PHONY: coco-export smoke-tabbed-api arango-up arango-down
arango-up:
	docker compose -f docker-compose.arango.yml up -d

arango-down:
	docker compose -f docker-compose.arango.yml down -v

# --- litellm_call smokes (utility-level) ---
smoke-litellm:
	$(PY) scripts/smokes/litellm_call_smoke.py sanity

smoke-litellm-image:
	$(PY) scripts/smokes/litellm_call_smoke.py image-url

smoke-litellm-all: smoke-litellm smoke-litellm-image

# Save structured artifacts (sanitized request/messages)
smoke-litellm-results:
	$(PY) scripts/smokes/litelllm/call2_sanity.py sanity && \
	$(PY) scripts/smokes/litelllm/call2_sanitize_modes.py all

# Extended smokes: local file path, streaming, and batch
smoke-litellm-local:
	$(PY) scripts/smokes/litellm_call_smoke.py local-image

smoke-litellm-stream:
	$(PY) scripts/smokes/litellm_call_smoke.py stream

# --- Pipeline offline smokes ---
.PHONY: smokes-pipeline-offline run-all-offline
smokes-pipeline-offline:
	. .venv/bin/activate 2>/dev/null || true; \
		python scripts/smokes/smoke_stage03_skip_llm.py -o data/results/pipeline_smoke_tmp03 && \
		python scripts/smokes/smoke_stage06_skip_descriptions.py -o data/results/pipeline_smoke_tmp06 && \
		python scripts/smokes/smoke_stage08_skip_proving.py -o data/results/pipeline_smoke_tmp08 && \
		python scripts/smokes/smoke_stage10_skip_embeddings.py -o data/results/pipeline_smoke_tmp10 && \
		python scripts/smokes/smoke_stage11_skip_graph.py -o data/results/pipeline_smoke_tmp11

run-all-offline:
	. .venv/bin/activate 2>/dev/null || true; \
		PYTHONPATH=./src python scripts/smokes/smoke_run_all_offline.py -o data/results/pipeline_smoke_offline

.PHONY: smokes-pipeline-db arango-clean-db
smokes-pipeline-db:
	. .venv/bin/activate 2>/dev/null || true; \
		python scripts/smokes/pipeline/smoke_stage10_export_db.py -o data/results/pipeline_db_smoke && \
		python scripts/smokes/pipeline/smoke_stage11_graph_db.py -o data/results/pipeline_db_smoke && \
		python scripts/smokes/pipeline/smoke_stage12_annotations_db.py -o data/results/pipeline_db_smoke

arango-clean-db:
	. .venv/bin/activate 2>/dev/null || true; \
		python -c "import os,sys; from arango import ArangoClient; host=os.getenv('ARANGO_HOST','localhost'); port=int(os.getenv('ARANGO_PORT',8529)); user=os.getenv('ARANGO_USER','root'); password=os.getenv('ARANGO_PASSWORD'); db=os.getenv('ARANGO_DATABASE','pdf_knowledge_base_test');\n\
if not password: sys.exit('ARANGO_PASSWORD not set');\n\
client=ArangoClient(hosts=f'http://{host}:{port}'); sys_db=client.db('_system', username=user, password=password);\n\
import json;\n\
print(f'Dropping DB if exists: {db}');\n\
\nif sys_db.has_database(db): sys_db.delete_database(db); print(f'Dropped DB: {db}')" || true

.PHONY: smokes-pipeline-happy
smokes-pipeline-happy:
	. .venv/bin/activate 2>/dev/null || true; \
		PYTHONPATH=./src ARANGO_DATABASE=$${ARANGO_DATABASE:-pdf_knowledge_base_test} \
		python scripts/smokes/pipeline/smoke_pipeline_happy.py -o data/results/pipeline_happy_smoke

.PHONY: smokes-pipeline-skip01 smokes-api-external
smokes-pipeline-skip01:
	. .venv/bin/activate 2>/dev/null || true; \
		PYTHONPATH=./src python scripts/smokes/pipeline/smoke_pipeline_happy_skip01.py -o data/results/pipeline_happy_skip01

smokes-pipeline-api-external smokes-api-external:
	. .venv/bin/activate 2>/dev/null || true; \
		PYTHONPATH=./src python scripts/smokes/pipeline/smoke_api_external_annotations.py

.PHONY: smokes-pipeline-api-upsert
smokes-pipeline-api-upsert:
	. .venv/bin/activate 2>/dev/null || true; \
		PYTHONPATH=./src python scripts/smokes/pipeline/smoke_api_upsert.py

.PHONY: smokes-pipeline-api-chat
smokes-pipeline-api-chat:
	. .venv/bin/activate 2>/dev/null || true; \
		PYTHONPATH=./src python scripts/smokes/pipeline/smoke_api_chat.py

.PHONY: smoke-ui-extract-load
smoke-ui-extract-load:
	@echo "Requires dev servers: Vite on 8080, Tabbed API running"; \
	node scripts/smokes/ui_extract_load.mjs

.PHONY: smoke-ui-extract-load-cdp
smoke-ui-extract-load-cdp:
	@echo "Requires Chrome with --remote-debugging-port=9222 and Vite on 8080"; \
	BROWSERLESS_WS=$${BROWSERLESS_WS:-ws://127.0.0.1:9222/devtools/browser} \
	node scripts/smokes/ui_extract_load_cdp.mjs

.PHONY: ux-autofix
ux-autofix:
	@echo "Attempting CDP/Puppeteer overlay auto-fix (ClassicLayout.tsx SidebarContent)…"; \
	BROWSERLESS_WS=$${BROWSERLESS_WS:-ws://127.0.0.1:9222/devtools/browser} \
	BASE_URL=$${BASE_URL:-http://127.0.0.1:8080} \
	node scripts/tools/ux_autofix_overlay.mjs || true

.PHONY: steps-happy
steps-happy:
	@echo "[steps-happy] Running happy-path pipeline on BHT sample..."
	@. .venv/bin/activate 2>/dev/null || true; \
		set -a; [ -f .env ] && . .env; set +a; \
		export PYTHONPATH=$$(pwd)/src; \
		export ARANGO_DATABASE=$${ARANGO_DATABASE:-pdf_knowledge_base_test}; \
		pipeline-happy \
		  --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
		  --results data/results/pipeline_happy || exit $$?; \
		echo "[steps-happy] Report (md): data/results/pipeline_happy/final_report.md"; \
		echo "[steps-happy] Summary   : scripts/artifacts/run_summary_happy.json"; \
		( command -v jq >/dev/null 2>&1 && jq -r '. | {ok,score,stages}' scripts/artifacts/run_summary_happy.json ) || true

smoke-litellm-batch:
	$(PY) scripts/smokes/litellm_call_smoke.py batch

smoke-litellm-full: smoke-litellm-all smoke-litellm-results smoke-litellm-local smoke-litellm-stream smoke-litellm-batch

# Minimal Stage 07 reflow smoke to prevent empty-results regressions
smoke-07-reflow-min:
	$(PY) scripts/smokes/pipeline/smoke_stage07_reflow_min.py

# Python-only smokes (no servers). Ensures PYTHONPATH for in-repo imports.
smokes-python:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=src $(PY) scripts/smokes/run_all_smokes.py && \
	$(MAKE) smoke-litellm-full && \
	$(MAKE) smoke-07-reflow-min

# Strict Stage 07 smokes only
smokes-stage07-strict:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_stage_call_text.py && \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_complex_full.py && \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_table_integrity.py && \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_figure_propagation.py

smokes-stage07-strict-extended:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_stage_call_text.py && \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_complex_full.py && \
	PYTHONPATH=src LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json $(PY) scripts/smokes/pipeline/smoke_stage07_table_block_strict.py

# --- UI runtime error smoke (Playwright over CDP) ---
SMOKE_URL ?= http://127.0.0.1:8080/classic
CDP_ORIGIN ?= http://127.0.0.1:9222
CDP_TOKEN ?=

smoke-ui:
	. .venv/bin/activate 2>/dev/null || true; \
		.venv/bin/python -m pip install -q playwright typer requests >/dev/null 2>&1 || true; \
		.venv/bin/python -m playwright install chromium >/dev/null 2>&1 || true; \
		CDP_ORIGIN=$(CDP_ORIGIN) CDP_TOKEN=$(CDP_TOKEN) \
		.venv/bin/python scripts/smokes/console_errors.py --url "$(SMOKE_URL)" --cdp-origin "$(CDP_ORIGIN)" --token "$(CDP_TOKEN)"

smoke-ui-strict: smoke-ui

# Quick end-to-end pipeline (gold checks), skips heavy DB/graph steps
quick-pipeline:
	. .venv/bin/activate 2>/dev/null || true; PYTHONPATH=src $(PY) src/extractor/pipeline/tools/quick_smoke.py --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf

# Full pipeline (requires provider API keys and ArangoDB configured in env)
pipeline-full:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src $(PY) -m extractor.pipeline \
		--pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
		--out data/results/pipeline

# --- Live CI helper (self-hosted) ---
# Runs LLM stages on the BHT sample (noannots) and verifies outputs.
# Expects CHUTES_* env set (API base/key/models); skips DB export.
LIVE_PDF ?= data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf
LIVE_OUT ?= data/results/pipeline_live

.PHONY: ci-live
ci-live:
	. .venv/bin/activate 2>/dev/null || true; \
		python -m pip install --upgrade pip >/dev/null 2>&1 || true; \
		python -m pip install -e .[dev]; \
		set -a; test -f ./.env && . ./.env || true; set +a; \
		export PYTHONPATH=$$(pwd)/src; \
		TABLE_LLM_ASSIST=1 \
		python -m extractor.pipeline.run_pipeline \
		  --pdf $(LIVE_PDF) \
		  --out $(LIVE_OUT) \
		  --stop-on-fail \
		  --stage-timeout $${PIPELINE_STAGE_TIMEOUT:-900} \
		  --skip-export; \
		python scripts/ci/verify_live_pipeline.py --out $(LIVE_OUT)

.PHONY: ci-det
ci-det:
	. .venv/bin/activate 2>/dev/null || true; \
		python -m pip install --upgrade pip >/dev/null 2>&1 || true; \
		python -m pip install -e .[dev]; \
		export PYTHONPATH=$$(pwd)/src; \
		STAGE05_LLM_SPLIT_1COL=0 STAGE06B_EMIT_MERGE_HINTS=0 \
		python -m extractor.pipeline.run_pipeline \
		  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		  --out data/results/pipeline_det \
		  --summary-only --skip-fig-descriptions --annotate-pdf --stop-on-fail; \
		pytest -q tests/contract/test_contract_bht_det.py

# --- Bundles for LLM code reviews ---
BUNDLE_ROOT ?= prototypes/tabbed
BUNDLE_OUT ?= scripts/artifacts/tabbed_bundle.txt
BUNDLE_HEADER ?= scripts/artifacts/tabbed_code_review_request.md
BUNDLE_REVIEW_OUT ?= scripts/artifacts/tabbed_code_review_bundle.md

.PHONY: coco-export smoke-tabbed-api bundle-tabbed
bundle-tabbed:
	@mkdir -p scripts/artifacts
	@echo "[bundle-tabbed] Bundling $(BUNDLE_ROOT) → $(BUNDLE_OUT)"
	@python3 scripts/tools/copy_selected_files.py --root $(BUNDLE_ROOT) --output $(BUNDLE_OUT)
	@echo "[bundle-tabbed] Writing review header → $(BUNDLE_HEADER)"
	@cp docs/templates/review_header_python.md $(BUNDLE_HEADER)
	@echo "[bundle-tabbed] Creating final bundle with header → $(BUNDLE_REVIEW_OUT)"
	@cat $(BUNDLE_HEADER) $(BUNDLE_OUT) > $(BUNDLE_REVIEW_OUT)
	@wc -c $(BUNDLE_REVIEW_OUT) | awk '{print "[bundle-tabbed] Bytes:", $$1}'; echo "[bundle-tabbed] Done → $(BUNDLE_REVIEW_OUT)"

lessons-propose:
	@if command -v lessons-propose >/dev/null 2>&1; then \
		ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		lessons-propose --k $${K:-12} --sim-thresh $${SIM:-0.55} --min-top $${MIN_TOP:-3} $$( [ -n "$(SCOPE)" ] && echo --scope "$(SCOPE)" || true ); \
	else \
		PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		./scripts/lessons/propose_faiss.py --k $${K:-12} --sim-thresh $${SIM:-0.55} --min-top $${MIN_TOP:-3} $$( [ -n "$(SCOPE)" ] && echo --scope "$(SCOPE)" || true ); \
	fi

lessons-prune:
	@if command -v lessons-prune >/dev/null 2>&1; then \
		ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} lessons-prune; \
	else \
		PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		uv run scripts/lessons/prune_pending.py; \
	fi

lessons-status-report:
	pytest -q || true
	uv run scripts/lessons/report_status.py --report test-results.json --out-md scripts/artifacts/lessons_status_report.md

lessons-http-smokes:
	pytest -q tests/lessons/test_http_endpoints.py

lessons-recall-diff:
	@if command -v lessons-recall-diff >/dev/null 2>&1; then \
		ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		lessons-recall-diff --q "$(Q)" --scope "$(SCOPE)" --k $${K:-5} --depth $${DEPTH:-2}; \
	else \
		PYTHONPATH=. ARANGO_URL=$${ARANGO_URL:-http://127.0.0.1:8529} ARANGO_DB=$${ARANGO_DB:-lessons} ARANGO_USER=$${ARANGO_USER:-root} ARANGO_PASS=$${ARANGO_PASS:-openSesame} \
		uv run scripts/lessons/recall_diff.py diff --q "$(Q)" --scope "$(SCOPE)" --k $${K:-5} --depth $${DEPTH:-2}; \
	fi


.PHONY: coco-export smoke-tabbed-api prompt-opt prompt-compile prompt-run
prompt-opt:
	python -m prototypes.gamified.tools.prompt_opt optimize $(PROMPT) -o $(PROMPT) --show-diff

prompt-compile:
	python -m prototypes.gamified.tools.prompt_compile compile $(RESEARCH) -o prototypes/gamified/docs/02_tokamak_prompt.md --show-diff

prompt-run:
	./scripts/gamified_show_and_tell.py --codebase . --prompt "$(shell cat $(PROMPT))"
.PHONY: lint-ruff-extractor
lint-ruff-extractor:
	. .venv/bin/activate 2>/dev/null || true; \
	ruff check src/extractor || true

# --- Pipeline fast gates (offline/online smokes) ---
.PHONY: smokes-fast smokes-online

smokes-fast:
	./scripts/ci_fast_gate.sh

smokes-online:
	SMOKES_ONLINE=1 ./scripts/ci_fast_gate.sh

ARANGODB_URL?=http://localhost:8529
ARANGODB_USERNAME?=root

.PHONY: arango-bootstrap
arango-bootstrap:
	uv run scripts/db/arangodb_bootstrap.py $(DB)

.PHONY: graph-edges-from-hints
graph-edges-from-hints:
	@[ -n "$(HINTS)" ] || (echo "Set HINTS=path/to/edge_hints.json" && exit 2)
	@[ -n "$(DB)" ] || (echo "Set DB=name (e.g., lean4_prod)" && exit 2)
	uv run scripts/pipeline/stage11_build_edges.py $(HINTS) edges.json --arangodb $(DB)

.PHONY: graph-knn
graph-knn:
	@[ -n "$(FLAT10)" ] || (echo "Set FLAT10=path/to/flat10.json" && exit 2)
	@[ -n "$(DB)" ] || (echo "Set DB=name (e.g., lean4_prod)" && exit 2)
	uv run scripts/pipeline/compute_embeddings_knn.py $(FLAT10) knn_edges.json --arangodb $(DB) --knn-k 5

.PHONY: graph-oneclick
graph-oneclick:
	@[ -n "$(DB)" ] || (echo "Set DB=name (e.g., lean4_prod)" && exit 2)
	@[ -n "$(HINTS)$(FLAT10)" ] || (echo "Provide HINTS=edge_hints.json or FLAT10=flat10.json" && exit 2)
	uv run scripts/db/arangodb_bootstrap.py $(DB)
	@if [ -n "$(HINTS)" ]; then \
	  uv run scripts/pipeline/stage11_build_edges.py $(HINTS) edges.json --arangodb $(DB); \
	else \
	  uv run scripts/pipeline/stage11_build_edges.py $(FLAT10) edges.json --arangodb $(DB) --fallback-lemma-candidates; \
	fi
	@if [ -n "$(FLAT10)" ]; then \
	  uv run scripts/pipeline/compute_embeddings_knn.py $(FLAT10) knn_edges.json --arangodb $(DB) --knn-k 5; \
	fi
	@mkdir -p aql_out
	uv run scripts/queries/run_aql.py --db $(DB) scripts/queries/q1_find_contradictions.aql > aql_out/contradictions.json || true
	uv run scripts/queries/run_aql.py --db $(DB) scripts/queries/q2_downstream_impact.aql --params '{"start_id":"sections/S1","max_hops":3,"graph":"lean4_g"}' > aql_out/downstream_S1.json || true

.PHONY: graph-metrics
graph-metrics:
	@[ -n "$(DB)" ] || (echo "Set DB=name (e.g., lean4_prod)" && exit 2)
	uv run scripts/reports/graph_metrics.py --db $(DB)

.PHONY: graph-emit-db-edges
graph-emit-db-edges:
	@[ -n "$(OUT)" ] || (echo "Set OUT=db_edges.json" && exit 2)
	@if [ -n "$(HINTS)" ]; then \
	  uv run scripts/pipeline/stage11_build_edges.py $(HINTS) edges.json --emit-db-edges $(OUT); \
	elif [ -n "$(FLAT10)" ]; then \
	  uv run scripts/pipeline/stage11_build_edges.py $(FLAT10) edges.json --emit-db-edges $(OUT) --fallback-lemma-candidates; \
	else \
	  echo "Provide HINTS=edge_hints.json or FLAT10=flat10.json" && exit 2; \
	fi
.PHONY: graph-viewer-prepare
graph-viewer-prepare:
	@[ -n "$(SRC)" ] || (echo "Set SRC=edge_hints.json or edges.json (portable) or docgen4.json (DB-native)" && exit 2)
	@if echo "$(SRC)" | grep -q docgen4; then \
	  uv run scripts/viewers/adapter_docgen4_to_graph.py $(SRC) graph.json; \
	else \
	  uv run scripts/viewers/prepare_graph_json.py $(SRC) graph.json; \
	fi
	@echo "Wrote graph.json (viewer input)"

.PHONY: graph-viewer-render
graph-viewer-render:
	@[ -n "$(JSON)" ] || (echo "Set JSON=graph.json" && exit 2)
	uv run scripts/viewers/render_vis_html.py $(JSON) viewer.html
	@echo "Open viewer.html in a browser"
# Rinse/Repeat UX gate with timeouts and optional bundle
.PHONY: rinse rinse-cdp
rinse:
	ATTEMPTS?=3
	@echo "[make rinse] attempts=$(ATTEMPTS)"
	ATTEMPTS=$(ATTEMPTS) bash scripts/ci_rinse_repeat.sh

	rinse-cdp:
	ATTEMPTS?=3
	@echo "[make rinse-cdp] attempts=$(ATTEMPTS)"
	ATTEMPTS=$(ATTEMPTS) BROWSERLESS_WS?=ws://127.0.0.1:9222/devtools/browser \
	  bash scripts/ci_rinse_repeat.sh

# Run UI/API smokes with timeouts (fast and full variants)
.PHONY: smokes-rinse smokes-rinse-full
smokes-rinse:
	@echo "[make smokes-rinse] FAST=1"
	SMOKES_FAST=1 timeout 900s node scripts/smokes/all.mjs

smokes-rinse-full:
	@echo "[make smokes-rinse-full]"
	timeout 1800s node scripts/smokes/all.mjs


# --- CI helpers ---
PDF_DIR ?= prototypes/tabbed/pdfs
TARGET_URL ?= http://127.0.0.1:4173/main

.PHONY: ensure-pdfs
ensure-pdfs:
	@if ! ls -1 "$(PDF_DIR)"/*.pdf >/dev/null 2>&1; then 	  echo "[ensure-pdfs] No PDFs found in $(PDF_DIR). Add at least one .pdf or set PDF_DIR=..."; 	  exit 1; 	fi

.PHONY: lint-api-gates
lint-api-gates:
	@echo "[lint-api-gates] checking that /api calls are gated in preview/dev..."
	@! rg -n --hidden "/api/" prototypes/tabbed/html/src 	  | rg -v "isPreview\(|isDev\(" 	  || (echo "[lint-api-gates] Found ungated /api references. Gate them behind isPreview()/isDev()." && exit 1)

# --- CI one-shot (scenarios-first) ---

# Defaults for CDP + base URL (override in CI if needed)
BASE_URL ?= http://127.0.0.1:8080
CDP_DISCOVERY ?= http://127.0.0.1:9222/json/version

.PHONY: ci-rinse
ci-rinse:
	@echo "[ci-rinse] UX pack (scenarios)"
	SCENARIOS_FILTER=ux_ \
	SCENARIOS_STOP_ON_FIRST_FAILURE=0 \
	BASE_URL=$(BASE_URL) \
	BROWSERLESS_DISCOVERY_URL=$(CDP_DISCOVERY) \
	python3 scenarios/run_all.py
	@echo "[ci-rinse] Pipeline subset (scenarios)"
	SCENARIOS_FILTER=pipeline_api_health,pipeline_check_stage10_flattened,pipeline_step_11_graph_db \
	python3 scenarios/run_all.py
	@echo "[ci-rinse] Summaries:"
	@find scripts/artifacts -maxdepth 4 -type f -name "scenarios_summary.json" -print | tail -n 6

.PHONY: ci-rinse-preview
ci-rinse-preview:
	@echo "[ci-rinse-preview] preview gate"; \
	VITE_PREVIEW=1 CONSOLE_ERRORS_TIMEOUT_MS=90000 TARGET_URL=$(TARGET_URL) node scenarios/ux/console_errors.mjs
	@echo "[ci-rinse-preview] no-preview-api check"; \
	VITE_PREVIEW=1 TARGET_URL=$(TARGET_URL) node scenarios/ux/no_preview_api_requests.mjs
.PHONY: env-accurate
env-accurate:
	@echo "Syncing environment with accurate extras (Torch + Surya + table_rec)"
	uv sync --extra accurate
	@echo "Done. Activate with: source .venv/bin/activate"
	@echo "  make run-ci PDF=... OUT=...     # deterministic profile: no LLM, summary-only07, skip 10/11"
	@echo "  make run-prod PDF=... OUT=...   # production profile: 03/06/07 LLMs ON with hardening"
# --- Profiles: CI (deterministic) and PROD (LLMs on) ---
.PHONY: run-ci run-prod
run-ci:
	@if [ -z "$(PDF)" ] || [ -z "$(OUT)" ]; then \
	  echo "Usage: make run-ci PDF=path/to/file.pdf OUT=data/results/pipeline_ci"; exit 1; fi
	PROFILE=ci \
	STAGE07_MINIMAL_JSON=1 STAGE07_FORCE_SCHEMA_HINT=1 \
	python -m extractor.pipeline.run_all \
	  --pdf "$(PDF)" \
	  --results "$(OUT)" \
	  --offline --skip-llm03 --skip-descriptions06 --summary-only07 \
	  --skip-export10 --skip-embeddings10 --skip-graph11 --prove08

run-prod:
	@if [ -z "$(PDF)" ] || [ -z "$(OUT)" ]; then \
	  echo "Usage: make run-prod PDF=path/to/file.pdf OUT=data/results/pipeline_prod"; exit 1; fi
	PROFILE=prod \
	USE_LLM_ADAPTER=1 \
	STAGE07_MINIMAL_JSON=1 STAGE07_FORCE_SCHEMA_HINT=1 STAGE07_PRUNE_TOPLEVEL_KEYS=1 \
	python -m extractor.pipeline.run_all \
	  --pdf "$(PDF)" \
	  --results "$(OUT)" \
	  --no-offline --no-skip-llm03 --no-skip-descriptions06 --full07 \
	  --skip-export10 --skip-embeddings10 --skip-graph11 --skip-proving08
# Deterministic golden verify (no network)
pipeline-verify-expected:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src $(PY) -m extractor.pipeline \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline \
		--summary-only \
		--skip-fig-descriptions \
		--skip-export && \
	uv run scripts/tools/expected_verify.py \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline \
		--expected-root data/expected/pipeline \
		--steps 01,02,04,05,06,07,09
# Render visual overlays for steps (PNG per page)
pipeline-render-visuals:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src $(PY) -m extractor.pipeline \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline \
		--summary-only \
		--skip-fig-descriptions \
		--skip-export && \
	PYTHONPATH=src $(PY) -m extractor.pipeline.visual.render \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline \
		--viz-out data/results/pipeline \
		--steps 02,05,06

# Compare rendered visuals with expected
pipeline-verify-expected-images:
	uv run scripts/tools/expected_imgdiff.py \
		--expected data/expected/pipeline/BHT_CV32A65X_with_requirements_noannots \
		--actual   data/results/pipeline \
		--steps 02,05,06
# Live (LLM-on) pipeline run for actual results (no deterministic flags)
pipeline-live:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src $(PY) -m extractor.pipeline \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline

# Live run + visuals + snapshot for side-by-side diff later
pipeline-live-visuals:
	. .venv/bin/activate 2>/dev/null || true; \
	PYTHONPATH=src $(PY) -m extractor.pipeline \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline && \
	PYTHONPATH=src $(PY) -m extractor.pipeline.visual.render \
		--pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
		--out data/results/pipeline \
		--viz-out data/results/pipeline \
		--steps 02,05,06 && \
	uv run scripts/tools/snapshot_pipeline_outputs.py \
		--out data/results/pipeline \
		--visual-dir data/results/pipeline \
		--dest-root scripts/artifacts/snapshots
PIPELINE_PDF ?= data/input/pipeline/BHT_CV32A65X_marked.pdf
PIPELINE_OUT ?= data/results/pipeline

.PHONY: pipeline-fast
pipeline-fast:
	PYTHONPATH=src \
	python -m extractor.pipeline.run_pipeline \
	  --pdf $(PIPELINE_PDF) \
	  --out $(PIPELINE_OUT) \
	  --summary-only \
	  --skip-fig-descriptions || true
	@mkdir -p scripts/artifacts/pipeline
	PYTHONPATH=src \
	python scripts/tools/collect_proofs.py $(PIPELINE_OUT) scripts/artifacts/pipeline
	@echo "Artifacts collected under scripts/artifacts/pipeline"
