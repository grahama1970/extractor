from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
import textwrap
from typing import Any, Dict, Optional


def format_block_text(block: Optional[Dict[str, Any]]) -> str:
    """Converts a block to text with font summary if available.

    Priority:
    - Use flat 'text' when present (Stage 02 output)
    - Fall back to lines/spans if available
    - Append concise font info from 'first_span_font' when present
    """
    if not block:
        return "N/A (No block found)"

    text_val = (block.get("text") or block.get("content") or "").strip()
    if text_val:
        fsf = block.get("first_span_font") or {}
        if isinstance(fsf, dict) and (fsf.get("name") or fsf.get("size")):
            parts = []
            name = fsf.get("name")
            size = fsf.get("size")
            if name:
                parts.append(str(name))
            if size is not None:
                try:
                    parts.append(f"{float(size):.1f}pt")
                except Exception as exc:
                    log_stage_error('prompt_builder.py', exc, {'context': 'prompt_builder.py'})
                    raise
                    parts.append(str(size))
            if fsf.get("bold"):
                parts.append("bold")
            if fsf.get("italic"):
                parts.append("italic")
            bucket = fsf.get("color_bucket")
            if bucket:
                parts.append(bucket)
            font_str = " ".join(parts)
            if font_str:
                return f"{text_val}\n[font: {font_str}]"
        return text_val

    # Fallback to lines/spans (legacy shape)
    lines_text = []
    for line in block.get("lines", []) or []:
        line_str = ""
        for span in line.get("spans", []) or []:
            t = span.get("text", "")
            fs = span.get("font_style", {})
            fname = fs.get("font_name", "Unknown")
            fsize = fs.get("font_size", "N/A")
            line_str += f"{t} (Font: {fname}, Size: {fsize}) "
        if line_str.strip():
            lines_text.append(line_str.strip())
    return "\n".join(lines_text) if lines_text else "N/A (Block is empty)"


def _signals(b: Optional[Dict[str, Any]]) -> str:
    if not b:
        return ""
    fsf = b.get("first_span_font") or {}
    name = fsf.get("name")
    size = fsf.get("size")
    bucket = fsf.get("color_bucket")
    bold = fsf.get("bold")
    italic = fsf.get("italic")
    surya = b.get("surya_confidence")
    susp = b.get("suspicion_confidence")
    quality = b.get("quality_score")
    parts = []
    if name:
        parts.append(f"font={name}")
    if size is not None:
        try:
            parts.append(f"size={float(size):.1f}pt")
        except Exception as exc:
            log_stage_error('prompt_builder.py', exc, {'context': 'prompt_builder.py'})
            raise
            parts.append(f"size={size}")
    if bucket:
        parts.append(f"color={bucket}")
    if bold:
        parts.append("bold")
    if italic:
        parts.append("italic")
    if isinstance(surya, (int, float)):
        parts.append(f"surya={float(surya):.2f}")
    if isinstance(susp, (int, float)):
        parts.append(f"suspicion={float(susp):.2f}")
    if isinstance(quality, (int, float)):
        parts.append(f"quality={float(quality):.2f}")
    return ", ".join(parts)


def build_llm_context(
    target_block: Dict[str, Any],
    above_block: Optional[Dict[str, Any]],
    below_block: Optional[Dict[str, Any]],
    human_annotations_summary: Optional[str] = None,
) -> str:
    target_text = format_block_text(target_block)
    above_text = format_block_text(above_block)
    below_text = format_block_text(below_block)

    tgt_sig = _signals(target_block)
    abv_sig = _signals(above_block)
    bel_sig = _signals(below_block)

    base = textwrap.dedent(
        f"""
    Please analyze the following content. The 'Block in Question' was identified as a SectionHeader but its characteristics are suspicious.

    === Text CONTEXT Directly Above ===
    {above_text}
    Signals: {abv_sig}

    === Block in Question (Candidate Header) ===
    Block Type: {target_block.get('block_type', 'N/A')}
    Text:
    {target_text}
    Signals: {tgt_sig}

    === Text CONTEXT Directly Below ===
    {below_text}
    Signals: {bel_sig}

    Based on the image and this text, is the 'Block in Question' a true section header?
    """
    ).strip()

    if human_annotations_summary:
        base += (
            "\n\n"
            + textwrap.dedent(
                f"""
        === Human Annotations Near This Text ===
        {human_annotations_summary}

        Treat explicit negative cues (e.g., "NOT a section header") as high-confidence constraints unless clearly contradicted by layout and content.
        """
            ).strip()
        )
    return base
