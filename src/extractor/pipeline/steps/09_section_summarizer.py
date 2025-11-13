#!/usr/bin/env python3
"""
Pipeline Stage 9: Concurrent Section Summarizer (After Theorem Prover)

Purpose: Generate summaries for all sections AFTER theorem proving to include
formal requirements and proofs in the summaries.

This stage runs after the Lean 4 theorem prover (stage 8) and before ArangoDB
export (stage 10) to create concise summaries that include proven requirements.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from textwrap import dedent

# Third-party
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.json_utils import clean_json_string, restrict_top_level_keys
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD
from tqdm import tqdm
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.model_select import get_text_model
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

# Note: Avoid import-time side effects. Tests can import this module safely.

console = Console()
STEP_NAME = "09_section_summarizer"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# Monkeypatch hook for tests: provide a placeholder litellm_call that tests can override
def litellm_call(prompts, **kwargs):  # type: ignore[unused-argument]
    raise RuntimeError("litellm_call is not implemented in stage 09; tests may monkeypatch it.")


async def summarize_section(
    section: Dict[str, Any],
    semaphore: asyncio.Semaphore,
    previous_summaries: List[Dict[str, Any]] = None,
    window_size: int = 3,
    strict_json: bool = True,
    request_timeout: int = 120,
    timings_lock: Optional[asyncio.Lock] = None,
    timings_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a summary for a single section using scillm with optional rolling context."""
    prev = previous_summaries or []
    async with semaphore:
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

            # Router-only, strict JSON; fail fast on any deviation
            system_json_guard = JSON_SYSTEM_GUARD
            model_name = get_text_model()
            is_gpt5 = "gpt-5" in (model_name or "").lower()
            router = get_text_router()

            t0 = asyncio.get_event_loop().time()
            error: Optional[str] = None
            served_model: Optional[str] = None
            usage: Dict[str, Any] = {}
            content_preview: Optional[str] = None
            try:
                resp = await router.acompletion(
                    model="chutes/text",
                    messages=[
                        {"role": "system", "content": system_json_guard},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"} if strict_json else None,
                    temperature=0.0 if is_gpt5 else 0.0,
                    timeout=request_timeout,
                )
                served_model = getattr(resp, "model", None) or getattr(resp, "id", None) or "chutes/text"
                content = (getattr(resp, "choices", [{}])[0].get("message", {}).get("content", ""))
                try:
                    # Keep a short preview for debugging if parsing fails downstream
                    content_preview = str(content)[:400]
                except Exception:
                    content_preview = None
                usage_obj = getattr(resp, "usage", None) or {}
                if isinstance(usage_obj, dict):
                    usage = usage_obj
                else:
                    usage = {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                        "total_tokens": getattr(usage_obj, "total_tokens", None),
                    }
                result = clean_json_string(content, return_dict=True)
                # Strictly restrict top-level keys to the schema; tolerate extra keys by trimming
                if isinstance(result, dict):
                    try:
                        result = restrict_top_level_keys(result, allowed={"summary", "key_concepts"})
                    except Exception:
                        pass
                if strict_json and (
                    not isinstance(result, dict)
                    or "summary" not in result
                    or not isinstance(result.get("key_concepts", []), list)
                    or any(k not in {"summary", "key_concepts"} for k in result.keys())
                ):
                    raise ValueError(f"stage09.invalid_json: {str(content)[:160]}")
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
                error = f"{type(e).__name__}: {e}"
                raise
            finally:
                # Per-attempt timings
                if timings_path is not None and timings_lock is not None:
                    t1 = asyncio.get_event_loop().time()
                    latency_ms = int((t1 - t0) * 1000)
                    line = {
                        "ts": datetime.utcnow().isoformat() + "Z",
                        "type": "section",
                        "section_id": section.get("id"),
                        "section_title": section.get("title"),
                        "served_model": served_model,
                        "usage": usage,
                        "latency_ms": latency_ms,
                        "outcome": "success" if error is None else "error",
                        "error": error,
                        "raw_preview": content_preview if error is not None else None,
                    }
                    try:
                        async with timings_lock:
                            with timings_path.open("a", encoding="utf-8") as f:
                                f.write(json.dumps(line, ensure_ascii=False) + "\n")
                    except Exception:
                        pass


async def create_checkpoint_summary(
    summaries: List[Dict[str, Any]],
    checkpoint_name: str = "Chapter",
    request_timeout: int = 120,
    timings_lock: Optional[asyncio.Lock] = None,
    timings_path: Optional[Path] = None,
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
        router = get_text_router()
        return await router.acompletion(
            model="chutes/text",
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
    last_error: Optional[str] = None
    served_model: Optional[str] = None
    usage: Dict[str, Any] = {}
    start_time = asyncio.get_event_loop().time()
    while True:
        try:
            resp = await _call_once_async()
            break
        except Exception as e:
            attempts += 1
            msg = str(e)
            _ = msg  # keep var for potential future logging; avoid unused
            if attempts >= 3:
                logger.error(f"Failed to create checkpoint summary (attempts={attempts}): {e}")
                # If capacity-related, emit a skip marker so downstream can record it deterministically
                if any(t in msg for t in ("429", "Too Many Requests", "capacity", "maximum capacity")):
                    if timings_path is not None and timings_lock is not None:
                        try:
                            async with timings_lock:
                                with timings_path.open("a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        "ts": datetime.utcnow().isoformat() + "Z",
                                        "type": "checkpoint",
                                        "name": checkpoint_name,
                                        "served_model": None,
                                        "usage": {},
                                        "latency_ms": int((asyncio.get_event_loop().time() - start_time) * 1000),
                                        "outcome": "skipped_capacity",
                                        "error": msg,
                                    }) + "\n")
                        except Exception:
                            pass
                    return {
                        "type": "checkpoint",
                        "name": checkpoint_name,
                        "sections_covered": len(successful_summaries),
                        "data": {"checkpoint_skipped": "capacity"},
                        "skipped": True,
                        "reason": "capacity",
                    }
                if ("401" in msg) or ("Unauthorized" in msg):
                    if timings_path is not None and timings_lock is not None:
                        try:
                            async with timings_lock:
                                with timings_path.open("a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        "ts": datetime.utcnow().isoformat() + "Z",
                                        "type": "checkpoint",
                                        "name": checkpoint_name,
                                        "served_model": None,
                                        "usage": {},
                                        "latency_ms": int((asyncio.get_event_loop().time() - start_time) * 1000),
                                        "outcome": "skipped_auth",
                                        "error": msg,
                                    }) + "\n")
                        except Exception:
                            pass
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

    content = (getattr(resp, "choices", [{}])[0].get("message", {}).get("content", ""))
    if not content:
        logger.error("checkpoint_summary.empty_content")
        return None
    try:
        served_model = getattr(resp, "model", None) or getattr(resp, "id", None) or "chutes/text"
        usage_obj = getattr(resp, "usage", None) or {}
        if isinstance(usage_obj, dict):
            usage = usage_obj
        else:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                "total_tokens": getattr(usage_obj, "total_tokens", None),
            }
        result = clean_json_string(content, return_dict=True)
    except Exception as e:
        logger.error(f"checkpoint_summary.json_clean_failed: {e}")
        return None

    # timings write
    if timings_path is not None and timings_lock is not None:
        try:
            async with timings_lock:
                with timings_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "ts": datetime.utcnow().isoformat() + "Z",
                        "type": "checkpoint",
                        "name": checkpoint_name,
                        "served_model": served_model,
                        "usage": usage,
                        "latency_ms": int((asyncio.get_event_loop().time() - start_time) * 1000),
                        "outcome": "success",
                        "error": None,
                    }) + "\n")
        except Exception:
            pass

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
    timings_dir: Optional[Path] = None,
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
    timings_lock = asyncio.Lock()
    timings_path: Optional[Path] = None
    if timings_dir is not None:
        timings_dir.mkdir(parents=True, exist_ok=True)
        try:
            timings_path = (timings_dir / "timings.jsonl")
            timings_path.touch(exist_ok=True)
        except Exception:
            timings_path = None

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
                    timings_lock=timings_lock if timings_path is not None else None,
                    timings_path=timings_path,
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
                    timings_lock=timings_lock if timings_path is not None else None,
                    timings_path=timings_path,
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
            checkpoint_buffer,
            "Final Checkpoint",
            request_timeout=request_timeout,
            timings_lock=timings_lock if timings_path is not None else None,
            timings_path=timings_path,
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

    # Aggregate timings into summary if available
    if timings_path is not None:
        try:
            calls = success = error = latency_sum = 0
            prompt_tokens_total = completion_tokens_total = total_tokens_total = 0
            with timings_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    calls += 1
                    if rec.get("outcome") == "success":
                        success += 1
                    else:
                        error += 1
                    latency_sum += int(rec.get("latency_ms") or 0)
                    u = rec.get("usage") or {}
                    prompt_tokens_total += int(u.get("prompt_tokens") or 0)
                    completion_tokens_total += int(u.get("completion_tokens") or 0)
                    total_tokens_total += int(u.get("total_tokens") or 0)
            timings_summary_path = (timings_dir / "timings_summary.json") if timings_dir else None
            if timings_summary_path:
                with timings_summary_path.open("w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "calls": calls,
                            "success": success,
                            "error": error,
                            "latency_ms_total": latency_sum,
                            "latency_ms_avg": (latency_sum // calls) if calls else 0,
                            "prompt_tokens_total": prompt_tokens_total,
                            "completion_tokens_total": completion_tokens_total,
                            "total_tokens_total": total_tokens_total,
                        },
                        f,
                        indent=2,
                    )
        except Exception:
            pass
    return all_summaries


