#!/usr/bin/env python3
"""
Pipeline Stage 09: Section Summarizer (Modernized)

Consolidates logic and adheres to the SCILLM Paved Path.
Uses SciLLM v1.78.1 parallel_acompletions_iter for standardized execution.
"""

import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from extractor.pipeline.utils.content_query import ContentRepository
from extractor.pipeline.utils.step_sanity import run_step_sanity

# Ensure JSON strict mode before SciLLM calls
os.environ["SCILLM_JSON_STRICT"] = "1"
load_dotenv(find_dotenv(usecwd=True), override=False)

STEP_NAME = "09_section_summarizer"

# ------------------------------------------------------------------------


# Default model and API settings
DEFAULT_MODEL = os.getenv("CHUTES_TEXT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
DEFAULT_API_BASE = os.getenv("SCILLM_API_BASE", "http://localhost:4000")
DEFAULT_CONCURRENCY = int(os.getenv("SCILLM_CONCURRENCY", "6"))

# Minimum content requirements to avoid summarizing boilerplate
MIN_SECTION_WORDS = int(os.getenv("STAGE09_MIN_SECTION_WORDS", "20"))


def extract_message_content(r: Any) -> Optional[str]:
    """Normalize SciLLM response content extraction."""
    try:
        if isinstance(r, dict):
            # Try to get from 'parsed' first if schema/JSON was used
            if r.get("parsed"):
                return r["parsed"]
            return r.get("content")

        # Fallback for raw objects
        choices = getattr(r, "choices", None)
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg:
                return getattr(msg, "content", None)
        return None
    except Exception as e:
        logger.debug(f"extraction_normalization_failed: {e}")
        return None


def fetch_ordered_section_content(repo: ContentRepository, section_id: str) -> str:
    """
    Fetches all artifacts for a section and joins them in reading order.
    Merges contiguous text blocks.
    """
    # 1. Fetch all assets using ContentRepository
    clean_blocks = repo.get_clean_blocks(section_id)
    section_tables = repo.get_tables_for_section(section_id)
    section_figures = repo.get_figures_for_section(section_id)

    # 2. Interleave
    all_items = []
    for b in clean_blocks:
        all_items.append(
            {"page": b.get("page", 0), "y0": b.get("y0", 0), "type": "text",
             "content": b.get("text", ""), "sub_type": b.get("type", "")}
        )
    for t in section_tables:
        title = t.get("llm_title") or "Untitled Table"
        desc = t.get("llm_description") or ""
        all_items.append(
            {
                "page": t.get("page", 0),
                "y0": t.get("y0", 0),
                "type": "table",
                "content": f"[TABLE: {title}] {desc}".strip(),
            }
        )
    for f in section_figures:
        title = f.get("llm_title") or "Untitled Figure"
        desc = f.get("llm_description") or ""
        all_items.append(
            {
                "page": f.get("page", 0),
                "y0": f.get("y0", 0),
                "type": "figure",
                "content": f"[FIGURE: {title}] {desc}".strip(),
            }
        )

    all_items.sort(key=lambda x: (x["page"], x["y0"]))

    # 3. Merge contiguous text and format
    final_lines = []
    current_text = []

    for item in all_items:
        if item["type"] == "text":
            line = item["content"].strip()
            if not line:
                continue
            if item.get("sub_type") == "SectionHeader":
                if current_text:
                    final_lines.append(" ".join(current_text))
                    current_text = []
                final_lines.append(f"### {line}")
            else:
                current_text.append(line)
        else:
            # Table or Figure
            if current_text:
                final_lines.append(" ".join(current_text))
                current_text = []
            final_lines.append(item["content"])

    if current_text:
        final_lines.append(" ".join(current_text))

    return "\n\n".join(final_lines)


async def run_summarizer(
    repo: ContentRepository,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
    preset_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """Batch summarize sections with rolling context via parallel_acompletions_iter."""
    from scillm.batch import parallel_acompletions_iter

    # 1. Fetch sections
    section_rows = [(s["id"], s.get("title", "")) for s in
                    sorted(repo.sections, key=lambda s: (s.get("page_start") or 0, s.get("id", "")))]
    if not section_rows:
        logger.warning("No sections found for summarization.")
        return {"summaries": 0}

    # Load prompts
    from extractor.pipeline.utils.prompt_loader import load_prompt

    prompts = load_prompt("09_section_summarizer")
    system_prompt = prompts["system"]

    user_override = (
        preset_config.get("features", {}).get("summarization_prompt") if preset_config else None
    )
    if user_override:
        user_prompt_tmpl = user_override
        logger.info("Using Custom Summarization Prompt from Preset Context")
    else:
        user_prompt_tmpl = prompts["user"]

    # Schema for validation
    summary_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "minLength": 20},
            "key_concepts": {"type": "array", "items": {"type": "string"}, "minItems": 2},
        },
        "required": ["summary", "key_concepts"],
    }

    batch_size = concurrency if concurrency > 0 else 4
    all_results = []
    previous_summaries = []

    api_key = os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123")

    # 1.1 Verify bridge connectivity before starting
    if "localhost" in api_base or "127.0.0.1" in api_base:
        import aiohttp

        logger.info(f"Checking bridge connectivity at {api_base}...")
        try:
            async with aiohttp.ClientSession() as session:
                test_url = api_base.rstrip("/") + "/models"
                async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status >= 500:
                        logger.warning(f"Bridge returned {resp.status}; summarization might fail.")
                    else:
                        logger.info("Bridge is reachable.")
        except Exception as e:
            logger.error(f"Bridge unreachable at {api_base}: {e}")
            logger.warning("Skipping summarization to avoid timeout waits.")
            return {"summaries": 0}

    logger.info(f"Summarizing {len(section_rows)} sections in batches of {batch_size}...")

    for i in range(0, len(section_rows), batch_size):
        batch_rows = section_rows[i : i + batch_size]

        # Build context from the last 3 successful summaries
        context_str = "\n".join(
            [f"- {s['title']}: {s['summary']}" for s in previous_summaries[-3:]]
        )
        if not context_str:
            context_str = "(none)"

        payloads = []
        for s_id, title in batch_rows:
            section_text = fetch_ordered_section_content(repo, s_id)

            # Skip sections with insufficient content
            word_count = len(section_text.split())
            if word_count < MIN_SECTION_WORDS:
                logger.debug(f"Skipping section {s_id} ({title}): only {word_count} words")
                continue

            prompt = user_prompt_tmpl.format(
                previous_summaries=context_str,
                section_title=title,
                section_level=0,
                section_text=section_text[:15000],
            )
            payloads.append(
                {
                    "model": model,
                    "id": s_id,
                    "title": title,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                }
            )

        # Run this batch
        async for r in parallel_acompletions_iter(
            payloads,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai",
            concurrency=batch_size,
            repair_invalid_json=True,
            retry_invalid_json=2,
            schema=summary_schema,
            timeout=120,
            wall_time_s=600,
            tenacious=True,
        ):
            req = r.get("request", {})
            s_id = req.get("id")
            title = req.get("title")

            content_val = extract_message_content(r)

            if isinstance(content_val, dict):
                data = content_val
            elif isinstance(content_val, str):
                try:
                    data = json.loads(content_val)
                except Exception:
                    data = {}
            else:
                data = {}

            summary = data.get("summary", "")
            key_concepts = data.get("key_concepts", [])

            if summary:
                logger.info(f"Successfully summarized section {s_id}: {title}")
                res = {"id": s_id, "title": title, "summary": summary, "success": True}
                previous_summaries.append(res)
                all_results.append(res)

                # Metadata capture
                meta = {
                    "usage": r.get("usage"),
                    "model": r.get("model", model),
                    "latency_ms": r.get("metrics", {}).get("total_time_ms"),
                    "timings": r.get("timings"),
                    "generated_at": datetime.utcnow().isoformat(),
                }

                # Update in-memory data via ContentRepository
                repo.update_section(
                    s_id,
                    llm_summary=summary,
                    llm_key_concepts=json.dumps(key_concepts),
                    llm_metadata=json.dumps(meta),
                )
            else:
                err_msg = r.get("error", "Unknown error")
                logger.warning(f"Failed to summarize section {s_id}: {title} | Error: {err_msg}")

    # --- Document-level summary (ONE call with all section summaries) ---
    successful_summaries = [r for r in all_results if r["success"]]
    if successful_summaries:
        doc_summary = await create_document_summary(
            repo, successful_summaries, model, api_base, api_key
        )
        if doc_summary:
            logger.info(f"Document summary created: {len(doc_summary.get('summary', ''))} chars")

    # Save all updates back to JSON
    repo.save()

    return {"summaries": len(successful_summaries)}


