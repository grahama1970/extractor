.PHONY: healthcheck verify-env pipeline-health

# Verify full network access, no filesystem sandbox, and ArangoDB connectivity
healthcheck: verify-env

verify-env:
	bash scripts/verify_environment.sh

# Run full pipeline CLI verification (real network + Arango)
pipeline-health:
	bash scripts/verify_pipeline_cli.sh
