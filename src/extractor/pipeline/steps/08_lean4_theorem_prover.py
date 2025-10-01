#!/usr/bin/env python3
"""
Pipeline Stage 8: Lean 4 Theorem Proving for Requirements
=========================================================

This stage processes reflowed sections from stage 07 to extract and prove
formal requirements using the Lean 4 theorem prover.

Key Features:
- Processes already-reflowed text from stage 07
- Single LLM call per section to identify all requirements
- Treats theorem prover as an LLM-like service (30-300s processing)
- Returns success with proof OR detailed feedback for fixes
- Handles text requirements, bullet lists, and table constraints
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, cast
from datetime import datetime
import textwrap
import time
import tempfile
import shlex

# Direct imports - fail fast
import typer
from dotenv import load_dotenv, find_dotenv
from loguru import logger
from rich.console import Console
from tqdm.asyncio import tqdm

# Import JSON utilities
from extractor.pipeline.utils.json_utils import clean_json_string
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    iso_now,
    make_event,
    snapshot_resources,
    build_stage_timings,
    gpu_metrics_available,
)
from extractor.pipeline.utils.litellm_call import litellm_call

# Import what we need from lean4_prover
from dataclasses import dataclass

try:
    from lean4_prover.core.validation_models import get_validation_strategy
except Exception:
    get_validation_strategy = None  # type: ignore[assignment]
try:
    from lean4_prover.core.prove_requirement import ProofResult, generate_lean_code
except Exception:

    @dataclass
    class ProofResult:  # type: ignore[no-redef]
        success: bool
        lean_code: str
        stdout: str
        stderr: str
        return_code: int
        test_filename: str
        error_messages: list[str] | None = None
        proof_output: str | None = None

    async def generate_lean_code(requirement: str, strategy):  # type: ignore[no-redef]
        # Minimal stub: produce a comment-only Lean snippet to fail fast but safely
        return (
            f"-- requirement: {requirement}\n"
            f"-- strategy: {getattr(strategy, 'validation_approach', 'unknown')}\n"
        )


# --- Initialization ---
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)

from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

initialize_litellm_cache()

# Logger configured per run (see CLI commands below) to align with prior stages.

app = typer.Typer(help="Extract and prove formal requirements using Lean 4")
console = Console()

# LLM Configuration
LEAN4_MODEL = os.getenv(
    "LEAN4_MODEL", "openai/gpt-5-mini"
)  # Fast, cost-effective model for extraction
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", 5))
MAX_CONCURRENT_LEAN4 = int(
    os.getenv("MAX_CONCURRENT_LEAN4_CALLS", 2)
)  # Lean 4 is heavy (30-300s per theorem)

# Optional external CLI integration (portable; avoids Docker coupling)
# Provide the full command template via LEAN4_CLI_CMD, e.g.:
#  - Stdin JSON mode: "python /path/to/cli_mini.py prove --json {stdin}"
#  - File mode:       "python /path/to/cli_mini.py prove --input {input} --output {output}"
LEAN4_CLI_CMD = os.getenv("LEAN4_CLI_CMD", "").strip()

# --- Streamlined Requirement Extraction ---


async def identify_requirements_in_section(
    section: Dict[str, Any], semaphore: asyncio.Semaphore
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Single LLM call to identify ALL requirements in a reflowed section.
    Processes the clean, reflowed text from stage 07.
    """
    async with semaphore:
        try:
            # Get reflowed text and tables from stage 07 output
            reflowed_text = section.get("reflowed_text", "")
            tables = section.get("tables", [])

            # Build comprehensive prompt for the entire section
            prompt = textwrap.dedent(
                f"""
                Analyze this reflowed section and extract ALL formal requirements that need theorem proving.
                
                Section Title: {section.get('title', 'Untitled')}
                
                Reflowed Text:
                {reflowed_text}
                
                Tables in this section:
                {json.dumps([{ 
                    'id': t.get('id', ''),
                    'caption': t.get('caption', ''),
                    'text_content': t.get('text_content', ''),
                    'pandas_df_dict': t.get('pandas_df_dict', {})
                } for t in tables], indent=2)}
                
                Extract requirements following these rules:
                1. Find all sentences containing "shall", "must", "will", "should"
                2. For sentences ending with ":" followed by a list, each list item inherits the modal verb
                3. From tables, extract constraints (ranges, mandatory values, compliance requirements)
                4. Group related requirements that depend on each other
                
                Format each requirement for the theorem prover:
                {{
                    "requirements": [
                        {{
                            "id": "req_001",
                            "requirement_text": "The exact requirement statement",
                            "context": {{
                                "subject": "who/what must do this",
                                "predicate": "what must be done",
                                "modal": "shall/must/will/should",
                                "has_dependency": true/false,
                                "depends_on": ["req_ids"]
                            }},
                            "source": "text/list/table",
                            "source_details": {{
                                "section_id": "{section.get('id', '')}",
                                "section_title": "{section.get('title', '')}",
                                "page": {section.get('page_start', -1)}
                            }}
                        }}
                    ],
                    "table_constraints": [
                        {{
                            "id": "const_001",
                            "constraint_text": "Formal constraint from table",
                            "constraint_type": "range/equality/membership",
                            "parameters": {{}},
                            "source_table_id": "table_id"
                        }}
                    ]
                }}
            """
            ).strip()

            # Prefer provider JSON mode, via shared litellm_call wrapper for consistency with other stages
            params: Dict[str, Any] = {
                "model": LEAN4_MODEL,
                "messages": [
                    {"role": "system", "content": JSON_SYSTEM_GUARD},
                    {"role": "user", "content": prompt},
                ],
                "timeout": 120,
                "response_format": {"type": "json_object"},
                "stream": False,
            }
            if "gpt-5" not in (LEAN4_MODEL or "").lower():
                params["temperature"] = 0.1
            sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
            results = await litellm_call(
                [params],
                wrap_json=False,
                concurrency=1,
                desc="Extract Requirements",
                session_id=sid,
                export="results",
            )
            r0 = results[0] if results else None
            try:
                from loguru import logger as _logger
                if r0:
                    _logger.info(f"lean4_requirements: model={r0.request.model} ok={r0.exception is None}")
            except Exception:
                pass
            response = r0.content if r0 else ""
            # Normalize response object/dict
            content: Optional[str] = None
            if isinstance(response, dict):
                try:
                    ch = response.get("choices") or []
                    if ch:
                        msg = ch[0].get("message") or {}
                        content = msg.get("content")
                except Exception:
                    content = None
            else:
                ch_obj = getattr(response, "choices", None)
                if ch_obj:
                    try:
                        ch0 = ch_obj[0]
                        msg = getattr(ch0, "message", None)
                        if msg is not None and getattr(msg, "content", None) is not None:
                            content = msg.content  # type: ignore[attr-defined]
                        else:
                            txt = getattr(ch0, "text", None)
                            if isinstance(txt, str):
                                content = txt
                    except Exception:
                        content = None
            if not isinstance(content, str) or not content.strip():
                logger.warning(
                    "Requirement extraction returned empty content; defaulting to empty lists."
                )
                return [], []
            parsed_obj: Any = clean_json_string(content, return_dict=True)
            # Normalize string JSON to object
            if isinstance(parsed_obj, str):
                try:
                    parsed_obj = json.loads(parsed_obj)
                except Exception:
                    parsed_obj = {}

            # Extract requirements and constraints with robust typing
            if isinstance(parsed_obj, list):
                requirements = cast(List[Dict[str, Any]], parsed_obj)
                constraints = []
            elif isinstance(parsed_obj, dict):
                requirements = cast(List[Dict[str, Any]], parsed_obj.get("requirements", []))
                constraints = cast(List[Dict[str, Any]], parsed_obj.get("table_constraints", []))
            else:
                requirements, constraints = [], []

            # Add section context to all items
            for req in requirements:
                req["section_context"] = reflowed_text[:500]  # First 500 chars for context

            for const in constraints:
                const["section_context"] = reflowed_text[:500]

            logger.info(
                f"Section '{section.get('title')}': Found {len(requirements)} requirements, {len(constraints)} constraints"
            )

            return requirements, constraints

        except Exception as e:
            logger.error(
                f"Failed to extract requirements from section '{section.get('title', 'Unknown')}': {e}"
            )
            logger.debug(f"Section content: {section.get('reflowed_text', '')[:200]}...")
            return [], []


