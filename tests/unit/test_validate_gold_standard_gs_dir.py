import os
import sys
from pathlib import Path

# Ensure 'src' is importable
sys.path.insert(0, os.path.abspath("src"))


def test_gs_dir_points_to_pipeline_dir():
    from extractor.pipeline.tools import validate_gold_standard as vgs

    gs_dir = vgs._gs_dir()
    assert isinstance(gs_dir, Path)
    assert gs_dir.exists(), f"gold standards dir missing: {gs_dir}"

    # For each known stage file, ensure it exists in gs_dir
    for stage, fname in vgs.STAGE_TO_GS.items():
        path = gs_dir / fname
        assert path.exists(), f"missing gold file for stage {stage}: {fname}"