def _cmd_run(
    input_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    max_concurrent: int = 5,
    window_size: int = 3,
    strict_json: bool = True,
    request_timeout: int = 120,
):
    """Generates summaries for all sections using concurrent processing."""
    console.print("[bold green]Starting Section Summarization (Stage 09)[/bold green]")
    try:
        require_scillm_preflight()
    except RuntimeError as exc:
        console.print(f"[red]Stage 09 SciLLM preflight failed: {exc}[/red]")
        raise

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
    timings_dir = stage_output_dir
    try:
        summaries = asyncio.run(
            batch_summarize_sections_rolling(
                sections=sections,
                max_concurrent=max_concurrent,
                window_size=window_size,
                strict_json=strict_json,
                request_timeout=request_timeout,
                timings_dir=timings_dir,
            )
        )
    finally:
        # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
        pass

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
    return output_path


def _cmd_debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    max_concurrent: int = 5,
    window_size: int = 3,
    strict_json: bool = True,
    request_timeout: int = 120,
):
    """Run Stage 09 summarization from a consolidated list of sections."""
    try:
        require_scillm_preflight()
    except RuntimeError as exc:
        console.print(f"[red]Stage 09 SciLLM preflight failed: {exc}[/red]")
        raise
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
        print(f"Failed to load bundle: {e}")
        raise ValueError(f"Failed to load bundle: {e}")

    timings_dir = stage_output_dir
    try:
        summaries = asyncio.run(
            batch_summarize_sections_rolling(
                sections=sections,
                max_concurrent=max_concurrent,
                window_size=window_size,
                strict_json=strict_json,
                request_timeout=request_timeout,
                timings_dir=timings_dir,
            )
        )
    finally:
        # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
        pass
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
    return output_path


