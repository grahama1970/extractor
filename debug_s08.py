
from pathlib import Path
import sys
from extractor.pipeline.steps import s08_lean4_theorem_prover
import asyncio
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

db_path = Path("data/results/pipeline/pipeline.duckdb")
pipeline_dir = Path("data/results/pipeline")

print("Running S08 Debug...")
import duckdb
logger.info("Cleaning up previous S08 data...")
con = duckdb.connect(str(db_path))
con.execute("DELETE FROM requirements")
con.execute("DELETE FROM lean4_proofs")
con.execute("DELETE FROM merged_content WHERE type='requirement'")
con.close()

s08_lean4_theorem_prover.run_extract_requirements(pipeline_dir, db_path)
print("S08 Debug Complete.")
