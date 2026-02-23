#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import math
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore


def b64_image(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    raw = path.read_bytes()
    if Image is not None:
        try:
            img = Image.open(BytesIO(raw))
            buf = BytesIO()
            img.save(buf, format="PNG")
            raw = buf.getvalue()
        except Exception:
            pass
    return base64.b64encode(raw).decode("utf-8")


def sanitize_text(s: str) -> str:
    if not s:
        return s
    removals = [
        "\u200e",
        "\u200f",  # LRM/RLM
        "\u200b",
        "\u200c",
        "\u200d",  # zero-width
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",  # bidi overrides
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",  # isolates
    ]
    for ch in removals:
        s = s.replace(ch, "")
    s = s.replace("\u00a0", " ")  # NBSP -> space
    s = "\n".join(" ".join(line.split()) for line in s.splitlines())
    return s.strip()


def sanitize_obj(obj: Any, *, max_string: int = 20000) -> Any:
    drop_keys = {
        "polygons",
        "polygon",
        "points",
        "mask",
        "glyphs",
        "glyph",
        "bitmap",
        "image_data",
        "image_bytes",
        "data_url",
        "base64",
        "pix",
        "chars",
    }
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).lower() in drop_keys:
                continue
            out[k] = sanitize_obj(v, max_string=max_string)
        return out
    if isinstance(obj, list):
        return [sanitize_obj(x, max_string=max_string) for x in obj]
    if isinstance(obj, str):
        s = sanitize_text(obj)
        if len(s) > max_string:
            s = s[:max_string] + " …(truncated)"
        return s
    return obj


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_encoding(model: str):
    try:
        if tiktoken is None:
            return None
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base") if tiktoken else None
        except Exception:
            return None


def approx_text_tokens(text: str, model: str) -> int:
    if not text:
        return 0
    enc = _get_encoding(model)
    if enc is None:
        return max(1, int(len(text) / 4))
    try:
        return len(enc.encode(text))
    except Exception:
        return max(1, int(len(text) / 4))


