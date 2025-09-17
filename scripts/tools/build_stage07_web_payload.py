#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

ROOT = Path.cwd()
RESULTS_04 = ROOT / "data/results/pipeline/04_section_builder/json_output/04_sections.json"
GOLD_04 = ROOT / "data/gold_standards/pipeline/004_section_builder_gs.json"
RESULTS_05 = ROOT / "data/results/pipeline/05_table_extractor/json_output/05_tables.json"
GOLD_05 = ROOT / "data/gold_standards/pipeline/005_table_extractor_gs.json"
RESULTS_06 = ROOT / "data/results/pipeline/06_figure_extractor/json_output/06_figures.json"
GOLD_06 = ROOT / "data/gold_standards/pipeline/006_figure_extractor_gs.json"


def choose_section(payload: dict) -> dict:
    secs = (payload or {}).get("sections") or []
    if not secs:
        raise SystemExit("No sections available to build payload")
    return secs[0]


def section_json_for_prompt(sec: dict) -> dict:
    out: dict = {
        "id": sec.get("id"),
        "title": sec.get("title"),
        "level": sec.get("level"),
        "page_start": sec.get("page_start"),
        "page_end": sec.get("page_end"),
    }
    md = sec.get("metadata") or {}
    if isinstance(md, dict):
        out["metadata"] = {
            k: md.get(k)
            for k in ("section_number", "section_hash")
            if k in md
        }
    # Keep blocks minimal: only text, first N
    blocks = sec.get("blocks") or []
    simple_blocks = []
    for b in blocks[:20]:
        if isinstance(b, dict) and b.get("text"):
            simple_blocks.append({"text": str(b.get("text"))[:1000]})
    out["blocks"] = simple_blocks
    return out


