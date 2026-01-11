import sys
from pathlib import Path
from extractor.pipeline.steps.s05b_table_describer import run
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="DEBUG")

stage_05_dir = Path("data/results/pipeline/test_run/05_table_extractor")
out_dir = Path("data/results/pipeline/test_run")

print(f"Running debug S05b input={stage_05_dir}")
run(stage_05_dir, out_dir, skip_descriptions=False)
