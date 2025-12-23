"""Stage 14 report generator runner."""
import json, os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
def run_report(results_dir: Path = Path("data/results/pipeline")) -> Tuple[Path, Dict[str, Any]]:
    """Pure-Python entry: generate a comprehensive final report from a results directory."""
    global console
    if console is None:
        console = Console()
    console.print(f"[green]Generating final report from results in: {results_dir}[/green]")
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    return asyncio.run(generate_comprehensive_report(results_dir, results_dir))


def _cmd_debug():
    """Debug mode for testing."""
    console.print("[yellow]Debug mode - testing report generation...[/yellow]")

    # Test empty pipeline directory to see error handling
    test_pipeline_dir = Path("test_empty_pipeline")
    test_pipeline_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Testing with empty pipeline dir: {test_pipeline_dir}")

    try:
        # Run report generation with empty directory
        output_path, result = asyncio.run(generate_comprehensive_report(test_pipeline_dir))

        console.print(f"✅ Report generated: {output_path}")
        console.print(f"📊 Quality score: {result.get('overall_quality_score', 0):.2%}")

    except Exception as exc:
        log_stage_error(p.name if 'p' in locals() else 'step', exc, {'context': p.name})
        raise
        console.print(f"❌ Expected behavior - empty pipeline: {e}")

    console.print("\n[cyan]Real usage requires pipeline data from stages 01-07:[/cyan]")
    console.print("  python 08_report_generator.py working pipeline_run/")


def debug_bundle(bundle: Path, output_dir: Path = Path("data/results/pipeline")) -> Tuple[Path, Dict[str, Any]]:
    """Pure-Python debug: materialize provided results and generate the report."""
    stage_output_dir = Path(output_dir)
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(bundle.read_text())
        results_map = data.get("results") if isinstance(data, dict) else None
        if results_map is None and isinstance(data, dict):
            # Treat entire object as the results map
            results_map = data
        if not isinstance(results_map, dict) or not results_map:
            raise ValueError("Bundle must be an object mapping stage names to JSON results, or have 'results' key")
    except Exception as exc:
        log_stage_error(p.name if 'p' in locals() else 'step', exc, {'context': p.name})
        raise
        raise ValueError(f"Failed to load bundle: {e}")

    canonical = {
        "01_annotation_processor": "01_annotations.json",
        "02_marker_extractor": "02_marker_blocks.json",
        "03_suspicious_headers": "03_verified_blocks.json",
        "04_section_builder": "04_sections.json",
        "05_table_extractor": "05_tables.json",
        "06_figure_extractor": "06_figures.json",
        "07_reflow_section": "07_reflowed.json",
        "08_lean4_theorem_prover": "08_theorems.json",
        "09_section_summarizer": "09_summaries.json",
        "10_arangodb_exporter": "10_export_confirmation.json",
        "11_arango_create_graph": "11_graph_confirmation.json",
    }

    # Materialize provided results
    for stage_name, obj in results_map.items():
        stage_dir = stage_output_dir / stage_name / "json_output"
        stage_dir.mkdir(parents=True, exist_ok=True)
        filename = canonical.get(stage_name, f"{stage_name}.json")
        (stage_dir / filename).write_text(json.dumps(obj, indent=2))

    # Generate report using the standard path-based flow
    output_path, result = asyncio.run(generate_comprehensive_report(stage_output_dir, stage_output_dir))
    return output_path, result


if __name__ == "__main__":
    # Tiny, optional entry for convenience. Keeps module import side-effect free.
    try:
        load_dotenv(find_dotenv())
    except Exception as exc:
        log_stage_error(p.name if 'p' in locals() else 'step', exc, {'context': p.name})
        raise
        pass
    import sys
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        from extractor.pipeline.steps.sanity_helper import sanity_run
        # Produce 07 (and earlier) to populate minimal report inputs
        sanity_run("07")
        out, _ = run_report(Path("data/results/pipeline"))
        print(str(out))
        sys.exit(0)
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.14_report_generator [RESULTS_DIR] | --bundle BUNDLE_JSON [OUT_DIR]",
            file=sys.stderr,
        )
        sys.exit(2)
    if argv and argv[0] == "--bundle":
        try:
            bundle = Path(argv[1])
        except IndexError:
            print("--bundle requires a path", file=sys.stderr)
            sys.exit(2)
        out_dir = Path(argv[2]) if len(argv) > 2 else Path("data/results/pipeline")
        out, _ = debug_bundle(bundle, out_dir)
        print(str(out))
    else:
        results_dir = Path(argv[0]) if argv else Path("data/results/pipeline")
        out, _ = run_report(results_dir)
        print(str(out))
