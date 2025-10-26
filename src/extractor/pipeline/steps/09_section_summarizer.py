#!/usr/bin/env python3
"""
Pipeline Stage 9: Concurrent Section Summarizer (After Theorem Prover)

Purpose: Generate summaries for all sections AFTER theorem proving to include
formal requirements and proofs in the summaries.

This stage runs after the Lean 4 theorem prover (stage 8) and before ArangoDB
export (stage 10) to create concise summaries that include proven requirements.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from textwrap import dedent

# Third-party
from loguru import logger
from rich.console import Console
import typer
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.diagnostics import get_run_id
from scillm.extras.json_utils import clean_json_string
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD
from tqdm import tqdm
from scillm import acompletion as sc_acompletion
from extractor.pipeline.utils.model_select import get_text_model

# Note: Avoid import-time side effects. CLI setup and environment initialization
# are performed inside build_cli() so tests can import this module safely.

console = None  # type: ignore[assignment]


async def summarize_section(
    section: Dict[str, Any],
    semaphore: asyncio.Semaphore,
    previous_summaries: List[Dict[str, Any]] = None,
    window_size: int = 3,
    strict_json: bool = True,
    request_timeout: int = 120,
) -> Dict[str, Any]:
    """Generate a summary for a single section using scillm with optional rolling context."""
    prev = previous_summaries or []
    async with semaphore:
        try:
            # Build rolling context
            prev_text = "\n".join(
                f"- {p.get('section_title', 'Untitled')}: {p.get('summary_data',{}).get('summary','')}"
                for p in prev
                if p.get("success")
            )
            base_text = (
                section.get("reflowed_text")
                or section.get("merged_text")
                or section.get("raw_text")
                or ""
            )
            prompt = dedent(
                f"""
                Summarize the following document section in 2–4 sentences and list 3–7 key concepts.
                If previous summaries are provided, keep the summary consistent with them.

                Previous summaries:
                {prev_text}

                Section title: {section.get('title','Untitled')}
                Level: {section.get('level',0)}
                Text:
                {base_text}

                Return strictly JSON:
                {{
                  "summary": "concise summary",
                  "key_concepts": ["concept1", "concept2", "..."]
                }}
            """
            ).strip()

            # Prefer explicit JSON formatting via system guard + provider JSON mode (when supported)
            system_json_guard = JSON_SYSTEM_GUARD
            model_name = get_text_model()
            # scillm + Chutes x-api-key path (no Bearer)
            is_gpt5 = "gpt-5" in (model_name or "").lower()
            ch_base = os.getenv("CHUTES_API_BASE", "").strip()
            ch_key = os.getenv("CHUTES_API_KEY", "").strip()
            # Optional contracts adapter path
            if os.getenv("USE_LLM_ADAPTER", "").lower() in ("1", "true", "yes", "y"):
                try:
                    try:
                        from src.llm_adapter.adapter import LLMAdapter  # type: ignore
                    except Exception:
                        from llm_adapter.adapter import LLMAdapter  # type: ignore
                    adapter = LLMAdapter()
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "You are a section summarization engine. Return ONLY a JSON object with key: summary_json."
                                        ' No code fences. schema: {"bullets":[string],"length":"short|medium|long"}.\n\n'
                                        + prompt
                                    ),
                                }
                            ],
                        }
                    ]
                    res = await adapter.summarize_section(
                        model=model_name,
                        messages=messages,
                        prompt_version=os.getenv("STAGE09_PROMPT_VERSION", "summary@0.1.0"),
                        doc_id=str(section.get("doc_id") or "doc"),
                        section_id=str(section.get("id") or "section"),
                        request_id=f"sum_{section.get('id','section')}",
                        timeout=request_timeout,
                    )
                    result = res.summary_json
                except Exception:
                    # Fall back to direct scillm call
                    resp = await sc_acompletion(
                        model=model_name,
                        api_base=ch_base or None,
                        api_key=ch_key,
                        custom_llm_provider="openai",
                        messages=[
                            {"role": "system", "content": system_json_guard},
                            {"role": "user", "content": prompt},
                        ],
                        response_format={"type": "json_object"} if (strict_json and "gemini" not in (model_name or "").lower()) else None,
                        temperature=0.0 if is_gpt5 else 0.3,
                        timeout=request_timeout,
                    )
                    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
                    result = clean_json_string(content, return_dict=True)
            else:
                # Direct SciLLM (x-api-key header; no helper)
                resp = await sc_acompletion(
                    model=model_name,
                    custom_llm_provider="openai_like",
                    api_base=ch_base or None,
                    api_key=None,
                    extra_headers={"x-api-key": ch_key} if ch_key else None,
                    messages=[
                        {"role": "system", "content": system_json_guard},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"} if strict_json else None,
                    temperature=0.0 if is_gpt5 else 0.3,
                    timeout=request_timeout,
                )
                content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
                result = clean_json_string(content, return_dict=True)
            if strict_json and (not isinstance(result, dict) or "summary" not in result):
                # Fail fast when strict JSON is requested
                raise ValueError(
                    f"Invalid JSON from LLM (strict mode). Raw snippet: {str(content)[:200]}"
                )
            if not isinstance(result, dict) or "summary" not in result:
                try:
                    logger.debug(f"LLM summary raw content (snippet): {(content or '')[:180]}")
                except Exception:
                    pass
                raise ValueError("Invalid LLM summary JSON")
            return {
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "section_level": section.get("level", 0),
                "summary_data": {
                    "summary": result.get("summary", ""),
                    "key_concepts": result.get("key_concepts", []),
                },
                "success": True,
            }
        except Exception as e:
            logger.warning(f"Summarize fallback for {section.get('title')}: {e}")
            # Fallback: first 300 chars + naive key concepts split
            text = (
                section.get("reflowed_text")
                or section.get("merged_text")
                or section.get("raw_text")
                or ""
            )
            return {
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "section_level": section.get("level", 0),
                "summary_data": {"summary": text[:300], "key_concepts": []},
                "success": False,
            }


async def create_checkpoint_summary(
    summaries: List[Dict[str, Any]], checkpoint_name: str = "Chapter", request_timeout: int = 120
) -> Dict[str, Any]:
    """Create a higher-level summary of multiple sections via the paved scillm helper.

    - Uses scillm.acompletion on an OpenAI-compatible Chutes path with x-api-key
    - Deterministic one-retry backoff on specific transient errors (429 capacity)
    - Fails fast with a clear error otherwise
    """
    if not summaries:
        return None

    successful_summaries = [s for s in summaries if s.get("success")]
    if not successful_summaries:
        return None

    summary_texts: List[str] = []
    for s in successful_summaries:
        try:
            if s.get("summary_data"):
                summary_texts.append(f"- {s['section_title']}: {s['summary_data']['summary']}")
        except Exception:
            continue

    prompt = dedent(
        f"""
    Create a high-level summary of this chapter/part of the document.

    Section summaries:
    {chr(10).join(summary_texts)}

    Provide a JSON response with:
    {{
        "checkpoint_summary": "A comprehensive 3-4 sentence summary of this entire chunk",
        "major_themes": ["List", "of", "major", "themes"],
        "key_concepts": ["Most", "important", "concepts", "from", "all", "sections"],
        "chapter_purpose": "The overall purpose of this chapter in the document"
    }}
    """
    ).strip()

    # Choose text model (CHUTES_TEXT_MODEL is canonical; helper supports vendor-first ids)
    model_name = (os.getenv("CHUTES_TEXT_MODEL") or get_text_model()).strip()
    if not model_name:
        logger.error("checkpoint_summary.no_model_configured")
        return None

    system_guard = JSON_SYSTEM_GUARD

    async def _call_once_async():
        return await sc_acompletion(
            model=model_name,
            custom_llm_provider="openai_like",
            api_base=os.getenv("CHUTES_API_BASE", "").strip() or None,
            api_key=None,
            extra_headers={"x-api-key": os.getenv("CHUTES_API_KEY", "").strip()} if os.getenv("CHUTES_API_KEY") else None,
            messages=[
                {"role": "system", "content": system_guard},
                {"role": "user", "content": prompt},
            ],
            response_format={"type":"json_object"},
            temperature=0.0,
            timeout=request_timeout,
        )

    # Try up to 3 attempts total, honoring capacity signals; helper/client handle Retry-After internally
    attempts = 0
    last_err_msg = ""
    while True:
        try:
            resp = await _call_once_async()
            break
        except Exception as e:
            attempts += 1
            msg = str(e)
            last_err_msg = msg
            if attempts >= 3:
                logger.error(f"Failed to create checkpoint summary (attempts={attempts}): {e}")
                # If capacity-related, emit a skip marker so downstream can record it deterministically
                if any(t in msg for t in ("429", "Too Many Requests", "capacity", "maximum capacity")):
                    return {
                        "type": "checkpoint",
                        "name": checkpoint_name,
                        "sections_covered": len(successful_summaries),
                        "data": {"checkpoint_skipped": "capacity"},
                        "skipped": True,
                        "reason": "capacity",
                    }
                if ("401" in msg) or ("Unauthorized" in msg):
                    return {
                        "type": "checkpoint",
                        "name": checkpoint_name,
                        "sections_covered": len(successful_summaries),
                        "data": {"checkpoint_skipped": "auth"},
                        "skipped": True,
                        "reason": "auth",
                    }
                return None
            # Capacity / rate limit: brief guard before next attempt; helper performs proper backoff
            if any(t in msg for t in ("429", "Too Many Requests", "capacity", "maximum capacity")):
                logger.info(f"checkpoint_summary.retry_after_capacity attempt={attempts}")
                await asyncio.sleep(0.5)
                continue
            # Auth transients: allow one more try (helper may lock a working auth style)
            if ("401" in msg) or ("Unauthorized" in msg):
                logger.info(f"checkpoint_summary.retry_after_401 attempt={attempts}")
                await asyncio.sleep(0.25)
                continue
            # Other errors: do not spin
            logger.error(f"Failed to create checkpoint summary: {e}")
            return None

    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if not content:
        logger.error("checkpoint_summary.empty_content")
        return None
    try:
        result = clean_json_string(content, return_dict=True)
    except Exception as e:
        logger.error(f"checkpoint_summary.json_clean_failed: {e}")
        return None

    return {
        "type": "checkpoint",
        "name": checkpoint_name,
        "sections_covered": len(successful_summaries),
        "data": result,
    }


async def batch_summarize_sections_rolling(
    sections: List[Dict[str, Any]],
    max_concurrent: int = 5,
    window_size: int = 3,
    checkpoint_interval: int = 20,
    strict_json: bool = True,
    request_timeout: int = 120,
) -> List[Dict[str, Any]]:
    """Summarize sections with rolling window context and periodic checkpoints.

    This implementation processes sections in order, maintaining a rolling
    window of previous summaries for context. Uses a hybrid approach:
    - Sequential processing to maintain context
    - Limited concurrency within windows for efficiency
    - Periodic checkpoint summaries to manage large documents

    Args:
        sections: List of section dictionaries from stage 7
        max_concurrent: Maximum concurrent LLM calls
        window_size: Size of rolling context window
        checkpoint_interval: Create checkpoint every N sections

    Returns:
        List of summary results in order with checkpoint summaries
    """
    # Filter to sections that have any usable text; accept fallback reflows too
    valid_sections = [
        s
        for s in sections
        if s.get("reflow_status") in ["success", "success_placeholder", "fallback"]
        and (s.get("reflowed_text") or s.get("merged_text") or s.get("raw_text"))
    ]

    if not valid_sections:
        return []

    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(max_concurrent)

    # Results accumulator
    all_summaries = []
    checkpoint_buffer = []  # Buffer for checkpoint creation
    last_checkpoint = None

    # Process in batches to balance order and concurrency
    batch_size = max_concurrent

    with tqdm(total=len(valid_sections), desc="Summarizing sections (rolling window)") as pbar:
        for i in range(0, len(valid_sections), batch_size):
            batch = valid_sections[i : i + batch_size]

            # Create tasks for this batch with appropriate context
            tasks = []
            for j, section in enumerate(batch):
                # For context, use recent summaries + last checkpoint
                context_summaries = all_summaries[-window_size:].copy()

                # If we have a checkpoint, prepend it as context
                if last_checkpoint:
                    checkpoint_summary = {
                        "section_id": "checkpoint",
                        "section_title": f"[{last_checkpoint['name']}]",
                        "section_level": -1,  # Special level for checkpoints
                        "summary_data": {"summary": last_checkpoint["data"]["checkpoint_summary"]},
                        "success": True,
                    }
                    context_summaries.insert(0, checkpoint_summary)

                task = summarize_section(
                    section=section,
                    semaphore=semaphore,
                    previous_summaries=context_summaries,
                    window_size=window_size + 1 if last_checkpoint else window_size,
                    strict_json=strict_json,
                    request_timeout=request_timeout,
                )
                tasks.append((i + j, task))  # Store index for ordering

            # Process batch concurrently with order preserved
            positions, coros = zip(*tasks) if tasks else ([], [])
            results = await asyncio.gather(*coros) if coros else []
            batch_results = [None] * len(results)
            for pos, res in zip(positions, results):
                batch_results[pos - i] = res
                if res.get("success"):
                    logger.success(f"Summarized: {res.get('section_title')}")
                else:
                    logger.warning(f"Failed: {res.get('section_title')} - {res.get('error', '')}")
                pbar.update(1)

            # Add batch results to accumulator in order
            all_summaries.extend(batch_results)
            checkpoint_buffer.extend(batch_results)

            # Create checkpoint if needed
            if len(checkpoint_buffer) >= checkpoint_interval:
                logger.info(f"Creating checkpoint summary for {len(checkpoint_buffer)} sections...")
                checkpoint = await create_checkpoint_summary(
                    checkpoint_buffer,
                    f"Checkpoint {len(all_summaries) // checkpoint_interval}",
                    request_timeout=request_timeout,
                )
                if checkpoint:
                    last_checkpoint = checkpoint
                    checkpoint_buffer = []  # Reset buffer
                    # Add checkpoint to results
                    all_summaries.append(
                        {
                            "section_id": f"checkpoint_{len(all_summaries)}",
                            "section_title": checkpoint["name"],
                            "section_level": -1,
                            "summary_data": checkpoint["data"],
                            "success": True,
                            "is_checkpoint": True,
                            "sections_covered": checkpoint["sections_covered"],
                        }
                    )

    # Final checkpoint for remaining sections
    if checkpoint_buffer:
        logger.info(f"Creating final checkpoint for {len(checkpoint_buffer)} sections...")
        checkpoint = await create_checkpoint_summary(
            checkpoint_buffer, "Final Checkpoint", request_timeout=request_timeout
        )
        if checkpoint:
            all_summaries.append(
                {
                    "section_id": "checkpoint_final",
                    "section_title": checkpoint["name"],
                    "section_level": -1,
                    "summary_data": checkpoint["data"],
                    "success": True,
                    "is_checkpoint": True,
                    "sections_covered": checkpoint["sections_covered"],
                }
            )

    return all_summaries


def _cmd_run(
    input_json: Path = typer.Argument(
        ..., help="Path to Stage 08 (theorems) or Stage 07 (reflow) JSON output.", exists=True
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    max_concurrent: int = typer.Option(5, help="Maximum concurrent LLM calls"),
    window_size: int = typer.Option(3, help="Rolling window size for context"),
    strict_json: bool = typer.Option(
        True,
        "--strict-json/--no-strict-json",
        help="Require provider JSON mode or allow free-form parsing",
    ),
    request_timeout: int = typer.Option(
        120, "--timeout", help="Per-request LLM timeout in seconds"
    ),
):
    """Generates summaries for all sections using concurrent processing."""
    console.print("[bold green]Starting Section Summarization (Stage 09)[/bold green]")

    # --- Directory and Data Setup ---
    stage_output_dir = output_dir / "09_section_summarizer"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(input_json, "r") as f:
        pipeline_data = json.load(f)

    sections = pipeline_data.get("reflowed_sections", [])

    if not sections:
        console.print("[yellow]No reflowed sections found in input file. Exiting.[/yellow]")
        return

    console.print(f"Found {len(sections)} sections to summarize.")

    # --- Concurrent Summarization ---
    summaries = asyncio.run(
        batch_summarize_sections_rolling(
            sections=sections,
            max_concurrent=max_concurrent,
            window_size=window_size,
            strict_json=strict_json,
            request_timeout=request_timeout,
        )
    )

    successful_count = sum(1 for s in summaries if s.get("success"))
    console.print(f"\n✅ Generated {successful_count}/{len(sections)} summaries.")

    # --- Final Payload and Output ---
    final_output = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(input_json),
        "status": "Completed",
        "sections_processed": len(sections),
        "summaries_generated": successful_count,
        "summaries": summaries,
    }

    output_path = json_output_dir / "09_summaries.json"
    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2)

    console.print(f"📄 Results saved to: {output_path}")


def _cmd_debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle with key: reflowed_sections (list)",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    max_concurrent: int = typer.Option(5, help="Maximum concurrent LLM calls"),
    window_size: int = typer.Option(3, help="Rolling window size for context"),
    strict_json: bool = typer.Option(
        True,
        "--strict-json/--no-strict-json",
        help="Require provider JSON mode or allow free-form parsing",
    ),
    request_timeout: int = typer.Option(
        120, "--timeout", help="Per-request LLM timeout in seconds"
    ),
):
    """Run Stage 09 summarization from a consolidated list of sections."""
    stage_output_dir = output_dir / "09_section_summarizer"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        sections = data.get("reflowed_sections") or []
        if not isinstance(sections, list) or not sections:
            raise ValueError("Bundle must include non-empty 'reflowed_sections' list")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    summaries = asyncio.run(
        batch_summarize_sections_rolling(
            sections=sections,
            max_concurrent=max_concurrent,
            window_size=window_size,
            strict_json=strict_json,
            request_timeout=request_timeout,
        )
    )
    successful_count = sum(1 for s in summaries if s.get("success"))
    final_output = {
        "timestamp": datetime.now().isoformat(),
        "status": "Completed",
        "sections_processed": len(sections),
        "summaries_generated": successful_count,
        "summaries": summaries,
    }
    output_path = json_output_dir / "09_summaries.json"
    output_path.write_text(json.dumps(final_output, indent=2))
    console.print(f"[green]Debug bundle: saved {successful_count} summaries to {output_path}")


def _cmd_test():
    """Test with a single section."""

    test_section = {
        "id": "test_001",
        "title": "Introduction to RISC-V",
        "level": 1,
        "reflow_status": "success",
        "reflowed_text": """
        RISC-V is an open standard instruction set architecture (ISA) based on 
        established reduced instruction set computer (RISC) principles. Unlike 
        proprietary ISAs, RISC-V is freely available for academic and commercial use. 
        The ISA supports various word-widths and subsets, making it suitable for 
        everything from tiny embedded systems to supercomputers.
        """,
    }

    # Test single section
    result = asyncio.run(
        summarize_section(
            section=test_section,
            semaphore=asyncio.Semaphore(1),
            previous_summaries=None,
            window_size=3,
        )
    )

    console.print("\n[bold]Test Result:[/bold]")
    console.print(json.dumps(result, indent=2))


## CLI removed: import and call run(...) entry points from Python/tests.


## No __main__: run via scripts/debug or import.
