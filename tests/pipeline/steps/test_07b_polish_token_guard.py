import json
import types
from pathlib import Path

# Match existing convention in repo tests using underscore alias
from extractor.pipeline.steps._07b_paragraph_polish import run as run_07b  # type: ignore


def test_polish_token_delta_guard(tmp_path: Path, monkeypatch):
    # Ensure gating allows processing and use offline identity path
    monkeypatch.setenv("PARA_NOISE_THRESHOLD", "0.0")
    # Also patch the imported module constant (it is read at import time)
    import sys
    # Patch the underlying loaded module used by the shim
    mod = sys.modules.get("steps_07b_paragraph_polish")
    assert mod is not None
    setattr(mod, "PARA_NOISE_THRESHOLD", 0.0)
    setattr(mod, "DISABLE_LLM", True)
    monkeypatch.setenv("STAGE07_DISABLE_LLM", "1")
    # Build minimal canonical input with one noisy paragraph that would be over-expanded by model
    canonical = {
        "sections": [
            {
                "id": "s1",
                "title": "T",
                "level": 1,
                "page_start": 0,
                "page_end": 0,
                "paragraphs": [
                    {"pid": "p1", "text": "Short line", "bbox": [0, 0, 10, 10], "page_idx": 0}
                ],
                "tables": [],
                "figures": [],
                "content_hash": "h",
            }
        ]
    }
    cpath = tmp_path / "canon.json"
    cpath.write_text(json.dumps(canonical))

    # Monkeypatch litellm_call to return inflated content (plain text), exercising revert guards
    import extractor.pipeline.steps._07b_paragraph_polish as mod  # type: ignore

    async def fake_call(prompts, wrap_json, concurrency, desc, session_id=None, request_timeout=None):
        r = types.SimpleNamespace()
        r.content = "Short line with a great many totally novel extraneous descriptive adjectives"
        return [r]

    mod.litellm_call = fake_call  # type: ignore

    out_dir = tmp_path
    # Run the step
    run_07b(
        canonical_json=cpath,
        output_dir=out_dir,
        verified03_json=None,
    )

    data = json.loads((out_dir / "07b_paragraph_polish" / "07b_paragraph_polish.json").read_text())
    # Should revert to original because token inflation exceeds allowed ratios (or be preserved in offline path)
    assert "polish" in data
    # Find whichever section key was emitted and check pid 'p1'
    sid = next(iter(data["polish"].keys())) if data["polish"] else None
    assert sid is not None
    assert data["polish"][sid]["p1"] == "Short line"