def approx_image_tokens(width: int, height: int, *, tokens_per_patch: int = 4) -> int:
    patches = math.ceil(width / 16) * math.ceil(height / 16)
    return max(patches * tokens_per_patch, 64)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="data/results/pipeline", help="Pipeline results base dir")
    ap.add_argument(
        "--out", default="tests/stage07_manual", help="Output directory for payload files"
    )
    ap.add_argument(
        "--auto-triage",
        action="store_true",
        help="If over model token budget, write trimmed variants",
    )
    ap.add_argument(
        "--headroom", type=int, default=1024, help="Reserved tokens for response/overhead"
    )
    ap.add_argument(
        "--model",
        default=None,
        help="Model name for token estimation (default env/openai/gpt-5-mini)",
    )
    ap.add_argument(
        "--compact", action="store_true", help="Build a compact prompt (no heavy blocks)"
    )
    ap.add_argument(
        "--table-confidence-threshold",
        type=float,
        default=0.6,
        help="Threshold below which a table image is attached",
    )
    ap.add_argument(
        "--max-table-rows", type=int, default=20, help="Max rows per high-confidence table to embed"
    )
    ap.add_argument(
        "--include-figures",
        action="store_true",
        help="Include figure images (off by default in compact)",
    )
    ap.add_argument(
        "--include-annotations",
        action="store_true",
        help="Include annotation images (off by default)",
    )
    ap.set_defaults(compact=True)
    args = ap.parse_args()

    results = Path(args.results)
    outdir = Path(args.out)
    (outdir / "images").mkdir(parents=True, exist_ok=True)

    # Load pipeline outputs
    sections = load_json(results / "04_section_builder" / "json_output" / "04_sections.json")
    tables = load_json(results / "05_table_extractor" / "json_output" / "05_tables.json")
    figures = load_json(results / "06_figure_extractor" / "json_output" / "06_figures.json")

    sec_list = sections.get("sections") or sections.get("result", {}).get("sections") or []
    section = sec_list[0] if sec_list else {}
    title = section.get("display_title") or section.get("title") or "Untitled"

    raw_text = (
        section.get("merged_text") or section.get("source_text") or section.get("raw_text") or ""
    )
    if not raw_text:
        lines: List[str] = []
        for b in section.get("blocks", []) or []:
            t = str(b.get("text") or "").strip()
            if t:
                lines.append(t)
        raw_text = "\n\n".join(lines)
    raw_text = sanitize_text(raw_text)

    visual_path_rel = section.get("metadata", {}).get("visual_path") or section.get("visual_path")
    section_img_path = (results / visual_path_rel) if visual_path_rel else None

    table_list = tables.get("tables") or tables.get("result", {}).get("tables") or []
    fig_list = figures.get("figures") or figures.get("result", {}).get("figures") or []

    # Load annotations relevant to section page range
    annotations: List[Dict[str, Any]] = []
    ann_json = results / "01_annotation_processor" / "json_output" / "01_annotations.json"
    if ann_json.exists():
        ann_data = load_json(ann_json)
        anns = ann_data.get("annotations") or []
        p0 = int(section.get("page_start", 0))
        p1 = int(section.get("page_end", p0))
        annotations = [a for a in anns if p0 <= int(a.get("page", -1)) <= p1]

    # Heuristic table confidence
    def table_confidence(t: Dict[str, Any]) -> float:
        pm = t.get("pandas_metrics") or {}
        try:
            shape = pm.get("shape") or [0, 0]
            rows, _ = int(shape[0] or 0), int(shape[1] or 0)
        except Exception:
            rows = 0
        density = float(pm.get("data_density") or 0.0)
        camel = t.get("camelot_metrics") or {}
        acc = float(camel.get("accuracy") or 0.0)
        white = float(camel.get("whitespace") or 0.0)
        score = 0.0
        score += 0.2 if rows >= 3 else 0.0
        score += min(max(density, 0.0), 1.0) * 0.4
        score += min(max(acc / 100.0, 0.0), 1.0) * 0.4
        score -= min(max(white / 100.0, 0.0), 1.0) * 0.1
        return max(0.0, min(1.0, score))

    # Build concise context text
    ctx_lines: List[str] = []
    ctx_lines.append(f"Section: {title}")
    ctx_lines.append("")
    if table_list:
        t0 = table_list[0]
        shape = (t0.get("pandas_metrics") or {}).get("shape") or []
        cols = (t0.get("pandas_metrics") or {}).get("columns") or []
        ctx_lines.append("Table summary:")
        ctx_lines.append(f"Shape: {tuple(shape)} columns: {', '.join(map(str, cols))}")
        ctx_lines.append("")

    # Relevant annotations snippets (up to 2)
    ann_texts: List[str] = []
    for a in annotations:
        snippet = ""
        for blk in (a.get("inside_blocks") or [])[:1]:
            for ln in (blk.get("lines") or [])[:1]:
                for sp in (ln.get("spans") or [])[:1]:
                    t = str(sp.get("text") or "").strip()
                    if t:
                        snippet = sanitize_text(t)
                        break
                if snippet:
                    break
            if snippet:
                break
        if snippet:
            ann_texts.append(snippet)
    if ann_texts:
        ctx_lines.append("Relevant annotations:")
        for t in ann_texts[:2]:
            ctx_lines.append(f"- {t}")
        ctx_lines.append("")

    # Section JSON summary
    sec_summary = {
        "id": section.get("id"),
        "title": title,
        "level": section.get("level"),
        "page_start": section.get("page_start"),
        "page_end": section.get("page_end", section.get("page_start")),
        "section_number": (section.get("metadata") or {}).get("section_number")
        or section.get("section_number"),
        "section_hash": (section.get("metadata") or {}).get("section_hash")
        or section.get("section_hash"),
        "blocks_count": len(section.get("blocks", [])),
    }
    ctx_lines.append("\nSection JSON Summary:")
    ctx_lines.append(json.dumps(sec_summary, ensure_ascii=False, indent=2))
    context_text = "\n".join(ctx_lines)
    (outdir / "context_text.txt").write_text(context_text, encoding="utf-8")

    # Images: always section; low-confidence tables; optional figures/annotations
    payload_images: List[Path] = []
    payload_meta: List[Dict[str, Any]] = []
    if section_img_path and section_img_path.exists():
        dst = outdir / "images" / "section.png"
        dst.write_bytes(section_img_path.read_bytes())
        payload_images.append(dst)
        payload_meta.append(
            {"order": len(payload_meta) + 1, "kind": "section", "filename": f"images/{dst.name}"}
        )

    tdir = outdir / "images"
    t_idx = 1
    for t in table_list:
        rel = t.get("table_image_path")
        if not rel:
            continue
        src = results / rel
        if src.exists() and table_confidence(t) < float(args.table_confidence_threshold):
            dst = tdir / f"table{t_idx}.png"
            dst.write_bytes(src.read_bytes())
            payload_images.append(dst)
            payload_meta.append(
                {
                    "order": len(payload_meta) + 1,
                    "kind": "table",
                    "filename": f"images/{dst.name}",
                    "table_index": t_idx,
                    "confidence": round(table_confidence(t), 3),
                }
            )
        t_idx += 1

    if args.include_figures or not args.compact:
        f_idx = 1
        for f in fig_list:
            rel = f.get("image_path")
            if not rel:
                continue
            src = results / rel
            if src.exists():
                dst = tdir / f"figure{f_idx}.png"
                dst.write_bytes(src.read_bytes())
                payload_images.append(dst)
                payload_meta.append(
                    {
                        "order": len(payload_meta) + 1,
                        "kind": "figure",
                        "filename": f"images/{dst.name}",
                        "figure_index": f_idx,
                    }
                )
                f_idx += 1

    # Include up to 2 annotation images if requested
    if args.include_annotations and annotations:
        a_idx = 1
        for a in annotations:
            if a_idx > 2:
                break
            rel = a.get("image_path")
            if not rel:
                continue
            src = Path(rel)
            if not src.is_absolute():
                src = results / "01_annotation_processor" / "visual_output" / src.name
            if src.exists():
                dst = tdir / f"annotation{a_idx}.png"
                dst.write_bytes(src.read_bytes())
                payload_images.append(dst)
                payload_meta.append(
                    {
                        "order": len(payload_meta) + 1,
                        "kind": "annotation",
                        "filename": f"images/{dst.name}",
                        "annotation_index": a_idx,
                    }
                )
                a_idx += 1

    # Enrich images manifest with sizes and token estimates
    def _image_info(p: Path) -> Dict[str, Any]:
        info: Dict[str, Any] = {"filename": f"images/{p.name}", "bytes": p.stat().st_size}
        if Image is not None:
            try:
                im = Image.open(p)
                w, h = im.size
                info.update(
                    {
                        "width": w,
                        "height": h,
                        "pixels": w * h,
                        "megapixels": round((w * h) / 1_000_000, 2),
                        "approx_tokens": approx_image_tokens(w, h),
                    }
                )
            except Exception:
                info.update({"approx_tokens": 64})
        else:
            info.update({"approx_tokens": 64})
        return info

    for meta, p in zip(payload_meta, payload_images):
        meta.update(_image_info(p))
    (outdir / "images_manifest.json").write_text(
        json.dumps({"images": payload_meta}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Token estimate
    import os as _os

    model_name = args.model or (
        _os.getenv("LITELLM_VLM_MODEL") or _os.getenv("LITELLM_MODEL") or "openai/gpt-5-mini"
    )
    sec_sanitized = sanitize_obj(section)
    section_full_sanitized = json.dumps(sec_sanitized, ensure_ascii=False, indent=2)
    (outdir / "section_full_sanitized.json").write_text(section_full_sanitized, encoding="utf-8")

    # Tables compact for prompt; full for debug
    tables_compact: List[Dict[str, Any]] = []
    for i, t in enumerate(table_list, start=1):
        pm = t.get("pandas_metrics") or {}
        df_rows = t.get("pandas_df") or []
        cols = list(pm.get("columns") or [])
        if not cols and df_rows:
            keys = list(df_rows[0].keys())
            try:
                cols = sorted(keys, key=lambda k: int(str(k)) if str(k).isdigit() else 9999)
            except Exception:
                cols = keys
        rows: List[List[Any]] = []
        if table_confidence(t) >= float(args.table_confidence_threshold):
            for r in df_rows[: int(args.max_table_rows)]:
                rows.append([r.get(c, None) for c in cols])
        tables_compact.append(
            {"index": i, "columns": cols, "rows": rows, "confidence": round(table_confidence(t), 3)}
        )
    ctx_tables_compact = json.dumps(
        {"tables_compact": tables_compact}, ensure_ascii=False, indent=2
    )

    full_tables_payload = []
    for i, t in enumerate(table_list, start=1):
        pm = t.get("pandas_metrics") or {}
        full_tables_payload.append(
            {
                "index": i,
                "metrics": sanitize_obj(pm, max_string=100000),
                "pandas_df": sanitize_obj(t.get("pandas_df") or [], max_string=100000),
            }
        )
    ctx_tables_full = json.dumps({"tables_full": full_tables_payload}, ensure_ascii=False, indent=2)

    # Token totals
    text_tokens = approx_text_tokens(context_text, model_name) + approx_text_tokens(
        section_full_sanitized, model_name
    )
    image_tokens_total = sum(int(m.get("approx_tokens", 0) or 0) for m in payload_meta)

    def _model_max_tokens(name: str) -> Optional[int]:
        try:
            from litellm import get_max_tokens as _get_max  # type: ignore

            return int(_get_max(name))
        except Exception:
            low = (name or "").lower()
            if "gpt-5" in low and "mini" in low:
                return 400_000
            if "gpt-4o" in low:
                return 128_000
            return None

    model_max = _model_max_tokens(model_name)
    token_report = {
        "model": model_name,
        "model_max_tokens": model_max,
        "context_text_chars": len(context_text),
        "context_text_tokens_est": text_tokens,
        "images": payload_meta,
        "images_total_tokens_est": image_tokens_total,
        "images_total_bytes": sum(m.get("bytes", 0) for m in payload_meta),
        "section_json_chars": len(section_full_sanitized),
        "tables_compact_chars": len(ctx_tables_compact),
    }
    (outdir / "token_estimate.json").write_text(
        json.dumps(token_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Auto-triage images if over budget
    triage_applied = False
    triage_kept: List[Dict[str, Any]] = []
    if args.auto_triage and model_max is not None:
        headroom = int(args.headroom)
        total_est = text_tokens + image_tokens_total
        if total_est + headroom > model_max:
            over_by = (total_est + headroom) - model_max

            def importance_rank(m: Dict[str, Any]) -> int:
                kind = m.get("kind")
                if kind == "annotation":
                    return 5
                if kind == "figure":
                    return 4
                if kind == "table":
                    idx = int(m.get("table_index", 99) or 99)
                    return 3 if idx > 1 else 2
                if kind == "section":
                    return 1
                return 0

            candidates = sorted(
                payload_meta,
                key=lambda m: (importance_rank(m), int(m.get("approx_tokens", 0) or 0)),
                reverse=True,
            )
            removed: List[Dict[str, Any]] = []
            saved = 0
            for m in candidates:
                if saved >= over_by:
                    break
                if m.get("kind") == "section":
                    continue
                removed.append(m)
                saved += int(m.get("approx_tokens", 0) or 0)
            kept = [m for m in payload_meta if m not in removed]

            (outdir / "images_manifest_trimmed.json").write_text(
                json.dumps(
                    {
                        "images": kept,
                        "removed": [m.get("filename") for m in removed],
                        "over_by": over_by,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            # Write trimmed JSON payload variants
            trimmed_input_content: List[Dict[str, Any]] = [
                {"type": "input_text", "text": context_text}
            ]
            for m in kept:
                trimmed_input_content.append(
                    {"type": "input_image", "image_url": f"<attach via UI: {m['filename']}>"}
                )
            responses_payload_trimmed = {
                "model": model_name,
                "temperature": 1.0,
                "max_output_tokens": 1200,
                "response_format": {"type": "json_object"},
                "input": [{"role": "user", "content": trimmed_input_content}],
            }
            (outdir / "responses_input_trimmed.json").write_text(
                json.dumps(responses_payload_trimmed, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            trimmed_messages_content: List[Dict[str, Any]] = [
                {"type": "text", "text": context_text}
            ]
            for m in kept:
                trimmed_messages_content.append(
                    {"type": "image_url", "image_url": {"url": f"<attach via UI: {m['filename']}>"}}
                )
            chat_payload_trimmed = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a technical editor. Reflow input into clean Markdown and return strict JSON with keys: reflowed_text, ocr_corrections, improvements_made, summary.",
                    },
                    {"role": "user", "content": trimmed_messages_content},
                ],
            }
            (outdir / "chat_messages_trimmed.json").write_text(
                json.dumps(chat_payload_trimmed, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            triage_applied = True
            triage_kept = kept

    # Write Responses input and Chat messages (templates; filenames for images)
    input_content: List[Dict[str, Any]] = [{"type": "input_text", "text": context_text}]
    for p in payload_images:
        input_content.append(
            {"type": "input_image", "image_url": f"<attach via UI: images/{p.name}>"}
        )
    responses_payload = {
        "model": "gpt-5-mini",
        "temperature": 1.0,
        "max_output_tokens": 1200,
        "response_format": {"type": "json_object"},
        "input": [{"role": "user", "content": input_content}],
    }
    (outdir / "responses_input.json").write_text(
        json.dumps(responses_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    messages_content: List[Dict[str, Any]] = [{"type": "text", "text": context_text}]
    for p in payload_images:
        messages_content.append(
            {"type": "image_url", "image_url": {"url": f"<attach via UI: images/{p.name}>"}}
        )
    chat_payload = {
        "model": "gpt-5-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a technical editor. Reflow input into clean Markdown and return strict JSON with keys: reflowed_text, ocr_corrections, improvements_made, summary.",
            },
            {"role": "user", "content": messages_content},
        ],
    }
    (outdir / "chat_messages.json").write_text(
        json.dumps(chat_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Web prompts
    system_prompt = (
        "You are a technical reflow engine. Given a PDF-extracted section JSON, compact pandas tables, and a small set of images, output a single reflowed section JSON that merges contiguous content for LLM use and DB storage.\n\n"
        "Core requirements\n"
        "- Merge contiguous text into coherent paragraphs (fix hyphenation, broken words, OCR joins). Remove duplicated headers/footers and page artifacts.\n"
        "- Merge contiguous tables, including those that span pages, into one logical table positioned at the first fragment.\n"
        "- Preserve reading order: top→bottom, left→right, across pages.\n"
        "- Prefer provided pandas/compact tables for content; use images only for context or disambiguation.\n\n"
        "Data Integrity (strict)\n"
        "- Tables: DO NOT change cell content. No spelling corrections, translations, unit changes, rounding, normalization, inference, or reformatting. Keep numeric formats as-is.\n"
        "- Allowed in tables only: remove intra-cell newlines/excess spaces (join without changing character order); flatten multi-row headers by concatenation.\n"
        "- Forbidden in tables: reordering rows/columns, filling blanks, deduping, computing totals.\n"
        "- Text/Headings/Lists: Fix OCR splits/hyphenation and obvious typos only outside tables. Record fixes in ocr_corrections.\n\n"
        "Return ONLY this JSON object (no extra text):\n"
        "{\n"
        '  "section_id": string,\n'
        '  "title": string,\n'
        '  "blocks": [\n'
        '    { "type": "heading", "level": int, "text": string, "source": { "pages": [int], "block_ids": [string] } },\n'
        '    { "type": "paragraph", "text": string, \n'
        '      "source": { "pages": [int], "block_ids": [string] } },\n'
        '    { "type": "list", "style": "bulleted|numbered", "items": [string, ...], \n'
        '      "source": { "pages": [int], "block_ids": [string] } },\n'
        '    { "type": "table", \n'
        '      "title": string | null,\n'
        '      "columns": [string], \n'
        '      "rows": [[string|number|null, ...]], \n'
        '      "confidence": { "status": "high|medium|low", "density": number|null, "source": "camelot+pandas" },\n'
        '      "markdown": string | null, \n'
        '      "markdown_provenance": "image" | null, \n'
        '      "image_refs": [string, ...],\n'
        '      "source": { "table_indices": [int], "page_indices": [int] } },\n'
        '    { "type": "figure", "title": string | null, "caption": string | null, "alt": string, "image_ref": string, \n'
        '      "source": { "pages": [int], "block_ids": [string] } }\n'
        "  ],\n"
        '  "ocr_corrections": { "erroneous": "corrected", ... },\n'
        '  "improvements_made": string,\n'
        '  "summary": string\n'
        "}\n\n"
        "Notes\n"
        '- Tables: build from provided columns+rows; ensure exact cell content; trim whitespace only. Include markdown only if pandas failed or confidence is low, in which case set markdown_provenance="image" and add relevant image_refs.\n'
        "- Use provided titles from 'Titles (tables & figures)'. If none literal, use the INFERRED: title as-is (light rephrasing allowed).\n"
        "- Figures: include a concise caption and set image_ref to the uploaded filename (e.g., images/figure1.png).\n"
        "- Return strict JSON only."
    )

    prompt_lines: List[str] = []
    prompt_lines.append("SYSTEM INSTRUCTIONS:\n")
    prompt_lines.append(system_prompt)
    prompt_lines.append("\n\nUSER CONTENT (paste below and upload the images listed):\n")
    prompt_lines.append(context_text)

    # Compact tables block
    prompt_lines.append("\n\nTables (pandas, compact):\n")
    prompt_lines.append("```json")
    prompt_lines.append(ctx_tables_compact)
    prompt_lines.append("```")

    # Titles (tables & figures)
    def _h_iou(b1: List[float], b2: List[float]) -> float:
        try:
            ax0, ay0, ax1, ay1 = [float(x) for x in b1]
            bx0, by0, bx1, by1 = [float(x) for x in b2]
            inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            uni = max(ax1, bx1) - min(ax0, bx0)
            return float(inter / uni) if uni > 0 else 0.0
        except Exception:
            return 0.0

    def _closest_text(
        blocks: List[Dict[str, Any]],
        page: int,
        target_bbox: List[float],
        direction: str = "above",
        max_gap: float = 50.0,
    ) -> Optional[Dict[str, Any]]:
        best, best_gap = None, 1e9
        for b in blocks or []:
            try:
                if int(b.get("page", b.get("page_idx", -1))) != int(page):
                    continue
                bb = b.get("bbox") or []
                if not bb:
                    continue
                if _h_iou(target_bbox, bb) < 0.2:
                    continue
                gap = None
                if direction == "above" and bb[3] <= target_bbox[1]:
                    gap = target_bbox[1] - bb[3]
                elif direction == "below" and bb[1] >= target_bbox[3]:
                    gap = bb[1] - target_bbox[3]
                if gap is None or gap > max_gap:
                    continue
                if gap < best_gap:
                    best, best_gap = b, gap
            except Exception:
                continue
        return best

    def _btxt(b: Optional[Dict[str, Any]]) -> str:
        return sanitize_text(str((b or {}).get("text") or "").strip())

    sec_blocks = section.get("blocks", []) or []
    tables_titles: List[Dict[str, Any]] = []
    for i, t in enumerate(table_list, start=1):
        title, derived = None, "literal"
        try:
            page = int(t.get("page_index", 0) or 0)
            tb = t.get("bbox") or []
            cand = _closest_text(sec_blocks, page, tb, "above") or _closest_text(
                sec_blocks, page, tb, "below"
            )
            txt = _btxt(cand)
            if txt:
                title = txt
            else:
                cols = (t.get("pandas_metrics") or {}).get("columns") or []
                head = ", ".join(map(str, cols[:3]))
                title, derived = (
                    f"INFERRED: Table - {head}" if head else "INFERRED: Table"
                ), "inferred"
        except Exception:
            title, derived = "INFERRED: Table", "inferred"
        tables_titles.append({"index": i, "title": title, "derived": derived})

    figures_titles: List[Dict[str, Any]] = []
    for j, f in enumerate(fig_list, start=1):
        title, derived = None, "literal"
        try:
            page = int(f.get("page", f.get("page_idx", 0)) or 0)
            fb = f.get("bbox") or []
            cand = _closest_text(sec_blocks, page, fb, "above") or _closest_text(
                sec_blocks, page, fb, "below"
            )
            txt = _btxt(cand)
            if txt:
                title = txt
            else:
                adesc = sanitize_text(str(f.get("ai_description") or ""))
                title, derived = (
                    f"INFERRED: {adesc[:80]}" if adesc else "INFERRED: Figure"
                ), "inferred"
        except Exception:
            title, derived = "INFERRED: Figure", "inferred"
        figures_titles.append({"index": j, "title": title, "derived": derived})

    titles_bundle = {
        "tables_titles": tables_titles,
        "figures_titles": figures_titles,
        "guidance": "Use literal titles when present. If 'INFERRED:' prefix exists, treat as a suggested caption; you may lightly rephrase while preserving meaning.",
    }
    prompt_lines.append("\n\nTitles (tables & figures):\n")
    prompt_lines.append("```json")
    prompt_lines.append(json.dumps(titles_bundle, ensure_ascii=False, indent=2))
    prompt_lines.append("```")

    # Footer and attach list
    prompt_lines.append("\nFull payload files are generated alongside this prompt:")
    prompt_lines.append(" - tests/stage07_manual/responses_input.json")
    prompt_lines.append(" - tests/stage07_manual/chat_messages.json")
    upload_list = [meta["filename"] for meta in payload_meta]
    if upload_list:
        prompt_lines.append("\nAttach these images in the chat UI (do not change filenames):")
        for rel in upload_list:
            prompt_lines.append(f" - {rel}")
    (outdir / "prompt_web.md").write_text("\n".join(prompt_lines), encoding="utf-8")

    # Full debug prompt with heavy blocks appended
    full_lines = list(prompt_lines)
    full_lines.append("\n\nSection JSON (sanitized):\n")
    full_lines.append("```json")
    full_lines.append(section_full_sanitized)
    full_lines.append("```")
    full_lines.append("\n\nTables Full Data (sanitized):\n")
    full_lines.append("```json")
    full_lines.append(ctx_tables_full)
    full_lines.append("```")
    (outdir / "prompt_web_full.md").write_text("\n".join(full_lines), encoding="utf-8")

    # If triage applied, write trimmed prompt variant
    if triage_applied:
        prompt_lines_trim = list(prompt_lines)
        prompt_lines_trim.append("\nTrimmed Attach List (auto-triage applied):")
        for m in triage_kept:
            prompt_lines_trim.append(f" - {m['filename']}")
        (outdir / "prompt_web_trimmed.md").write_text(
            "\n".join(prompt_lines_trim), encoding="utf-8"
        )

    # Relaxed variant (no strict JSON)
    relaxed_sys = (
        "You are a technical editor. Reflow the input into clean Markdown. "
        "Return a JSON object if possible with keys: reflowed_text, ocr_corrections, improvements_made, summary."
    )
    relaxed_lines: List[str] = []
    relaxed_lines.append("SYSTEM INSTRUCTIONS (relaxed):\n")
    relaxed_lines.append(relaxed_sys)
    relaxed_lines.append("\n\nUSER CONTENT:\n")
    relaxed_lines.append(context_text)
    if upload_list:
        relaxed_lines.append("\nAttach these images in the chat UI:")
        for name in upload_list:
            relaxed_lines.append(f" - {name}")
    (outdir / "prompt_web_relaxed.md").write_text("\n".join(relaxed_lines), encoding="utf-8")

    print(f"Wrote payloads to: {outdir}")


if __name__ == "__main__":
    main()
