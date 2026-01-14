"""Stage 09 section summarizer runner."""
import json, os, asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
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
    """Generate a summary for a single section using SciLLM (Router), with optional rolling context."""
    prev = previous_summaries or []
    async with semaphore:
        prev_text = "\\n".join(
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

        prompt = PROMPT["user"].format(
            previous_summaries=prev_text or "(none)",
            section_title=section.get("title", "Untitled"),
            section_level=section.get("level", 0),
            section_text=base_text,
        )

        system_json_guard = PROMPT["system"]
        model_name = get_text_model()
        is_gpt5 = "gpt-5" in (model_name or "").lower()
        router = get_text_router()

        t0 = asyncio.get_event_loop().time()
        error: Optional[str] = None
        served_model: Optional[str] = None
        usage: Dict[str, Any] = {}
        content_preview: Optional[str] = None

        try:
            from scillm.batch import parallel_acompletions_iter
            import os
            
            reqs = [{
                "model": "chutes/text",
                "messages": messages_payload,
                "response_format": {"type": "json_object"} if strict_json else None,
                "temperature": 0.0 if is_gpt5 else 0.0,
                "timeout": request_timeout,
                "index": 0
            }]
            
            api_key = os.getenv("CHUTES_API_KEY")
            api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
            
            resp = None
            async for r in parallel_acompletions_iter(
                reqs, api_base=api_base, api_key=api_key, concurrency=1, timeout=request_timeout, 
                response_format={"type": "json_object"} if strict_json else None
            ):
                if r.get("ok"):
                    resp = {
                        "model": r.get("model", "chutes/text"),
                        "usage": r.get("usage"),
                        "choices": [{"message": {"content": r.get("content")}}],
                        "id": r.get("id")
                    }
                else:
                    raise RuntimeError(f"SciLLM Summarizer Error: {r.get('error')}")

            log_llm_call(
                stage_key="09_summarizer",
                task_kind="summarize_section",
                route_name="chutes/text",
                model="chutes/text",
                success=True,
                latency_ms=(asyncio.get_event_loop().time() - t0) * 1000,
                raw_response=resp,
            )
            served_model = getattr(resp, "model", None) or getattr(resp, "id", None) or "chutes/text"
            content = _choice_content(resp)

            if content is None or (isinstance(content, str) and not content.strip()):
                logger.warning(
                    "stage09.router_empty_content section_id=%s model=%s -- retrying via direct SciLLM",
                    section.get("id"),
                    served_model,
                )
                resp_direct = await _direct_scillm_summary_call(
                    messages_payload,
                    response_format={"type": "json_object"} if strict_json else None,
                    timeout=request_timeout,
                )
                content = resp_direct if resp_direct else ""

            content_preview = str(content)[:400] if content is not None else None

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
            if isinstance(result, dict):
                result = restrict_top_level_keys(result, allowed={"summary", "key_concepts"})
            if isinstance(result, dict):
                if not result.get("summary"):
                    fallback = (base_text or "").strip()
                    if len(fallback) > 240:
                        fallback = f"{fallback[:120]} … {fallback[-120:]}"
                    result["summary"] = fallback or "(no content)"
                if not result.get("key_concepts"):
                    result["key_concepts"] = []

            if strict_json and (
                not isinstance(result, dict)
                or "summary" not in result
                or not isinstance(result.get("key_concepts", []), list)
                or any(k not in {"summary", "key_concepts"} for k in result.keys())
            ):
                raise ValueError(
                    f"stage09.invalid_response section_id={section.get('id')} content_preview={content_preview}"
                )

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
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "stage09.summarize_section_error section_id=%s title=%s error=%s",
                section.get("id"),
                section.get("title"),
                error,
            )
            return {
                "section_id": section.get("id"),
                "section_title": section.get("title"),
                "section_level": section.get("level", 0),
                "summary_data": {
                    "summary": "",
                    "key_concepts": [],
                },
                "success": False,
            }
        finally:
            if error:
                 log_llm_call(
                    stage_key="09_summarizer",
                    task_kind="summarize_section_logic",
                    route_name="chutes/text",
                    model="chutes/text",
                    success=False,
                    error_class="LogicError",
                    raw_preview=error,
                )
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
        except Exception as exc:
            logger.warning("stage09.checkpoint_summary_item_error item=%s error=%s", s, exc)
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
        t0 = time.time()
        try:
            reqs = [{
                "model": "chutes/text",
                "messages": [
                    {"role": "system", "content": system_guard},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type":"json_object"},
                "temperature": 0.0,
                "timeout": request_timeout,
                "index": 0
            }]
            
            api_key = os.getenv("CHUTES_API_KEY")
            api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
            
            resp = None
            async for r in parallel_acompletions_iter(
                reqs, api_base=api_base, api_key=api_key, concurrency=1, timeout=request_timeout, response_format={"type": "json_object"}
            ):
                if r.get("ok"):
                    resp = {
                        "model": r.get("model", "chutes/text"),
                        "usage": r.get("usage"),
                        "choices": [{"message": {"content": r.get("content")}}],
                        "id": r.get("id")
                    }
                else:
                    raise RuntimeError(f"SciLLM Checkpoint Error: {r.get('error')}")

            log_llm_call(
                stage_key="09_summarizer",
                task_kind="checkpoint_summary",
                route_name="chutes/text",
                model="chutes/text",
                success=True,
                latency_ms=int((time.time() - t0) * 1000),
                raw_response=resp,
            )
            return resp
        except Exception as exc:
            log_llm_call(
                stage_key="09_summarizer",
                task_kind="checkpoint_summary",
                route_name="chutes/text",
                model="chutes/text",
                success=False,
                latency_ms=int((time.time() - t0) * 1000),
                error_class=type(exc).__name__,
                raw_preview=str(exc),
            )
            raise

    # Try up to 3 attempts total, honoring capacity signals; helper/client handle Retry-After internally
    attempts = 0
    served_model: Optional[str] = None
    usage: Dict[str, Any] = {}

    while True:
        try:
            resp = await _call_once_async()
            break
        except Exception as exc:
            attempts += 1
            msg = str(exc)

            if attempts >= 3:
                logger.error(f"Failed to create checkpoint summary (attempts={attempts}): {exc}")
                # If capacity-related, emit a skip marker so downstream can record it deterministically
                if any(t in msg for t in ("429", "Too Many Requests", "capacity", "maximum capacity")):
                     log_llm_call(
                         stage_key="09_summarizer",
                         task_kind="checkpoint_skip_capacity",
                         route_name="chutes/text",
                         model="chutes/text",
                         success=False,
                         error_class="CapacityError",
                         raw_preview=msg,
                    )
                     return {
                        "type": "checkpoint",
                        "name": checkpoint_name,
                        "sections_covered": len(successful_summaries),
                        "data": {"checkpoint_skipped": "capacity"},
                        "skipped": True,
                        "reason": "capacity",
                    }
                if ("401" in msg) or ("Unauthorized" in msg):
                     log_llm_call(
                          stage_key="09_summarizer",
                          task_kind="checkpoint_skip_auth",
                          route_name="chutes/text",
                          model="chutes/text",
                          success=False,
                          error_class="AuthError",
                          raw_preview=msg,
                     )
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
            logger.error(f"Failed to create checkpoint summary: {exc}")
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
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '09'})
        return None

    # Telemetry handled internally

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
        except Exception as exc:
            log_stage_error(STEP_NAME, exc, {'context': '09'})
            raise
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

    # Final checkpoint: only if buffer meets interval threshold
    if checkpoint_buffer and len(checkpoint_buffer) >= checkpoint_interval:
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
                    except Exception as exc:
                        log_stage_error(STEP_NAME, exc, {'context': '09'})
                        raise
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
        except Exception as exc:
            log_stage_error(STEP_NAME, exc, {'context': '09'})
            raise
            pass
    return all_summaries


def _cmd_run(
    input_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    max_concurrent: int = int(os.getenv("STAGE09_MAX_CONCURRENT", "1")),
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

    # Validate output before writing
    from extractor.pipeline.schemas.summarizer_actual import validate_summarizer09_output
    validated_output, error = validate_summarizer09_output(final_output)
    if error:
        logger.error(f"Stage 09 output validation failed: {error}")
        # Log validation errors but don't fail - this is the second stage to get validation
        final_output["validation_errors"] = [error]
    else:
        # Validation passed - you can optionally replace with validated version
        pass

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
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '09'})
        raise
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
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '09'})
        raise
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