async def create_document_summary(
    repo: ContentRepository,
    section_summaries: list[dict],
    model: str,
    api_base: str,
    api_key: str | None,
) -> dict | None:
    """Create ONE document-level summary from all section summaries."""
    from scillm.batch import parallel_acompletions_iter

    if not section_summaries:
        return None

    section_texts = []
    for s in section_summaries:
        title = s.get("title", "Untitled")
        summary = s.get("summary", "")
        if summary:
            section_texts.append(f"## {title}\n{summary}")

    all_summaries_text = "\n\n".join(section_texts)

    estimated_tokens = len(all_summaries_text) // 4
    logger.info(f"Creating document summary from {len(section_summaries)} sections (~{estimated_tokens} tokens)")

    system_prompt = """You are a document summarization assistant. Create a comprehensive summary of the entire document based on the section summaries provided. Return JSON only."""

    user_prompt = f"""Based on these section summaries, create an overall document summary.

SECTION SUMMARIES:
{all_summaries_text}

Return strictly JSON:
{{
  "summary": "A comprehensive 3-5 paragraph summary of the entire document",
  "key_themes": ["major theme 1", "major theme 2", ...],
  "document_type": "requirements spec | technical report | user manual | other",
  "audience": "intended audience description"
}}"""

    payload = {
        "model": model,
        "id": "document_summary",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }

    result = None
    async for r in parallel_acompletions_iter(
        [payload],
        api_base=api_base,
        api_key=api_key,
        custom_llm_provider="openai",
        concurrency=1,
        repair_invalid_json=True,
        timeout=120,
    ):
        content_val = extract_message_content(r)
        if isinstance(content_val, dict):
            result = content_val
        elif isinstance(content_val, str):
            try:
                result = json.loads(content_val)
            except Exception:
                result = {"summary": content_val}

    if result:
        # Preserve existing scanned_pdf metadata
        existing_meta = repo.document_metadata or {}
        scanned_pdf = existing_meta.get("scanned_pdf")
        scanned_pdf_detection = existing_meta.get("scanned_pdf_detection")

        meta = {
            "model": model,
            "section_count": len(section_summaries),
            "generated_at": datetime.utcnow().isoformat(),
        }

        doc_meta = {
            "id": "doc",
            "document_summary": result.get("summary", ""),
            "key_themes": json.dumps(result.get("key_themes", [])),
            "section_count": len(section_summaries),
            "llm_metadata": json.dumps(meta),
            "scanned_pdf": scanned_pdf,
            "scanned_pdf_detection": scanned_pdf_detection,
        }
        repo.set_document_metadata(doc_meta)
        logger.info("Document summary stored in assembled_content.json")

    return result


