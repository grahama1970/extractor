#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger


app = typer.Typer(help="07e: Assemble final reflow JSON per section + provenance; write legacy file too.")


@app.command("run")
def run(
    canonical_json: Path = typer.Option(..., "--canonical", exists=True),
    polish_json: Path = typer.Option(..., "--polish", exists=True),
    table_titles_json: Path = typer.Option(..., "--table-titles", exists=True),
    figure_caps_json: Path = typer.Option(..., "--figure-captions", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    base = output_dir
    out_dir = base / "07e_assemble_reflow"
    json_dir = out_dir / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    cano = json.loads(canonical_json.read_text())
    pol = json.loads(polish_json.read_text())
    tt = json.loads(table_titles_json.read_text())
    fc = json.loads(figure_caps_json.read_text())

    polish_map: Dict[str, Dict[str, str]] = pol.get("polish", {})
    title_map: Dict[str, Dict[str, str]] = tt.get("table_titles", {})
    cap_map: Dict[str, Dict[str, str]] = fc.get("figure_captions", {})

    out_sections: List[Dict[str, Any]] = []
    for s in cano.get("sections", []):
        sid = s.get("id")
        # Paragraphs
        blocks: List[Dict[str, Any]] = []
        for p in s.get("paragraphs", []):
            pid = p.get("pid")
            txt = p.get("text") or ""
            pt = (polish_map.get(sid, {}) or {}).get(pid) or txt
            blocks.append({
                "type": "paragraph",
                "text": pt,
                "source": {"pages": [p.get("page")], "block_ids": [pid]},
            })
        # Tables
        for t in s.get("tables", []):
            title_key = t.get("raw_table_id") or t.get("normalized_label") or ""
            title = (title_map.get(sid, {}) or {}).get(title_key) or (t.get("title") or t.get("caption"))
            pm = t.get("pandas_metrics") or {}
            blocks.append({
                "type": "table",
                "title": title,
                "columns": pm.get("columns") or [],
                "rows": t.get("pandas_df") or [],
                "confidence": {"status": "high" if (pm.get("data_density") or 0) >= 0.9 else "medium", "density": pm.get("data_density"), "source": "camelot+pandas"},
                "image_refs": [t.get("table_image_path")] if t.get("table_image_path") else [],
                "source": {"pages": [t.get("page_index")], "block_ids": [t.get("raw_table_id")]},
                "provenance": t.get("provenance") or {},
            })
        # Figures
        for f in s.get("figures", []):
            key = f.get("figure_id") or f.get("image_ref") or ""
            cap = (cap_map.get(sid, {}) or {}).get(key) or (f.get("caption") or f.get("ai_description"))
            blocks.append({
                "type": "figure",
                "title": None,
                "caption": cap,
                "alt": cap or "Figure",
                "image_ref": f.get("image_ref") or f.get("image_path"),
                "source": {"pages": [f.get("page")], "block_ids": [f.get("figure_id") or key]},
            })

        reflow = {
            "title": s.get("title"),
            "blocks": blocks,
        }
        provenance = {
            "content_hash": s.get("content_hash"),
            "paragraphs_total": len(s.get("paragraphs", [])),
            "paragraphs_polished": len(polish_map.get(sid, {}) or {}),
            "tables_total": len(s.get("tables", [])),
            "tables_with_inferred_title": len([1 for v in (title_map.get(sid, {}) or {}).values() if v]),
            "figures_total": len(s.get("figures", [])),
            "figures_caption_refined": len([1 for v in (cap_map.get(sid, {}) or {}).values() if v]),
            "used_section_image": bool(s.get("needs_layout_image")),
        }
        out_sections.append({
            "id": sid,
            "reflowed_json": reflow,
            "ocr_corrections": {},
            "improvements_made": "polish/titles/captions gated",
            "summary": "",
            "metadata": {"parse_strategy": "assemble", "reflow_attempts": 0},
            "provenance": provenance,
        })

    final = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "status": "Completed",
        "section_count": len(out_sections),
        "reflowed_sections": out_sections,
    }
    out_main = json_dir / "07e_reflowed.json"
    out_main.write_text(json.dumps(final, indent=2, ensure_ascii=False))
    # Legacy mirror
    legacy_dir = Path("data/results/pipeline/07_reflow_section/json_output")
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "07_reflowed.json").write_text(json.dumps(final, indent=2, ensure_ascii=False))
    logger.success(f"07e: wrote {out_main} and legacy mirror {legacy_dir / '07_reflowed.json'}")


if __name__ == "__main__":
    app()

