
import asyncio
import os
import shutil
from pathlib import Path

# Import Steps
from extractor.pipeline.steps.s07_duckdb_ingest import run_assemble_corpus
from extractor.pipeline.steps.s08_extract_requirements import run_extract_requirements
from extractor.pipeline.steps.s10_markdown_exporter import run as run_s10

# Config (Clean Environment)
os.environ["SCILLM_API_BASE"] = "http://localhost:8787/v1" # Proven working
os.environ["CERTAINLY_BRIDGE_BASE"] = "http://127.0.0.1:8787"
os.environ["SCILLM_API_KEY"] = "sk-placeholder"
os.environ["CHUTES_TEXT_MODEL"] = "moonshotai/Kimi-K2-Instruct-0905"
os.environ["STAGE05_DEMOTE_TEXT_TABLES"] = "1"
# User requested line_scale=15 (Default). Removing override of 40.
os.environ["TABLE_MULTI_PAGE_MERGE_ENABLED"] = "1"

pipeline_dir = Path("data/results/pipeline")
db_path = pipeline_dir / "pipeline.duckdb"

# Artifact Paths
json_dir = pipeline_dir
s04_json = json_dir / "04_section_builder/json_output/04_sections.json"
s05_json = json_dir / "05_table_extractor/json_output/05_tables.json"
s06_json = json_dir / "06_figure_extractor/json_output/06_figures.json"


def main():
    from extractor.pipeline.run_pipeline import clean_step_artifacts
    
    # Run S05c Merger
    from extractor.pipeline.steps.s05c_table_merger import run as run_s05c
    print(">>> 1b. Running S05c (Table Merger)...")
    
    # Hygiene: Clean artifacts for 05c (and implicitly downstream)
    clean_step_artifacts("05c_table_merger", pipeline_dir)
    
    s05c_out_file = run_s05c(pipeline_dir, pipeline_dir) # reads 05_tables.json, writes 05c_tables.json
    
    print(">>> 1c. Running S07 (Ingest fixed artifacts)...")
    try:
        run_assemble_corpus(
            results_db_path=db_path,
            sections_json=s04_json,
            tables_json=s05c_out_file, # Use merged tables
            figures_json=s06_json
        )
    except Exception as e:
        print(f"S07 Failed: {e}")
        return

    print(">>> 2. Running S08 (Extract & Prove Requirements)...")
    try:
        # This calls both Miner and Prover inside s08_extract_requirements (if configured)?
        # Wait, s08_extract_requirements only does MINING.
        # s08_lean4_theorem_prover does PROVING.
        # But we want to use the miner to populate requirements first.
        # The 'run' function in s08_extract_requirements handles mining.
        count = run_extract_requirements(pipeline_dir, db_path)
        print(f"Extracted {count} requirements.")
        
        # Now run Prover (Optional but desired for verification)
        # Import dynamically to avoid issues if files changed
        from extractor.pipeline.steps.s08_lean4_theorem_prover import prove_requirements
        from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
        
        # We patched the validator so this should pass
        # require_scillm_preflight() 
        # Actually, let's skip preflight in this script to be safe, prove_requirements calls it anyway?
        # No, prove_requirements calls it.
        # Let's just run it.
        
        asyncio.run(prove_requirements(db_path, pipeline_dir / "08_lean4_theorem_prover"))
        
    except Exception as e:
        print(f"S08 Failed: {e}")
        # Proceed to Export regardless? No, proving might have failed, but we want the text.

    print(">>> 3. Running S10 (Markdown Export)...")
    try:
        md_file = run_s10(db_path, pipeline_dir)
        print(f"Exported to {md_file}")
        
        # Copy to brain
        brain_dir = Path("/home/graham/.gemini/antigravity/brain/e798a01e-b43d-4bf8-8404-0a8308348507")
        dest = brain_dir / "walkthrough.md.resolved"
        if md_file and md_file.exists():
            shutil.copy(md_file, dest)
            print(f"Copied to {dest}")
            
    except Exception as e:
        print(f"S10 Failed: {e}")

if __name__ == "__main__":
    main()
