import asyncio
from pathlib import Path
from extractor.pipeline.steps import s04_section_builder

# Mock paths
json_in = Path("data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json")
pdf_dir = Path("data/results/pipeline/01_annotation_processor")
out_dir = Path("data/results/pipeline/04_section_builder_debug")


async def run_debug():
    print("Running S04 Debug...")
    res_path, res_data = await s04_section_builder.build_and_validate_sections_comprehensive(
        json_in, Path("tools/tasks_loop/fixtures/tricky_twin/tricky_twin.pdf"), out_dir
    )

    print("\nResult Sections:", len(res_data["sections"]))
    for s in res_data["sections"]:
        print(f"- {s.get('title')} (Blocks: {len(s.get('blocks',[]))})")
        # Check for REQ-CRIT
        dump = str(s)
        if "REQ-CRIT" in dump:
            print("  *** FOUND REQ-CRIT ***")
        else:
            print("  [MISSING REQ-CRIT]")


if __name__ == "__main__":
    asyncio.run(run_debug())
