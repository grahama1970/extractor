import os
import sys
import base64
from pathlib import Path
import importlib.util
import pytest

# Ensure 'src' is importable
sys.path.insert(0, os.path.abspath("src"))
from llm_adapter.adapter import LLMAdapter


RUN = os.getenv("RUN_S07_VISION_SMOKE") == "1"


def _load_stage01_module():
    file_path = Path("src/extractor/pipeline/steps/s01_annotation_processor.py").resolve()
    assert file_path.exists(), f"Missing Stage 01 script at {file_path}"
    spec = importlib.util.spec_from_file_location("stage01_module", str(file_path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


@pytest.mark.skipif(not RUN, reason="RUN_S07_VISION_SMOKE not set")
@pytest.mark.asyncio
async def test_stage07_vision_adapter_returns_json(tmp_path):
    model = None
    if os.getenv("GEMINI_API_KEY"):
        model = os.getenv("LITELLM_DEFAULT_MODEL", "gemini/gemini-2.5-flash")
    elif os.getenv("OPENAI_API_KEY"):
        model = os.getenv("LITELLM_DEFAULT_MODEL", "openai/gpt-4o-mini")
    else:
        pytest.skip("No provider API key found (GEMINI_API_KEY or OPENAI_API_KEY)")

    # Build real images from Stage 01 annotation crops
    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_marked.pdf").resolve()
    assert pdf_path.exists(), "Fixture PDF missing"
    mod = _load_stage01_module()
    Config = getattr(mod, "Config")
    cfg = Config(
        input_pdf=pdf_path,
        output_dir=tmp_path / "pipeline" / "01_annotation_processor",
        include_freetext=True,
        use_images=False,
        render_dpi=150,
        llm_model="ignore",
        llm_concurrency=1,
        limit_annotations=0,
        max_runtime_seconds=0,
        debug=False,
        cache=False,
    )
    extract_annotations_data = getattr(mod, "extract_annotations_data")
    annots = extract_annotations_data(pdf_path, cfg)
    assert annots, "No annotations found in fixture PDF"

    # Pick one section-like and two table-like annotation images
    section_img = None
    table_imgs = []
    for a in annots:
        cf = a.get("computed_features") or {}
        vs = a.get("validator_suggestion") or {}
        img = a.get("image_path")
        if not img:
            continue
        if (vs.get("type") == "section_header") or (
            cf.get("has_numbering") is True or cf.get("bold_detected_inside") is True
        ):
            if section_img is None:
                section_img = img
                continue
        if (vs.get("type") == "table_region") or (cf.get("gridlines_detected") is True):
            if len(table_imgs) < 2:
                table_imgs.append(img)
        if section_img and len(table_imgs) >= 2:
            break

    # Fallbacks if heuristics were too strict
    if section_img is None:
        section_img = annots[0].get("image_path")
    while len(table_imgs) < 2:
        for a in annots:
            if a.get("image_path") and a.get("image_path") != section_img:
                table_imgs.append(a.get("image_path"))
            if len(table_imgs) >= 2:
                break

    def to_data_url(path: str) -> str:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"

    images = [
        {"type": "image_url", "image_url": {"url": to_data_url(section_img)}},
        {"type": "image_url", "image_url": {"url": to_data_url(table_imgs[0])}},
        {"type": "image_url", "image_url": {"url": to_data_url(table_imgs[1])}},
    ]

    adapter = LLMAdapter(logs_root=tmp_path / "logs")
    guard = (
        "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
        "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
        "Requirements: reflowed_json.blocks must preserve reading order and include: "
        "(a) a single merged table block when tables are fragmented/continued. The table title MUST start with 'INFERRED:'; "
        "(b) a figure block with a non-empty title, short caption, and image_ref when applicable. "
        "Always provide ocr_corrections and improvements_made; include summary."
    )
    context = (
        "Section: 4.1.5.4. BHT (Branch History Table) submodule. Contains 2 related tables. "
        "Use the images to infer titles and preserve cell values exactly."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{guard}\n\n{context}"},
                *images,
            ],
        }
    ]

    result = await adapter.reflow_section(
        model=model,
        messages=messages,
        prompt_version="reflow@0.1.0",
        doc_id="bht",
        section_id="s0",
        request_id="smoke07-vision",
        timeout=45,
    )

    assert isinstance(result.reflowed_json, dict)
    assert "blocks" in result.reflowed_json
