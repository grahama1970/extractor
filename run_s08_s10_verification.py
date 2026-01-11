
import asyncio
import os
from pathlib import Path
from extractor.pipeline.steps.s08_extract_requirements import run_extract_requirements
from extractor.pipeline.steps.s10_markdown_exporter import run as run_s10
import shutil

# Config
os.environ["SCILLM_API_BASE"] = "http://localhost:8791/v1"
os.environ["SCILLM_API_KEY"] = "sk-placeholder"
os.environ["CHUTES_TEXT_MODEL"] = "moonshotai/Kimi-K2-Instruct-0905" # Default from s09

pipeline_dir = Path("data/results/verify_quality_02")
db_path = pipeline_dir / "pipeline.duckdb"

print(f"Running S08 (Requirements) on {db_path}...")
# This will call LLM to extract requirements and Insert into DB
num_reqs = run_extract_requirements(pipeline_dir, db_path)
print(f"S08 Extracted {num_reqs} requirements.")

print(f"Running S10 (Markdown Export)...")
md_file = run_s10(db_path, pipeline_dir)
print(f"S10 Exported to {md_file}")

# Copy to brain for easy viewing
brain_dir = Path("/home/graham/.gemini/antigravity/brain/e798a01e-b43d-4bf8-8404-0a8308348507")
dest = brain_dir / "walkthrough.md.resolved"
if md_file and md_file.exists():
    shutil.copy(md_file, dest)
    print(f"Copied to {dest}")
else:
    print("Export failed.")
