#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
import os
import sys
import base64
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 07 vision via adapter (3 images)")


def _load_stage01():
    p = Path("src/extractor/pipeline/steps/01_annotation_processor.py").resolve()
    spec = importlib.util.spec_from_file_location("stage01", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 01 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _to_data_url(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:image/png;base64,{b64}"


@app.command()
def main(
    input_pdf: Path = typer.Option(
        Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
        exists=True,
        help="Fixture PDF",
    ),
    model: str = typer.Option(
        os.getenv(
            "LITELLM_DEFAULT_MODEL",
            os.getenv("DEFAULT_LITELLM_MODEL", "gemini/gemini-2.5-flash"),
        ),
        help="Model",
    ),
    prompt_version: str = typer.Option("reflow@0.1.0"),
    timeout: int = typer.Option(60),
):
    try:
        # Load API keys from .env if present
        load_dotenv(find_dotenv())
        sys.path.insert(0, os.path.abspath("src"))
        from llm_adapter.adapter import LLMAdapter  # type: ignore

        mod = _load_stage01()
        Config = getattr(mod, "Config")
        stage_dir = Path("data/results/pipeline/smokes/01_annotation_processor")
        stage_dir.mkdir(parents=True, exist_ok=True)
        cfg = Config(
            input_pdf=input_pdf,
            output_dir=stage_dir,
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
        annots = extract_annotations_data(input_pdf, cfg)
        if not annots:
            raise RuntimeError("No annotations found")

        # Heuristic selection: 1 section-like + 2 table-like
        section_img = None
        table_imgs = []
        for a in annots:
            img = a.get("image_path")
            if not img:
                continue
            cf = a.get("computed_features") or {}
            vs = a.get("validator_suggestion") or {}
            if section_img is None and (vs.get("type") == "section_header" or cf.get("has_numbering") is True):
                section_img = Path(img)
                continue
            if len(table_imgs) < 2 and (vs.get("type") == "table_region" or cf.get("gridlines_detected") is True):
                table_imgs.append(Path(img))
            if section_img and len(table_imgs) >= 2:
                break
        if section_img is None:
            section_img = Path(annots[0].get("image_path"))
        while len(table_imgs) < 2:
            for a in annots:
                p = a.get("image_path")
                if p:
                    pp = Path(p)
                    if pp != section_img and pp not in table_imgs:
                        table_imgs.append(pp)
                if len(table_imgs) >= 2:
                    break

        images = [
            {"type": "image_url", "image_url": {"url": _to_data_url(section_img)}},
            {"type": "image_url", "image_url": {"url": _to_data_url(table_imgs[0])}},
            {"type": "image_url", "image_url": {"url": _to_data_url(table_imgs[1])}},
        ]

        guard = (
            "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
            "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
            "Requirements: reflowed_json.blocks must preserve reading order and include: "
            "(a) a single merged table block when tables are fragmented/continued. The table title MUST start with 'INFERRED:'; "
            "(b) a figure block with a non-empty title, short caption, and image_ref when applicable. "
            "Always provide ocr_corrections and improvements_made; include summary."
        )
        context = (
            "Section: 4.1.5.4. BHT (Branch History Table) submodule. Contains 2 related tables. Use the images to infer titles and preserve cell values exactly."
        )
        messages = [{"role": "user", "content": [{"type": "text", "text": f"{guard}\n\n{context}"}, *images]}]

        import asyncio
        adapter = LLMAdapter(logs_root=Path("logs"))
        res = asyncio.run(
            adapter.reflow_section(
                model=model,
                messages=messages,
                prompt_version=prompt_version,
                doc_id="bht",
                section_id="s0",
                request_id="smoke07-vision",
                timeout=timeout,
            )
        )
        if not isinstance(res.reflowed_json, dict) or "blocks" not in res.reflowed_json:
            raise RuntimeError("Missing reflowed_json.blocks")
        typer.echo("OK: Stage 07 vision JSON returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