def _emit_summary_visuals(pipeline_dir: Path, repo: ContentRepository) -> None:
    """Generate summary visuals from pipeline data and save to output directory."""
    stage_dir = pipeline_dir / "09_section_summarizer"
    visual_dir = stage_dir / "visual_output"
    visual_dir.mkdir(parents=True, exist_ok=True)

    sections_json = pipeline_dir / "04_section_builder" / "json_output" / "04_sections.json"
    section_visuals: dict[str, Path] = {}
    source_pdf = None
    if sections_json.exists():
        try:
            data = json.loads(sections_json.read_text())
            source_pdf = data.get("source_pdf") or None
            for sec in data.get("sections") or []:
                sid = sec.get("id")
                vrel = sec.get("visual_path")
                if sid and vrel:
                    cand = Path(str(vrel))
                    if not cand.is_absolute():
                        cand = pipeline_dir / cand
                    if cand.exists():
                        section_visuals[str(sid)] = cand
        except Exception as e:
            logger.debug(f"Failed to load section visuals from S04 output: {e}")

    doc = None
    if source_pdf:
        try:
            import fitz

            doc = fitz.open(str(source_pdf))
        except Exception:
            doc = None

    # Get sections with summaries
    summarized_sections = [
        (s["id"], s.get("page_start", 0))
        for s in repo.sections
        if s.get("llm_summary")
    ]
    summarized_sections.sort(key=lambda x: (x[1] or 0, x[0]))

    visuals = []
    for idx, (sid, page_start) in enumerate(summarized_sections):
        out_path = visual_dir / f"section_{idx:04d}.png"
        src = section_visuals.get(str(sid)) if sid is not None else None
        if src and src.exists():
            if not out_path.exists():
                shutil.copy2(src, out_path)
            visuals.append(
                {
                    "section_id": sid,
                    "visual_path": str(out_path.relative_to(pipeline_dir)),
                }
            )
            continue
        if doc is None:
            continue
        try:
            pg = int(page_start or 0)
            if pg < 0 or pg >= len(doc):
                pg = 0
            page = doc[pg]
            rect = page.rect
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
            pix.save(str(out_path))
            visuals.append(
                {
                    "section_id": sid,
                    "visual_path": str(out_path.relative_to(pipeline_dir)),
                }
            )
        except Exception:
            continue

    if doc is not None:
        doc.close()

    json_dir = stage_dir / "json_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    summary_path = json_dir / "09_section_summaries.json"
    summary_path.write_text(
        json.dumps({"visuals": visuals}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_stage_09_summarizer(
    pipeline_dir: Path,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
    preset_config: Optional[Dict[str, Any]] = None,
):
    """Entry point for the pipeline driver."""

    json_path = pipeline_dir / "07_assembled" / "assembled_content.json"
    if not json_path.exists():
        logger.error(f"assembled_content.json not found at {json_path}")
        return

    repo = ContentRepository(json_path)
    try:
        asyncio.run(run_summarizer(repo, model, api_base, concurrency, preset_config=preset_config))
        if os.getenv("CONTRACT_LOOP_DEBUG_VISUALS", "0").lower() in {"1", "true", "yes", "y"}:
            _emit_summary_visuals(pipeline_dir, repo)
        logger.info("Stage 09 Section Summarizer complete.")
    except Exception as e:
        logger.error(f"Stage 09 Failed: {e}")
        raise e


def sanity() -> int:
    """Run sanity check for this step."""
    return run_step_sanity(STEP_NAME)


# Standard entry point alias for consistency across pipeline steps
run = run_stage_09_summarizer


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 09: Section Summarizer")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    args = parser.parse_args()

    json_path = args.pipeline_dir / "07_assembled" / "assembled_content.json"
    if not json_path.exists():
        logger.error(f"assembled_content.json missing: {json_path}")
        sys.exit(1)

    repo = ContentRepository(json_path)

    try:
        logger.info("Running Stage 09...")
        asyncio.run(run_summarizer(repo))
        if os.getenv("CONTRACT_LOOP_DEBUG_VISUALS", "0").lower() in {"1", "true", "yes", "y"}:
            _emit_summary_visuals(args.pipeline_dir, repo)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