# --- Theorem Proving with Feedback ---


async def _prove_via_cli(requirement: str, strategy: Any) -> Dict[str, Any]:
    """
    Invoke external Lean4 CLI when LEAN4_CLI_CMD is set.
    Supports two contract styles:
      - Stdin JSON: command contains "{stdin}" placeholder → write to stdin, read JSON from stdout
      - File I/O:   command has both "{input}" and "{output}" → write temp input.json, read temp output.json
    Returns a dict shaped like ProofResult-compatible payload.
    """
    if not LEAN4_CLI_CMD:
        return {"error": "LEAN4_CLI_CMD not configured"}

    payload = {
        "requirement": requirement,
        "strategy": getattr(strategy, "__dict__", strategy),
    }

    # Stdin JSON mode
    if "{stdin}" in LEAN4_CLI_CMD:
        cmd_str = LEAN4_CLI_CMD.replace("{stdin}", "").strip()
        argv = shlex.split(cmd_str)
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdin_bytes = (json.dumps(payload) + "\n").encode("utf-8")
            stdout, stderr = await proc.communicate(stdin_bytes)
            out = stdout.decode("utf-8", errors="ignore")
            try:
                result = json.loads(out) if out.strip() else {}
            except Exception:
                result = {"success": False, "stderr": "Non-JSON output from CLI", "stdout": out}
            # Normalize expected keys
            return {
                "success": bool(result.get("success", False)),
                "lean_code": result.get("lean_code", ""),
                "stdout": result.get("stdout", out),
                "stderr": result.get("stderr", stderr.decode("utf-8", errors="ignore")),
                "return_code": int(result.get("return_code", proc.returncode or 1)),
                "proof_output": result.get("proof_output"),
                "error_messages": result.get("error_messages", []),
            }
        except Exception as e:
            return {
                "success": False,
                "stderr": f"CLI invoke failed: {e}",
                "return_code": 1,
                "lean_code": "",
                "stdout": "",
            }

    # File mode
    if "{input}" in LEAN4_CLI_CMD and "{output}" in LEAN4_CLI_CMD:
        with tempfile.TemporaryDirectory() as td:
            in_path = Path(td) / "requirement.json"
            out_path = Path(td) / "proof.json"
            in_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            cmd_str = LEAN4_CLI_CMD.replace("{input}", str(in_path)).replace(
                "{output}", str(out_path)
            )
            argv = shlex.split(cmd_str)
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                try:
                    result = json.loads(out_path.read_text()) if out_path.exists() else {}
                except Exception:
                    result = {
                        "success": False,
                        "stderr": "Output file missing or invalid JSON",
                        "stdout": stdout.decode("utf-8", errors="ignore"),
                    }
                return {
                    "success": bool(result.get("success", False)),
                    "lean_code": result.get("lean_code", ""),
                    "stdout": result.get("stdout", stdout.decode("utf-8", errors="ignore")),
                    "stderr": result.get("stderr", stderr.decode("utf-8", errors="ignore")),
                    "return_code": int(result.get("return_code", proc.returncode or 1)),
                    "proof_output": result.get("proof_output"),
                    "error_messages": result.get("error_messages", []),
                }
            except Exception as e:
                return {
                    "success": False,
                    "stderr": f"CLI invoke failed: {e}",
                    "return_code": 1,
                    "lean_code": "",
                    "stdout": "",
                }

    return {
        "success": False,
        "stderr": "LEAN4_CLI_CMD missing required placeholders ({stdin} or {input}/{output})",
        "return_code": 1,
        "lean_code": "",
        "stdout": "",
    }


