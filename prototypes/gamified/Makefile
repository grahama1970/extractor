.PHONY: memory-timeline research-update

# Update timeline freshness for gamified scope (recency-aware search)
memory-timeline:
	ARANGO_URL?=http://127.0.0.1:8529
	ARANGO_DB?=lessons
	ARANGO_USER?=root
	ARANGO_PASS?=openSesame
	uv run lessons-timeline build --scope gamified --json >/dev/null || true

# On-demand arXiv refresh for research scope (abstract-only by default)
research-update:
	ARANGO_URL?=http://127.0.0.1:8529
	ARANGO_DB?=lessons
	ARANGO_USER?=root
	ARANGO_PASS?=openSesame
	SCOPE?=research
	MAX?=3
	PDF_TOP?=0
	@if [ -f configs/arxiv_queries.txt ]; then \
	  while IFS= read -r Q; do \
	    [ -z "$$Q" ] && continue; \
	    echo "[arxiv] $$Q"; \
	    uv run lessons-arxiv-research --q "$$Q" --scope "$(SCOPE)" --max-results "$(MAX)" --pdf-top "$(PDF_TOP)" >/dev/null || true; \
	  done < configs/arxiv_queries.txt; \
	else \
	  echo "No configs/arxiv_queries.txt; pass Q='...' to run once"; \
	  [ -n "$(Q)" ] && uv run lessons-arxiv-research --q "$(Q)" --scope "$(SCOPE)" --max-results "$(MAX)" --pdf-top "$(PDF_TOP)" || true; \
	fi
