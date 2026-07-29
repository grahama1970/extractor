#!/bin/bash
# Run re-extraction for Iteration 1 stratified sample (45 PDFs)

SAMPLE_FILE="stratified_sample.txt"
RESULTS_BASE="/mnt/storage12tb/extractor_corpus/results_iteration_1"
CORPUS_ROOT="/mnt/storage12tb/extractor_corpus"
mkdir -p "$RESULTS_BASE"

echo "Using stratified sample: $SAMPLE_FILE"
echo "Results dir: $RESULTS_BASE"
echo "Corpus root: $CORPUS_ROOT"

# Read line by line (safely)
while IFS= read -r PDF_REL_PATH || [ -n "$PDF_REL_PATH" ]; do
    # Skip empty lines
    if [ -z "$PDF_REL_PATH" ]; then
        continue
    fi

    FULL_PDF_PATH="$CORPUS_ROOT/$PDF_REL_PATH"
    
    if [ ! -f "$FULL_PDF_PATH" ]; then
        echo "Error: PDF not found: $FULL_PDF_PATH"
        continue
    fi

    PDF_NAME=$(basename "$FULL_PDF_PATH" .pdf)
    echo "Processing $PDF_NAME ($FULL_PDF_PATH)..."
    
    # Run full pipeline (all 14 stages)
    # We do NOT use skip flags.
    # We enable requirement proving and PDF annotation.
    # We enable the ML-based strategy predictor for tables.
    export USE_STRATEGY_PREDICTOR=true
    export STRATEGY_PREDICTOR_MODEL_PATH="${STRATEGY_PREDICTOR_MODEL_PATH:-$HOME/workspace/experiments/pi-mono/.pi/skills/create-table-classifier/models/table-classifier-ensemble-final}"
    export SCILLM_MODEL="PLACEHOLDER_M7"
    
    uv run python3 -m extractor.pipeline \
        --pdf "$FULL_PDF_PATH" \
        --out "$RESULTS_BASE/results_iter1/$PDF_NAME" \
        --skip-table-descriptions \
        --skip-fig-descriptions \
        --skip-llm03 >> batch_iter1.log 2>&1
    
    RET_CODE=$?
    if [ $RET_CODE -ne 0 ]; then
        echo "Error processing $PDF_NAME (exit code $RET_CODE). A batch failure occurred."
        # Optional: create a sentinel file or just exit
        echo "FATAL: Pipeline failed for $PDF_NAME" >> batch_iter1.log
        if [ "$STOP_ON_FAIL" = "true" ]; then
             exit 1
        fi
    fi
done < "$SAMPLE_FILE"

echo "Iteration 1 re-extraction complete."
