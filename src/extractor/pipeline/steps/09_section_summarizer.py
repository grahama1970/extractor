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
from typing import Dict, List, Any, Optional
from datetime import datetime
from textwrap import dedent

# Third-party
from loguru import logger
try:
    try:
        import typer
        _HAS_TYPER = True
    except Exception:
        _HAS_TYPER = False
        class _TyperShim:
            def __init__(self,*a,**k): pass
            def command(self,*a,**k): return lambda f: f
            def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
        def _opt(*a,**k): return None
        def _arg(*a,**k): return None
        typer = _TyperShim()  # type: ignore
        typer.Typer = _TyperShim  # type: ignore
        typer.Option = _opt  # type: ignore
        typer.Argument = _arg  # type: ignore
        typer.secho = print  # type: ignore

    _HAS_TYPER = True
except Exception:
    _HAS_TYPER = False
    class _TyperShim:
        def __init__(self,*a,**k): pass
        def command(self,*a,**k): return lambda f: f
        def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
    def _opt(*a,**k): return None
    def _arg(*a,**k): return None
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Option = _opt  # type: ignore
    typer.Argument = _arg  # type: ignore
    typer.secho = print  # type: ignore

from rich.console import Console
from tqdm.asyncio import tqdm
from extractor.pipeline.utils.litellm_call import litellm_call
from extractor.pipeline.utils.diagnostics import get_run_id

# Import JSON utilities
from extractor.core.services.utils.json_utils import clean_json_string
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD

# FAIL FAST - simple env loading
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache
if not load_dotenv(find_dotenv()):
    logger.error("No .env file found - check .env exists")
    sys.exit(1)
try:
    initialize_litellm_cache()
except Exception as _e:
    logger.warning(f"LiteLLM cache init failed (continuing): {_e}")

logger.remove()
logger.add(sys.stderr, level="INFO")

app = typer.Typer(help="Generate concurrent summaries for PDF sections")
console = Console()


async def summarize_section(
    section: Dict[str, Any], 
    semaphore: asyncio.Semaphore,
    previous_summaries: List[Dict[str, Any]] = None,
    window_size: int = 3,
    strict_json: bool = True,
) -> Dict[str, Any]:
    """Generate a summary for a single section using LiteLLM with optional rolling context."""
    prev = previous_summaries or []
    async with semaphore:
        try:
            # Build rolling context
            prev_text = "\n".join(
                f"- {p.get('section_title', 'Untitled')}: {p.get('summary_data',{}).get('summary','')}"
                for p in prev if p.get('success')
            )
            base_text = section.get('reflowed_text') or section.get('merged_text') or section.get('raw_text') or ''
            prompt = dedent(f"""
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
            """).strip()

            # Prefer explicit JSON formatting via system guard + provider JSON mode (when supported)
            system_json_guard = JSON_SYSTEM_GUARD
            model_name = (
                os.getenv("LITELLM_MODEL")
                or os.getenv("LITELLM_DEFAULT_MODEL")
                or os.getenv("LITELLM_SMALL_MODEL")
                or "openai/gpt-5-mini"
            )
            # Use the shared LiteLLM batch runner for consistency with other stages
            is_gpt5 = "gpt-5" in (model_name or "").lower()
            params = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_json_guard},
                    {"role": "user", "content": prompt},
                ],
                "timeout": 120,
                "max_tokens": 700,
            }
            if not is_gpt5:
                params["temperature"] = 0.3
            if strict_json:
                params["response_format"] = {"type": "json_object"}
            sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
            out = await litellm_call([params], concurrency=1, desc="summarize_section", session_id=sid)
            content = out[0] if out else ""
            result = clean_json_string(content, return_dict=True)
            if strict_json and (not isinstance(result, dict) or 'summary' not in result):
                # Fail fast when strict JSON is requested
                raise ValueError(f"Invalid JSON from LLM (strict mode). Raw snippet: {str(content)[:200]}")
            if not isinstance(result, dict) or 'summary' not in result:
                try:
                    logger.debug(f"LLM summary raw content (snippet): {(content or '')[:180]}")
                except Exception:
                    pass
                raise ValueError("Invalid LLM summary JSON")
            return {
                "section_id": section.get('id'),
                "section_title": section.get('title'),
                "section_level": section.get('level', 0),
                "summary_data": {"summary": result.get('summary',''), "key_concepts": result.get('key_concepts', [])},
                "success": True
            }
        except Exception as e:
            logger.warning(f"Summarize fallback for {section.get('title')}: {e}")
            # Fallback: first 300 chars + naive key concepts split
            text = (section.get('reflowed_text') or section.get('merged_text') or section.get('raw_text') or '')
            return {
                "section_id": section.get('id'),
                "section_title": section.get('title'),
                "section_level": section.get('level', 0),
                "summary_data": {"summary": text[:300], "key_concepts": []},
                "success": False
            }