def _cmd_test():
    """Test with a single section."""
    try:
        require_scillm_preflight()
    except RuntimeError as exc:
        console.print(f"[red]Stage 09 SciLLM preflight failed: {exc}[/red]")
        raise

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


if __name__ == "__main__":
    # Minimal entry: INPUT_JSON [OUT_DIR]  or  --bundle BUNDLE_JSON [OUT_DIR]
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception:
        pass
    import sys
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.09_section_summarizer INPUT_JSON [OUT_DIR]\n"
            "   or: python -m extractor.pipeline.steps.09_section_summarizer --bundle BUNDLE_JSON [OUT_DIR]",
            file=sys.stderr,
        )
        sys.exit(2)
    out_dir = Path("data/results/pipeline")
    if argv[0] == "--bundle":
        if len(argv) < 2:
            print("--bundle requires a path", file=sys.stderr)
            sys.exit(2)
        bundle = Path(argv[1])
        out_dir = Path(argv[2]) if len(argv) > 2 else out_dir
        out = _cmd_debug_bundle(bundle=bundle, output_dir=out_dir)
        print(str(out))
    else:
        input_json = Path(argv[0])
        out_dir = Path(argv[1]) if len(argv) > 1 else out_dir
        out = _cmd_run(
            input_json=input_json,
            output_dir=out_dir,
        )
        print(str(out))
