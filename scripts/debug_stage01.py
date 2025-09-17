import asyncio
import importlib.util
import os
from pathlib import Path


def load_stage_module():
    stage_path = Path("src/extractor/pipeline/steps/01_annotation_processor.py")
    if not stage_path.exists():
        raise FileNotFoundError(f"Stage file not found: {stage_path}")
    spec = importlib.util.spec_from_file_location("stage01", stage_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load stage01 module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def main():
    stage01 = load_stage_module()
    model = os.getenv("LITELLM_DEFAULT_MODEL", os.getenv("DEFAULT_LITELLM_MODEL", "openai/gpt-4o-mini"))
    cfg = stage01.Config(
        input_pdf=Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
        # Align with CLI: write into the stage-specific directory
        output_dir=Path("data/results/pipeline/01_annotation_processor"),
        include_freetext=True,
        use_images=False,   # Flip to True once text-only path is stable
        render_dpi=150,
        llm_model=model,
        llm_concurrency=1,  # Deterministic stepping
        limit_annotations=2,
        max_runtime_seconds=60,
        debug=True,
    )
    asyncio.run(stage01.process_pdf_pipeline(cfg))


if __name__ == "__main__":
    main()