async def create_checkpoint_summary(
    summaries: List[Dict[str, Any]],
    checkpoint_name: str = "Chapter"
) -> Dict[str, Any]:
    """Create a higher-level summary of multiple sections.
    
    Used to create periodic checkpoints that summarize large chunks
    of the document, preventing context overflow.
    """
    if not summaries:
        return None
        
    successful_summaries = [s for s in summaries if s.get('success')]
    if not successful_summaries:
        return None
    
    # Collect all summaries
    summary_texts = []
    all_concepts = []
    
    for s in successful_summaries:
        if s.get('summary_data'):
            summary_texts.append(f"- {s['section_title']}: {s['summary_data']['summary']}")
            all_concepts.extend(s['summary_data'].get('key_concepts', []))
    
    prompt = dedent(f"""
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
    """).strip()
    
    try:
        system_json_guard = (
            "You output ONLY well-formed JSON objects. No prose, markdown, or extra text. "
            "Use double-quoted keys/strings and no trailing commas."
        )
        model_name = (
            os.getenv("LITELLM_MODEL")
            or os.getenv("LITELLM_DEFAULT_MODEL")
            or os.getenv("LITELLM_SMALL_MODEL")
            or "openai/gpt-5-mini"
        )
        is_gpt5 = "gpt-5" in (model_name or "").lower()
        params: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_json_guard},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "timeout": 120,
            "max_tokens": 1024,
        }
        if not is_gpt5:
            params["temperature"] = 0.3
        sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
        out = await litellm_call([params], concurrency=1, desc="checkpoint_summary", session_id=sid)
        content = out[0] if out else ""
        result = clean_json_string(content, return_dict=True)
        
        return {
            "type": "checkpoint",
            "name": checkpoint_name,
            "sections_covered": len(successful_summaries),
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to create checkpoint summary: {e}")
        return None


async def batch_summarize_sections_rolling(
    sections: List[Dict[str, Any]],
    max_concurrent: int = 5,
    window_size: int = 3,
    checkpoint_interval: int = 20,
    strict_json: bool = True,
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
        s for s in sections
        if s.get('reflow_status') in ['success', 'success_placeholder', 'fallback']
           and (s.get('reflowed_text') or s.get('raw_text'))
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
            batch = valid_sections[i:i + batch_size]
            
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
                        "summary_data": {
                            "summary": last_checkpoint['data']['checkpoint_summary']
                        },
                        "success": True
                    }
                    context_summaries.insert(0, checkpoint_summary)
                
                task = summarize_section(
                    section=section,
                    semaphore=semaphore,
                    previous_summaries=context_summaries,
                    window_size=window_size + 1 if last_checkpoint else window_size,
                    strict_json=strict_json,
                )
                tasks.append((i + j, task))  # Store index for ordering
            
            # Process batch concurrently with order preserved
            positions, coros = zip(*tasks) if tasks else ([], [])
            results = await asyncio.gather(*coros) if coros else []
            batch_results = [None] * len(results)
            for pos, res in zip(positions, results):
                batch_results[pos - i] = res
                if res.get('success'):
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
                    f"Checkpoint {len(all_summaries) // checkpoint_interval}"
                )
                if checkpoint:
                    last_checkpoint = checkpoint
                    checkpoint_buffer = []  # Reset buffer
                    # Add checkpoint to results
                    all_summaries.append({
                        "section_id": f"checkpoint_{len(all_summaries)}",
                        "section_title": checkpoint['name'],
                        "section_level": -1,
                        "summary_data": checkpoint['data'],
                        "success": True,
                        "is_checkpoint": True,
                        "sections_covered": checkpoint['sections_covered']
                    })
    
    # Final checkpoint for remaining sections
    if checkpoint_buffer:
        logger.info(f"Creating final checkpoint for {len(checkpoint_buffer)} sections...")
        checkpoint = await create_checkpoint_summary(
            checkpoint_buffer,
            "Final Checkpoint"
        )
        if checkpoint:
            all_summaries.append({
                "section_id": f"checkpoint_final",
                "section_title": checkpoint['name'],
                "section_level": -1,
                "summary_data": checkpoint['data'],
                "success": True,
                "is_checkpoint": True,
                "sections_covered": checkpoint['sections_covered']
            })
    
    return all_summaries


