
from pathlib import Path
from extractor.pipeline.steps.s05_table_extractor import run

input_json = Path("data/results/verify_quality_02/01_annotation_processor/json_output/01_annotations.json")
# If that doesn't exist, we might need a fake one or point to 04 sections?
# S05 signature: def run(input_json: Path, pdf_dir: Path=..., output_dir: Path=...)
# It reads input_json to find "clean_pdf" or "source_pdf".

# Let's check if input exists
if not input_json.exists():
    print(f"Wait, {input_json} missing. Trying 04 sections?")
    input_json = Path("data/results/verify_quality_02/json_output/04_sections.json")

print(f"Running S05 on {input_json}")
out = run(
    input_json=input_json, 
    pdf_dir=Path("data/results/verify_quality_02/01_annotation_processor"),
    output_dir=Path("data/results/verify_quality_02")
)
print(f"Output: {out}")