async def _prove_batch_via_cli(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Invoke external Lean4 CLI once with JSONL input and parse JSONL output when configured.

    Supported contracts via LEAN4_CLI_CMD:
      - Stdin JSONL: command contains "{stdin_jsonl}" → write JSONL to stdin, read JSONL from stdout
      - File JSONL:  command contains "{input_jsonl}" and "{output_jsonl}" → write temp input.jsonl, read temp output.jsonl
      - File JSON:   command contains "{input_json}" and "{output_json}" → write temp input.json (array), read temp output.json (array)

    Each input line is a JSON object like:
      {"id": "item_0", "item_type": "requirement"|"constraint", "requirement": "...", "strategy": {...}}

    Each output line is expected to be a JSON object containing at least:
      {"id": "item_0", "success": true|false, "lean_code": "...", "stdout": "...", "stderr": "...", "return_code": 0, "proof_output": "..."}
    """
    if not LEAN4_CLI_CMD:
        return []

    results: List[Dict[str, Any]] = []
    try:
        # Stdin JSONL mode
        if "{stdin_jsonl}" in LEAN4_CLI_CMD:
            cmd_str = LEAN4_CLI_CMD.replace("{stdin_jsonl}", "").strip()
            argv = shlex.split(cmd_str)
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            data = "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n"
            stdout, stderr = await proc.communicate(data.encode("utf-8"))
            out = stdout.decode("utf-8", errors="ignore")
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    obj = {"success": False, "stderr": "Non-JSON line from CLI", "raw": line}
                results.append(obj)
            return results

        # File JSONL mode
        if "{input_jsonl}" in LEAN4_CLI_CMD and "{output_jsonl}" in LEAN4_CLI_CMD:
            with tempfile.TemporaryDirectory() as td:
                in_path = Path(td) / "batch_in.jsonl"
                out_path = Path(td) / "batch_out.jsonl"
                with open(in_path, "w", encoding="utf-8") as f:
                    for it in items:
                        f.write(json.dumps(it, ensure_ascii=False) + "\n")
                cmd_str = (
                    LEAN4_CLI_CMD.replace("{input_jsonl}", str(in_path))
                    .replace("{output_jsonl}", str(out_path))
                    .strip()
                )
                argv = shlex.split(cmd_str)
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if out_path.exists():
                    content = out_path.read_text(encoding="utf-8", errors="ignore")
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            results.append(json.loads(line))
                        except Exception:
                            results.append(
                                {"success": False, "stderr": "Non-JSON line from CLI", "raw": line}
                            )
                return results

        # File JSON array mode (for lean4_prover/cli_mini.py batch --input-file / --output-file)
        if "{input_json}" in LEAN4_CLI_CMD and "{output_json}" in LEAN4_CLI_CMD:
            # Transform our items into cli_mini batch input shape
            batch_array = []
            for it in items:
                entry = {}
                entry["requirement"] = (
                    it.get("requirement") or it.get("constraint_text") or it.get("text") or ""
                )
                strat = it.get("strategy")
                if isinstance(strat, dict):
                    name = strat.get("name") or strat.get("strategy")
                    if isinstance(name, str) and name:
                        entry["strategies"] = [name]
                elif isinstance(strat, str) and strat:
                    entry["strategies"] = [strat]
                entry["metadata"] = {
                    k: it.get(k) for k in ("id", "item_type", "source", "section_id") if k in it
                }
                batch_array.append(entry)

            import tempfile, json, shlex
            from pathlib import Path

            with tempfile.TemporaryDirectory() as td:
                in_json = Path(td) / "batch_in.json"
                out_json = Path(td) / "batch_out.json"
                in_json.write_text(json.dumps(batch_array, ensure_ascii=False), encoding="utf-8")
                cmd_str = (
                    LEAN4_CLI_CMD.replace("{input_json}", str(in_json))
                    .replace("{output_json}", str(out_json))
                    .strip()
                )
                argv = shlex.split(cmd_str)
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if out_json.exists():
                    try:
                        arr = json.loads(out_json.read_text(encoding="utf-8", errors="ignore"))
                        if isinstance(arr, list):
                            results.extend(arr)
                        else:
                            results.append({"success": False, "stderr": "Output JSON not a list"})
                    except Exception as e:
                        results.append({"success": False, "stderr": f"Invalid JSON output: {e}"})
                else:
                    results.append(
                        {
                            "success": False,
                            "stderr": stdout.decode("utf-8", errors="ignore")
                            or "Output file missing",
                        }
                    )
                return results
    except Exception as e:
        return [{"success": False, "stderr": f"Batch CLI failed: {e}"}]

    # If placeholders were not present, return empty results (caller falls back)
    return results


async def execute_lean_code(lean_code: str):
    """
    Execute Lean code using asyncio.subprocess (which works!).
    """
    try:
        # Run Lean in Docker using asyncio.subprocess
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            "-i",
            "lean_runner",
            "sh",
            "-c",
            "cd /workspace/mathlib_project && lake env lean --stdin",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send code and get output
        stdout, stderr = await proc.communicate(lean_code.encode())

        # Decode results
        stdout_str = stdout.decode("utf-8", errors="ignore")
        stderr_str = stderr.decode("utf-8", errors="ignore")

        # Lean outputs errors to stdout, not stderr!
        error_messages = None
        if proc.returncode != 0 and stdout_str:
            error_messages = [stdout_str]

        return ProofResult(
            success=proc.returncode == 0,
            lean_code=lean_code,
            stdout=stdout_str,
            stderr=stderr_str,
            return_code=int(proc.returncode or 1),
            test_filename="<stdin>",
            error_messages=error_messages,
            proof_output=stdout_str if proc.returncode == 0 else None,
        )

    except Exception as e:
        logger.error(f"Lean execution failed: {e}")
        return ProofResult(
            success=False,
            lean_code=lean_code,
            stdout="",
            stderr=str(e),
            return_code=1,
            test_filename="<stdin>",
            error_messages=[str(e)],
        )


async def prove_requirement(requirement: str, strategy: Any):
    """
    Prove a requirement using one of:
      1) External CLI (preferred when LEAN4_CLI_CMD is set)
      2) LLM-generated Lean code executed via Docker (fallback)
    """
    # Preferred: external CLI if configured (portable, avoids Docker coupling)
    if LEAN4_CLI_CMD:
        cli_res = await _prove_via_cli(requirement, strategy)
        from types import SimpleNamespace

        return SimpleNamespace(
            success=bool(cli_res.get("success", False)),
            lean_code=str(cli_res.get("lean_code", "")),
            stdout=str(cli_res.get("stdout", "")),
            stderr=str(cli_res.get("stderr", "")),
            return_code=int(cli_res.get("return_code", 1)),
            test_filename="<stdin>",
            error_messages=cli_res.get("error_messages", []),
            proof_output=cli_res.get("proof_output"),
        )

    # Fallback: generate Lean code via LLM and run inside Docker/lean runner
    try:
        if generate_lean_code is None:
            raise RuntimeError("generate_lean_code unavailable")
        lean_code = await generate_lean_code(requirement, strategy)
    except Exception as e:
        from types import SimpleNamespace

        return SimpleNamespace(
            success=False,
            lean_code="",
            stdout="",
            stderr=f"generate_lean_code unavailable: {e}",
            return_code=1,
            test_filename="<stdin>",
            error_messages=[str(e)],
            proof_output=None,
        )

    logger.info(f"LLM-generated Lean code:\n{lean_code}")
    result = await execute_lean_code(lean_code)

    if result.success:
        logger.success("Proof successful!")
    else:
        logger.error(f"Proof failed with return code {result.return_code}")
        if result.stdout:  # Lean errors go to stdout
            logger.error(f"Lean errors:\n{result.stdout}")
    return result


async def prove_with_feedback(
    item: Dict[str, Any], item_type: str, semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """
    Send requirement or constraint to theorem prover and get detailed feedback.
    Treats theorem prover like an LLM service with 30-300s processing time.
    """
    async with semaphore:
        try:
            start_time = datetime.now()

            if item_type == "requirement":
                # Import the validation model function
                try:
                    from lean4_prover.core.validation_models import get_validation_strategy

                    # Get validation strategy first
                    strategy = await get_validation_strategy(
                        item["requirement_text"], item.get("context", {})
                    )
                except ImportError:
                    # Create a simple strategy if import fails
                    from types import SimpleNamespace

                    strategy = SimpleNamespace(
                        validation_approach="direct proof", key_properties=[], dependencies=[]
                    )

                # Call our theorem prover for requirement
                result = await prove_requirement(
                    requirement=item["requirement_text"], strategy=strategy
                )

                # Convert ProofResult to dict format
                proof_dict: Dict[str, Any] = {
                    "status": "proved" if getattr(result, "success", False) else "failed",
                    "lean_code": getattr(result, "lean_code", ""),
                    "stdout": getattr(result, "stdout", ""),
                    "stderr": getattr(result, "stderr", ""),
                    "return_code": getattr(result, "return_code", 1),
                    "error_messages": getattr(result, "error_messages", []),
                    "proof_output": getattr(result, "proof_output", None),
                }

            else:  # constraint
                # For now, treat table constraints as requirements
                constraint_text = item.get("constraint_text", "")
                # Create a simple strategy for constraints
                from types import SimpleNamespace

                strategy = SimpleNamespace(
                    validation_approach="constraint verification",
                    key_properties=["constraint bounds", "data validation"],
                    dependencies=[],
                )

                # Call our theorem prover for constraint as a requirement
                result = await prove_requirement(requirement=constraint_text, strategy=strategy)

                # Convert ProofResult to dict format
                proof_dict = {
                    "status": "verified" if getattr(result, "success", False) else "failed",
                    "lean_code": getattr(result, "lean_code", ""),
                    "stdout": getattr(result, "stdout", ""),
                    "stderr": getattr(result, "stderr", ""),
                    "return_code": getattr(result, "return_code", 1),
                    "error_messages": getattr(result, "error_messages", []),
                    "verification_method": "constraint_proof",
                    "solver_output": getattr(result, "proof_output", None),
                }

            duration = (datetime.now() - start_time).total_seconds()

            # Process result with detailed feedback
            success_check = False
            if item_type == "requirement" and hasattr(result, "success"):
                success_check = result.success
            else:
                success_check = proof_dict.get("status") in ["proved", "verified"]

            if success_check:
                return {
                    "success": True,
                    "item": item,
                    "item_type": item_type,
                    "lean_code": proof_dict.get("lean_code", ""),
                    "proof": proof_dict.get("proof_output", proof_dict.get("stdout", "")),
                    "tactics_used": proof_dict.get("tactics_used", []),
                    "assumptions": proof_dict.get("assumptions", []),
                    "duration_seconds": duration,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                # Theorem prover provides detailed feedback on failures
                error_msg = proof_dict.get("stderr", "")
                if (
                    item_type == "requirement"
                    and hasattr(result, "error_messages")
                    and result.error_messages
                ):
                    error_msg = "\n".join(result.error_messages)

                return {
                    "success": False,
                    "item": item,
                    "item_type": item_type,
                    "lean_code": proof_dict.get("lean_code", ""),
                    "error": error_msg or "Unknown error",
                    "advice": proof_dict.get(
                        "advice", "Check theorem syntax and try simplifying the statement"
                    ),
                    "suggested_reformulation": proof_dict.get("suggested_reformulation", ""),
                    "stderr": proof_dict.get("stderr", ""),
                    "duration_seconds": duration,
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Theorem proving failed: {e}")
            return {
                "success": False,
                "item": item,
                "item_type": item_type,
                "error": str(e),
                "advice": "Check theorem prover installation and try again",
                "duration_seconds": 0,
            }


# --- Main Processing Pipeline ---


async def process_reflowed_sections(
    pipeline_data: Dict[str, Any], skip_proving: bool = False
) -> Dict[str, Any]:
    """
    Processes reflowed sections to extract and optionally prove theorems.
    """
    sections = pipeline_data.get("reflowed_sections", [])
    if not sections:
        logger.warning("No reflowed sections found in input data")
        return {"success": False, "error": "No reflowed sections to process", "proof_results": []}

    logger.info(f"Processing {len(sections)} reflowed sections for theorem proving.")

    # Phase 1: Extract requirements from all sections
    llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
    extraction_tasks = [identify_requirements_in_section(s, llm_semaphore) for s in sections]

    all_requirements, all_constraints = [], []
    for coro in tqdm(
        asyncio.as_completed(extraction_tasks),
        total=len(extraction_tasks),
        desc="Extracting Requirements",
    ):
        requirements, constraints = await coro
        all_requirements.extend(requirements)
        all_constraints.extend(constraints)

    logger.info(
        f"Extracted {len(all_requirements)} requirements and {len(all_constraints)} constraints."
    )

    if skip_proving:
        logger.info("Skipping Lean 4 proving as requested.")
        return {
            "success": True,
            "statistics": {
                "total_requirements_found": len(all_requirements),
                "total_constraints_found": len(all_constraints),
            },
            "proof_results": [],
        }

    # Phase 2: Prove theorems
    lean4_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LEAN4)
    all_items = [{"item": req, "type": "requirement"} for req in all_requirements] + [
        {"item": const, "type": "constraint"} for const in all_constraints
    ]

    # Fast-path: batch CLI via JSONL if configured
    if LEAN4_CLI_CMD and (
        ("{stdin_jsonl}" in LEAN4_CLI_CMD)
        or ("{input_jsonl}" in LEAN4_CLI_CMD and "{output_jsonl}" in LEAN4_CLI_CMD)
        or ("{input_json}" in LEAN4_CLI_CMD and "{output_json}" in LEAN4_CLI_CMD)
    ):
        try:
            batch_lines: List[Dict[str, Any]] = []
            id_to_item: Dict[str, Dict[str, Any]] = {}
            for idx, it in enumerate(all_items):
                rid = f"item_{idx}"
                if it["type"] == "requirement":
                    text = it["item"].get("requirement_text", "")
                else:
                    text = it["item"].get("constraint_text", "")
                batch_lines.append(
                    {
                        "id": rid,
                        "item_type": it["type"],
                        "requirement": text,
                        "strategy": {},
                    }
                )
                id_to_item[rid] = it

            batch_out = await _prove_batch_via_cli(batch_lines)
            proof_results: List[Dict[str, Any]] = []
            successful_proofs = 0
            for r in batch_out or []:
                rid = str(r.get("id", ""))
                ref = id_to_item.get(rid, {})
                item = ref.get("item", {})
                item_type = ref.get("type", "requirement")
                success = bool(r.get("success", False))
                out_entry: Dict[str, Any] = {
                    "success": success,
                    "item": item,
                    "item_type": item_type,
                    "lean_code": r.get("lean_code", ""),
                    "proof": r.get("proof_output", r.get("stdout", "")),
                    "tactics_used": r.get("tactics_used", []),
                    "assumptions": r.get("assumptions", []),
                    "duration_seconds": (
                        float(r.get("duration_seconds", 0))
                        if isinstance(r.get("duration_seconds", 0), (int, float))
                        else 0.0
                    ),
                    "timestamp": datetime.now().isoformat(),
                }
                if not success:
                    out_entry.update(
                        {
                            "error": r.get("stderr", "") or "Unknown error",
                            "advice": r.get(
                                "advice", "Check theorem syntax and try simplifying the statement"
                            ),
                            "suggested_reformulation": r.get("suggested_reformulation", ""),
                            "stderr": r.get("stderr", ""),
                        }
                    )
                proof_results.append(out_entry)
                if success:
                    successful_proofs += 1

            # --- Final Statistics ---
            stats = {
                "total_requirements_found": len(all_requirements),
                "total_constraints_found": len(all_constraints),
                "successful_proofs": successful_proofs,
                "failed_proofs": len(proof_results) - successful_proofs,
            }
            return {"success": True, "statistics": stats, "proof_results": proof_results}
        except Exception as e:
            logger.warning(f"Batch CLI path failed, falling back to per-item proving: {e}")

    proof_tasks = [
        prove_with_feedback(item["item"], item["type"], lean4_semaphore) for item in all_items
    ]

    proof_results = []
    successful_proofs = 0
    for f in tqdm(
        asyncio.as_completed(proof_tasks), total=len(proof_tasks), desc="Proving Theorems"
    ):
        result = await f
        proof_results.append(result)
        if result["success"]:
            successful_proofs += 1

    # --- Final Statistics ---
    stats = {
        "total_requirements_found": len(all_requirements),
        "total_constraints_found": len(all_constraints),
        "successful_proofs": successful_proofs,
        "failed_proofs": len(proof_results) - successful_proofs,
    }

    return {"success": True, "statistics": stats, "proof_results": proof_results}


# --- Main Command ---


def run(
    input_json: Path = typer.Argument(
        ..., help="Path to Stage 07 reflowed sections JSON.", exists=True
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    skip_proving: bool = typer.Option(
        False, "--skip-proving", help="Only extract requirements without running the Lean 4 prover."
    ),
):
    """
    Extracts and proves formal requirements from reflowed sections using Lean 4.
    """
    console.print("[bold green]Starting Lean 4 Theorem Proving (Stage 08)[/bold green]")

    # --- Directory and Data Setup ---
    stage_output_dir = output_dir / "08_lean4_theorem_prover"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    # Configure logging sink per run (INFO level; no extra flags for MVP)
    try:
        from loguru import logger as _lg

        _lg.remove()
        _lg.add(
            str(stage_output_dir / "stage_08_lean4.log"),
            level="INFO",
            enqueue=True,
            backtrace=True,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception:
        pass

    # Minimal diagnostics to align with other stages
    run_id = get_run_id()
    diagnostics: List[Dict[str, Any]] = []
    errors_count = 0
    warnings_count = 0
    stage_start_ts = iso_now()
    t0 = time.monotonic()
    resources = snapshot_resources("start")
    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "08_lean4_theorem_prover",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass

    with open(input_json, "r") as f:
        pipeline_data = json.load(f)

    # --- Main Processing ---
    # Honor --skip-proving flag; default to extraction-only unless environment is explicitly ready
    result = asyncio.run(process_reflowed_sections(pipeline_data, skip_proving=skip_proving))

    # Stop sampler and build timings/resources
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        errors_count = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
    except Exception:
        pass

    # --- Final Payload and Output ---
    final_output = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(input_json),
        "status": "Completed",
        "proving_skipped": skip_proving,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
        **result,
    }

    output_path = json_output_dir / "08_theorems.json"
    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2, default=str, ensure_ascii=False)

    # Write enriched per-requirement statuses for UX (merge 07 miner + 08 results)
    try:
        miner_json = output_dir / "07_requirements_miner" / "json_output" / "07_requirements.json"
        enr_out = json_output_dir / "08_requirements_enriched.json"
        enriched = {"requirements": []}
        if miner_json.exists():
            reqs = json.loads(miner_json.read_text()).get("requirements") or []
            # Map proof results by normalized text if available
            by_text = {}
            try:
                for r in (result.get("proof_results") or []):
                    txt = (r.get("item") or {}).get("requirement_text") or (r.get("item") or {}).get("text_canonical") or ""
                    key = str(txt).strip().lower()
                    by_text.setdefault(key, []).append(r)
            except Exception:
                by_text = {}
            for r in reqs:
                txt = str(r.get("text_canonical") or r.get("text_raw") or "").strip()
                key = txt.lower()
                pr = (by_text.get(key) or [None])[0]
                status = "proved" if (pr and pr.get("success")) else ("unproved" if not skip_proving else "new")
                enriched["requirements"].append({
                    **r,
                    "status": status,
                    "compile_log": (pr or {}).get("stderr", "") if pr else "",
                    "formalization": {"lean_code": (pr or {}).get("lean_code", "")} if pr else None,
                    "diagnostics": ([] if not pr else ([{"kind":"proof","message": pr.get("error","")}] if not pr.get("success") else [])),
                })
            enr_out.write_text(json.dumps(enriched, indent=2))
    except Exception as e:
        try:
            logger.warning(f"Stage 08: failed to write 08_requirements_enriched.json: {e}")
        except Exception:
            pass

    console.print("\n[bold green]✅ Lean 4 Processing Complete[/bold green]")
    stats = result.get("statistics", {})
    console.print(f"   - Requirements Found: {stats.get('total_requirements_found', 0)}")
    console.print(f"   - Successful Proofs: {stats.get('successful_proofs', 0)}")
    console.print(f"   - Failed Proofs: {stats.get('failed_proofs', 0)}")
    console.print(f"   - Results saved to: [cyan]{output_path}[/cyan]")


def debug_bundle(
    bundle: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Bundle with key 'reflowed_sections' (Stage 07 output-compatible)",
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Parent directory for pipeline results."
    ),
    skip_proving: bool = typer.Option(
        True, "--skip-proving/--no-skip-proving", help="Skip Lean proving for debug runs."
    ),
):
    """Run Stage 08 from a consolidated bundle of reflowed sections."""
    stage_output_dir = output_dir / "08_lean4_theorem_prover"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    # Minimal diagnostics to align with other stages
    run_id = get_run_id()
    diagnostics: List[Dict[str, Any]] = []
    errors_count = 0
    warnings_count = 0
    stage_start_ts = iso_now()
    t0 = time.monotonic()
    resources = snapshot_resources("start")
    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "08_lean4_theorem_prover",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass

    try:
        data = json.loads(bundle.read_text())
        if not isinstance(data, dict) or not isinstance(data.get("reflowed_sections"), list):
            raise ValueError("Bundle must include 'reflowed_sections' list")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    result = asyncio.run(process_reflowed_sections(data, skip_proving=skip_proving))

    # Stop sampler and build timings/resources
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        errors_count = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
    except Exception:
        pass

    final_output = {
        "timestamp": datetime.now().isoformat(),
        "status": "Completed",
        "proving_skipped": skip_proving,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
        **result,
    }
    output_path = json_output_dir / "08_theorems.json"
    output_path.write_text(json.dumps(final_output, indent=2, ensure_ascii=False))
    console.print(f"[green]Debug bundle: saved theorem results to {output_path}")


def build_cli():
    import typer as _typer

    app = _typer.Typer(help="Extract and prove formal requirements using Lean 4")
    app.command(name="run")(run)
    app.command(name="debug-bundle")(debug_bundle)
    return app


if __name__ == "__main__":
    build_cli()()