@app.command()
def run(
    input_json: Path = typer.Argument(..., help="Path to Stage 08 (theorems) or Stage 07 (reflow) JSON output.", exists=True),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    max_concurrent: int = typer.Option(5, help="Maximum concurrent LLM calls"),
    window_size: int = typer.Option(3, help="Rolling window size for context"),
    strict_json: bool = typer.Option(True, "--strict-json/--no-strict-json", help="Require provider JSON mode or allow free-form parsing"),
):
    """Generates summaries for all sections using concurrent processing."""
    console.print("[bold green]Starting Section Summarization (Stage 09)[/bold green]")

    # --- Directory and Data Setup ---
    stage_output_dir = output_dir / "09_section_summarizer"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    with open(input_json, 'r') as f:
        pipeline_data = json.load(f)
    
    sections = pipeline_data.get("reflowed_sections", [])
    
    if not sections:
        console.print("[yellow]No reflowed sections found in input file. Exiting.[/yellow]")
        return

    console.print(f"Found {len(sections)} sections to summarize.")
    
    # --- Concurrent Summarization ---
    summaries = asyncio.run(batch_summarize_sections_rolling(
        sections=sections,
        max_concurrent=max_concurrent,
        window_size=window_size,
        strict_json=strict_json,
    ))
    
    successful_count = sum(1 for s in summaries if s.get('success'))
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
    with open(output_path, 'w') as f:
        json.dump(final_output, f, indent=2)
    
    console.print(f"📄 Results saved to: {output_path}")

@app.command("debug-bundle")
def debug_bundle(
    bundle: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Bundle with key: reflowed_sections (list)"),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    max_concurrent: int = typer.Option(5, help="Maximum concurrent LLM calls"),
    window_size: int = typer.Option(3, help="Rolling window size for context"),
    strict_json: bool = typer.Option(True, "--strict-json/--no-strict-json", help="Require provider JSON mode or allow free-form parsing"),
):
    """Run Stage 09 summarization from a consolidated list of sections."""
    stage_output_dir = output_dir / "09_section_summarizer"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        sections = data.get('reflowed_sections') or []
        if not isinstance(sections, list) or not sections:
            raise ValueError("Bundle must include non-empty 'reflowed_sections' list")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED); raise typer.Exit(1)

    summaries = asyncio.run(batch_summarize_sections_rolling(sections=sections, max_concurrent=max_concurrent, window_size=window_size, strict_json=strict_json))
    successful_count = sum(1 for s in summaries if s.get('success'))
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



@app.command()
def test():
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
        """
    }
    
    # Test single section
    result = asyncio.run(summarize_section(
        section=test_section,
        semaphore=asyncio.Semaphore(1),
        previous_summaries=None,
        window_size=3
    ))
    
    console.print("\n[bold]Test Result:[/bold]")
    console.print(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