def find_section_image(sec: dict) -> Path | None:
    out_dir = ROOT / "data/results/pipeline/04_section_builder/image_output"
    candidates: list[Path] = []
    sid = sec.get("id")
    if isinstance(sid, str) and sid:
        # Common patterns
        candidates.append(out_dir / f"{sid}.png")
        candidates.append(out_dir / f"section_{sid}.png")
    # Common defaults
    candidates.append(out_dir / "sec_0001.png")
    # visual_path relative to results root
    vp = sec.get("visual_path") or sec.get("image_path")
    if isinstance(vp, str):
        # Try resolving relative to repo root and results root
        candidates.append((ROOT / vp).resolve())
        candidates.append((ROOT / "data/results/pipeline" / vp).resolve())
    for c in candidates:
        if c.exists():
            return c
    # Fallback: choose first PNG in image_output
    try:
        for p in sorted(out_dir.glob("*.png")):
            return p
    except Exception:
        pass
    return None


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)

    # Load pre-step07 JSON (prefer real results; fallback to gold sample)
    if RESULTS_04.exists():
        payload = json.loads(RESULTS_04.read_text(encoding="utf-8"))
    else:
        gold = json.loads(GOLD_04.read_text(encoding="utf-8"))
        payload = gold.get("sample") or {}

    sec = choose_section(payload)
    sec_json = section_json_for_prompt(sec)
    img_path = find_section_image(sec)

    # Load tables and figures; prefer real results, fallback to gold samples
    tables_payload = {}
    if RESULTS_05.exists():
        try:
            tables_payload = json.loads(RESULTS_05.read_text(encoding="utf-8"))
        except Exception:
            tables_payload = {}
    if not tables_payload and GOLD_05.exists():
        try:
            tables_payload = json.loads(GOLD_05.read_text(encoding="utf-8"))
            tables_payload = tables_payload.get("sample") or tables_payload
        except Exception:
            tables_payload = {}

    figures_payload = {}
    if RESULTS_06.exists():
        try:
            figures_payload = json.loads(RESULTS_06.read_text(encoding="utf-8"))
        except Exception:
            figures_payload = {}
    if not figures_payload and GOLD_06.exists():
        try:
            figures_payload = json.loads(GOLD_06.read_text(encoding="utf-8"))
            figures_payload = figures_payload.get("sample") or figures_payload
        except Exception:
            figures_payload = {}

    # Build compact snippets for the chosen section (first N)
    sec_id = sec.get("id")

    def table_snippets(max_items: int = 2) -> list[dict]:
        items = []
        for t in (tables_payload.get("tables") or [])[:50]:
            if sec_id and t.get("section_id") and t.get("section_id") != sec_id:
                continue
            pm = t.get("pandas_metrics") or {}
            snippet = {
                "page_index": t.get("page_index"),
                "table_index": t.get("table_index"),
                "pandas_metrics": {
                    "columns": pm.get("columns"),
                    "shape": pm.get("shape"),
                    "data_density": pm.get("data_density"),
                },
                "pandas_df": (t.get("pandas_df") or [])[:3],
                "table_image_path": t.get("table_image_path") or t.get("image_path"),
            }
            items.append(snippet)
            if len(items) >= max_items:
                break
        return items

    def figure_snippets(max_items: int = 2) -> list[dict]:
        items = []
        for f in (figures_payload.get("figures") or [])[:50]:
            if sec_id and f.get("section_id") and f.get("section_id") != sec_id:
                continue
            items.append({
                "figure_id": f.get("figure_id"),
                "page": f.get("page"),
                "image_path": f.get("image_path"),
                "bbox": f.get("bbox"),
                "ai_description": f.get("ai_description"),
                "section_id": f.get("section_id"),
            })
            if len(items) >= max_items:
                break
        return items

    tables_json = table_snippets()
    figures_json = figure_snippets()

    guard = "Return ONLY a well-formed JSON object. No prose, no code fences, no extra keys."
    user_text = (
        f"Image Path: {str(img_path) if img_path else '<no-image-found>'}\n\n"
        "Task\n"
        "- Reflow this SECTION JSON into output JSON. Keep tables unchanged if present; otherwise produce a clean text reflow. Be concise.\n\n"
        "Expected JSON keys\n"
        "- reflowed_json: object\n"
        "- ocr_corrections: object\n"
        "- improvements_made: string\n"
        "- summary: string\n\n"
        "Section JSON\n"
        "```json\n"
        f"{json.dumps(sec_json, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        + (
            "Tables JSON (subset)\n```json\n"
            + json.dumps(tables_json, ensure_ascii=False, indent=2)
            + "\n```\n\n"
            if tables_json
            else ""
        )
        + (
            "Figures JSON (subset)\n```json\n"
            + json.dumps(figures_json, ensure_ascii=False, indent=2)
            + "\n```\n\n"
            if figures_json
            else ""
        )
        + (
            "Image\n"
            "- The client attaches a single image_url part built from the local path at runtime using the helper below.\n"
            f"- Placeholder: {str(img_path) if img_path else '<no-image-found>'}\n\n"
            "Helper (client-side; do not execute in model)\n"
            "Python:\n"
            "def to_data_url(path: str) -> str:\n"
            "    import base64, mimetypes\n"
            "    with open(path, 'rb') as f:\n"
            "        b64 = base64.b64encode(f.read()).decode('ascii')\n"
            "    mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'\n"
            "    return f'data:{mime};base64,{b64}'\n"
        )
    )

    # Build an API-style payload with placeholders for image data URL
    messages = [
        {"role": "system", "content": guard},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                # Replace `{{DATA_URL}}` at runtime using the helper; do not embed base64 here
                *(
                    [{
                        "type": "image_url",
                        "image_url": {"url": "{{DATA_URL}}"},
                        "note": f"Build with to_data_url('{str(img_path)}')"
                    }] if img_path else []
                ),
            ],
        },
    ]

    artifacts = ROOT / "scripts/artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Write web prompt (for copy/paste + attach image)
    (artifacts / "stage07_web_prompt.txt").write_text(
        f"System:\n{guard}\n\nUser:\n{user_text}\n\nAttach image: {str(img_path) if img_path else '<none>'}\n",
        encoding="utf-8",
    )

    # Write API-style messages with placeholder
    (artifacts / "stage07_web_messages.json").write_text(
        json.dumps({
            "model": "gemini/gemini-2.5-flash",
            "messages": messages,
            "notes": {
                "image_path": str(img_path) if img_path else None,
                "data_url_placeholder": "{{DATA_URL}}",
                "how_to_build": "Use to_data_url(image_path) and replace in image_url.url before sending.",
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Wrote:")
    print(" - scripts/artifacts/stage07_web_prompt.txt")
    print(" - scripts/artifacts/stage07_web_messages.json")


if __name__ == "__main__":
    main()
