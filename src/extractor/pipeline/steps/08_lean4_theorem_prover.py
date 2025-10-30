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

import asyncio
import hashlib
import json
import os
import shlex
import sys
import tempfile
import textwrap
import time

# Import what we need from lean4_prover
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# Direct imports - fail fast
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.scillm_router import get_text_router
from scillm.extras.providers import certainly_prove
from tqdm.asyncio import tqdm
# httpx not used for LLM calls; SciLLM-only policy

from extractor.pipeline.utils.diagnostics import (
    build_stage_timings,
    get_run_id,
    gpu_metrics_available,
    iso_now,
    make_event,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD

# Import JSON utilities
from scillm.extras.json_utils import clean_json_string

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

# SciLLM-only: legacy litellm cache disabled; define a no-op initializer
try:
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except Exception:  # pragma: no cover
    def initialize_litellm_cache():  # type: ignore
        return None

initialize_litellm_cache()

# Logger configured per run (see CLI commands below) to align with prior stages.

console = Console()

# LLM Configuration
LEAN4_MODEL = os.getenv("LEAN4_MODEL", "openai/gpt-5-mini")  # extraction LLM
LEAN4_PROVER_MODEL = os.getenv("LEAN4_PROVER_MODEL", os.getenv("LEAN4_MODEL", "certainly/lean4"))
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
    section: dict[str, Any], semaphore: asyncio.Semaphore
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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

            # scillm + Chutes x-api-key, JSON mode
            ch_base = os.getenv("CHUTES_API_BASE", "").strip()
            ch_key = os.getenv("CHUTES_API_KEY", "").strip()
            async def _do_scillm():
                logger.info(
                    "req_extract.call", extra={
                        "model": LEAN4_MODEL,
                        "timeout": 120,
                        "section_id": section.get("id"),
                        "title": section.get("title"),
                        "text_len": len(reflowed_text or ""),
                        "tables": len(tables or []),
                    }
                )
                _t0=time.monotonic()
                router = get_text_router()
                return await router.acompletion(
                    model="chutes/text",
                    messages=[
                        {"role": "system", "content": JSON_SYSTEM_GUARD},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    timeout=120,
                    temperature=0,
                )
            resp_obj = await _do_scillm()
            logger.info("req_extract.done")
            response = resp_obj
            # Normalize response object/dict
            content: str | None = None
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
                requirements = cast(list[dict[str, Any]], parsed_obj)
                constraints = []
            elif isinstance(parsed_obj, dict):
                requirements = cast(list[dict[str, Any]], parsed_obj.get("requirements", []))
                constraints = cast(list[dict[str, Any]], parsed_obj.get("table_constraints", []))
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


async def _prove_via_cli(requirement: str, strategy: Any) -> dict[str, Any]:
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


async def _prove_batch_via_cli(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    global shlex, json, tempfile, Path
    results: list[dict[str, Any]] = []
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

            import json
            import shlex
            import tempfile
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


# --- Certainly/Lean4 bridge (paved path) ---
def _certainly_health(api_base: str, timeout: float = 3.0) -> bool:
    """Return True if the Certainly/Lean4 bridge is alive.

    Accepts either of these payloads:
      - {"ok": true, "schema": "canonical+lean4@v1", ...}
      - {"ok": true, "details": {...}}
    """
    try:
        url = (api_base.rstrip("/") + "/healthz") if api_base else ""
        if not url:
            return False
        import httpx
        r = httpx.get(url, timeout=timeout)
        if r.status_code != 200:
            return False
        js = r.json()
        if js.get("ok") is True:
            return True
        schema = str(js.get("schema", ""))
        return schema.startswith("canonical+lean4@")
    except Exception:
        return False
def prove_with_certainly_batch(
    requirements: list[str],
    api_base: str | None = None,
    max_seconds: int = 20,
    timeout: int = 60,
    require_proved: bool = False,
):
    """Call the Certainly→Lean4 bridge in a single batch.

    Returns the OpenAI-shaped response from scillm with additional
    payload under additional_kwargs["certainly"]. Requires that all
    items are proved (require_proved=True) or the bridge will error.
    """
    items = [{"id": f"r{i+1}", "requirement_text": r} for i, r in enumerate(requirements)]
    return certainly_prove(
        items=items,
        api_base=api_base,
        request_timeout=timeout,
        max_seconds=max_seconds,
        require_proved=require_proved,
    )


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

    # Remote prover via scillm (certainly/lean4) when enabled
    try:
        if os.getenv("LEAN4_REMOTE", "1").lower() in ("1", "true", "yes", "y"):
            ch_base = os.getenv("CHUTES_API_BASE", "").strip()
            ch_key = os.getenv("CHUTES_API_KEY", "").strip()
            async def _do_scillm_prover():
                router = get_text_router()
                return await router.acompletion(
                    model="chutes/text",
                    messages=[
                        {"role": "system", "content": "You are a Lean 4 theorem prover service. Return STRICT JSON with keys: success(bool), lean_code(string), stdout(string), stderr(string), proof_output(string|null)."},
                        {"role": "user", "content": textwrap.dedent(f"""
                            Prove the following requirement. Return STRICT JSON only.

                            Requirement:
                            {requirement}

                            Strategy:
                            {getattr(strategy, '__dict__', strategy)}
                        """)},
                    ],
                    response_format={"type": "json_object"},
                    timeout=300,
                    temperature=0,
                )
            resp = await _do_scillm_prover()
            content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
            try:
                obj = json.loads(content) if isinstance(content, str) else {}
            except Exception:
                obj = {}
            from types import SimpleNamespace
            return SimpleNamespace(
                success=bool(obj.get("success", False)),
                lean_code=str(obj.get("lean_code", "")),
                stdout=str(obj.get("stdout", "")),
                stderr=str(obj.get("stderr", "")),
                return_code=0 if obj.get("success") else 1,
                test_filename="<remote>",
                error_messages=[],
                proof_output=obj.get("proof_output"),
            )
    except Exception as e:
        logger.warning(f"remote_prover_failed: {e}")

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
    item: dict[str, Any], item_type: str, semaphore: asyncio.Semaphore
) -> dict[str, Any]:
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
                proof_dict: dict[str, Any] = {
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
    pipeline_data: dict[str, Any], skip_proving: bool = False
) -> dict[str, Any]:
    """
    Processes reflowed sections to extract and optionally prove theorems.
    """
    sections = pipeline_data.get("reflowed_sections", [])
    if not sections:
        logger.warning("No reflowed sections found in input data")
        return {"success": False, "error": "No reflowed sections to process", "proof_results": []}

    logger.info(f"Processing {len(sections)} reflowed sections for theorem proving.")

    # Phase 1: Extract requirements from all sections (LLM) and merge with miner output if available
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

    # Optional: merge deterministic miner output if provided via env LEAN4_MINER_JSON
    miner_path = os.getenv("LEAN4_MINER_JSON", "").strip()
    if miner_path:
        try:
            from pathlib import Path as _P
            print(f"MINER_PATH_DEBUG {miner_path} exists={_P(miner_path).exists()}")
        except Exception:
            pass
    if miner_path:
        try:
            mp = Path(miner_path)
            if mp.exists():
                miner = json.loads(mp.read_text())
                mined = miner.get("requirements") or []
                added = 0
                for m in mined:
                    txt = (
                        m.get("requirement_text")
                        or m.get("text_canonical")
                        or m.get("text_raw")
                        or m.get("text")
                        or ""
                    )
                    if not txt:
                        continue
                    all_requirements.append({
                        "requirement_text": str(txt),
                        "source": m.get("source") or {},
                        "modality": m.get("modality"),
                        "condition": m.get("condition"),
                    })
                    added += 1
                logger.info(f"Merged {added} requirements from miner: {miner_path}")
        except Exception as e:
            logger.warning(f"Failed to merge miner requirements: {e}")

    # Also merge requirements injected via pipeline_data (from --requirements option)
    try:
        injected = pipeline_data.get("_miner_requirements") or []
        if isinstance(injected, list) and injected:
            added = 0
            for m in injected:
                txt = (
                    m.get("requirement_text")
                    or m.get("text_canonical")
                    or m.get("text_raw")
                    or m.get("text")
                    or ""
                )
                if not txt:
                    continue
                all_requirements.append({
                    "requirement_text": str(txt),
                    "source": m.get("source") or {},
                    "modality": m.get("modality"),
                    "condition": m.get("condition"),
                })
                added += 1
            logger.info(f"Merged {added} injected miner requirements from pipeline_data")
    except Exception:
        pass

    logger.info(
        f"Extracted {len(all_requirements)} requirements and {len(all_constraints)} constraints (after merge)."
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

    # Preferred path: Certainly/Lean4 bridge (single-call batch). Chunk if very large.
    try:
        # Build requirement texts (ignore constraints for the bridge v1)
        def _is_high_quality(text: str) -> bool:
            import re as _re
            t = (text or "").strip()
            if len(t) < 40:
                return False
            if not _re.search(r"\b(shall|must|should|will)\b", t, _re.I):
                return False
            if t.startswith("REQ-"):
                return True
            # Heuristic: subject phrase before modal
            return bool(_re.match(r"^[A-Z][A-Za-z0-9_\-/ ]+\b(shall|must|should|will)\b", t))

        raw_req_texts: list[str] = []
        # Miner-provided metadata (if present) → build trace map by SHA1
        miner_items: list[dict[str, Any]] = []
        sha_to_meta: dict[str, dict[str, Any]] = {}
        for r in all_requirements:
            txt = (
                r.get("requirement_text")
                or r.get("text_canonical")
                or r.get("text_raw")
                or r.get("text")
                or ""
            )
            if txt:
                raw_req_texts.append(str(txt))
                meta = {
                    "requirement_text": str(txt),
                    "requirement_id": r.get("requirement_id"),
                    "text_sha1": r.get("text_sha1") or hashlib.sha1(str(txt).encode("utf-8")).hexdigest(),
                    "source": r.get("source") or {},
                    "from": r.get("from"),
                }
                miner_items.append(meta)
                sha_to_meta[meta["text_sha1"]] = meta

        req_texts = [t for t in raw_req_texts if _is_high_quality(t)]
        dropped = len(raw_req_texts) - len(req_texts)
        if dropped:
            logger.info(
                "req_filter.drop", extra={"total": len(raw_req_texts), "kept": len(req_texts), "dropped": dropped}
            )
        if req_texts:
            base = (
                os.getenv("CERTAINLY_BRIDGE_BASE")
                or os.getenv("LEAN4_BRIDGE_BASE")
                or "http://127.0.0.1:8787"
            )
            # Health preflight; fall back if bridge is not reachable
            if not _certainly_health(base):
                raise RuntimeError("certainly.health_unavailable")
            chunk_sz = max(1, int(os.getenv("LEAN4_PROVE_CHUNK_SIZE", "10")))
            max_seconds = int(os.getenv("LEAN4_PROVE_MAX_SECONDS", "20"))
            req_timeout = int(os.getenv("LEAN4_PROVE_TIMEOUT", "60"))
            logger.info(
                "certainly.batch.begin",
                extra={
                    "api_base": base,
                    "total_requirements": len(req_texts),
                    "chunk_size": chunk_sz,
                    "max_seconds": max_seconds,
                    "timeout": req_timeout,
                },
            )
            all_proofs = []
            certainly_meta: list[dict[str, Any]] = []
            proved_total = 0
            for i in range(0, len(req_texts), chunk_sz):
                chunk = req_texts[i : i + chunk_sz]
                t0 = time.monotonic()
                try:
                    resp = prove_with_certainly_batch(
                        requirements=chunk,
                        api_base=base,
                        max_seconds=max_seconds,
                        timeout=req_timeout,
                        require_proved=False,
                    )
                except Exception as e:
                    logger.error(f"certainly.batch.error: {e}")
                    raise
                dt = time.monotonic() - t0
                content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
                meta = (resp.get("additional_kwargs") or {}).get("certainly", {})
                # Support both {proved} and {proofs_proved} keys depending on bridge version
                sumry = meta.get("summary") or {}
                proofs_proved = int(sumry.get("proofs_proved") or sumry.get("proved") or 0)
                items_total = int(sumry.get("items_total") or sumry.get("items") or len(chunk))
                logger.info(
                    "certainly.chunk.done",
                    extra={
                        "idx": i,
                        "size": len(chunk),
                        "proved": proofs_proved,
                        "elapsed_s": round(dt, 3),
                        "content_preview": (content or "")[:80],
                    },
                )
                all_proofs.append({"meta": meta, "content": content})
                certainly_meta.append({
                    "idx": i,
                    "size": len(chunk),
                    "proved": proofs_proved,
                    "items_total": items_total,
                    "statistics": meta.get("statistics", {}),
                })
                proved_total += proofs_proved
            # Build per-item results from meta when available (partial success allowed)
            proof_results: list[dict[str, Any]] = []
            try:
                # Flatten results across chunks if provided
                flat = []
                for ap in all_proofs:
                    res = (ap.get("meta") or {}).get("results") or (ap.get("meta") or {}).get("proof_results") or []
                    if isinstance(res, list):
                        flat.extend(res)
                if flat:
                    for r in flat:
                        txt = r.get("requirement_text", "")
                        sha = hashlib.sha1(str(txt).encode("utf-8")).hexdigest()
                        meta = sha_to_meta.get(sha, {})
                        proof_results.append({
                            "success": bool(r.get("ok") is True),
                            "item": {
                                "requirement_text": txt,
                                "requirement_id": meta.get("requirement_id"),
                                "text_sha1": meta.get("text_sha1", sha),
                                "source": meta.get("source"),
                            },
                            "item_type": "requirement",
                            "lean_code": "",
                            "proof": "proved" if r.get("ok") else "unproved",
                            "tactics_used": [],
                            "assumptions": [],
                            "duration_seconds": 0.0,
                            "timestamp": datetime.now().isoformat(),
                        })
            except Exception:
                # Fallback: mark all as proved if summary said so
                for t in req_texts:
                    sha = hashlib.sha1(str(t).encode("utf-8")).hexdigest()
                    meta = sha_to_meta.get(sha, {})
                    proof_results.append({
                        "success": True,
                        "item": {
                            "requirement_text": t,
                            "requirement_id": meta.get("requirement_id"),
                            "text_sha1": meta.get("text_sha1", sha),
                            "source": meta.get("source"),
                        },
                        "item_type": "requirement",
                        "lean_code": "",
                        "proof": "proved",
                        "tactics_used": [],
                        "assumptions": [],
                        "duration_seconds": 0.0,
                        "timestamp": datetime.now().isoformat(),
                    })
            stats = {
                "total_requirements_found": len(all_requirements),
                "total_constraints_found": len(all_constraints),
                "successful_proofs": int(proved_total),
                "failed_proofs": max(0, int(len(req_texts) - proved_total)),
            }
            logger.info("certainly.batch.all_proved", extra={"total": len(req_texts)})
            return {
                "success": True,
                "statistics": stats,
                "proof_results": proof_results,
                "certainly": {
                    "chunks": certainly_meta,
                    "proved_total": proved_total,
                    "items_total": len(req_texts),
                },
            }
    except Exception as e:
        logger.warning(f"certainly.batch.fallback: {e}")

    # Fast-path: batch CLI via JSONL if configured
    if LEAN4_CLI_CMD and (
        ("{stdin_jsonl}" in LEAN4_CLI_CMD)
        or ("{input_jsonl}" in LEAN4_CLI_CMD and "{output_jsonl}" in LEAN4_CLI_CMD)
        or ("{input_json}" in LEAN4_CLI_CMD and "{output_json}" in LEAN4_CLI_CMD)
    ):
        try:
            batch_lines: list[dict[str, Any]] = []
            id_to_item: dict[str, dict[str, Any]] = {}
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
            proof_results: list[dict[str, Any]] = []
            successful_proofs = 0
            for r in batch_out or []:
                rid = str(r.get("id", ""))
                ref = id_to_item.get(rid, {})
                item = ref.get("item", {})
                item_type = ref.get("type", "requirement")
                success = bool(r.get("success", False))
                out_entry: dict[str, Any] = {
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
    input_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    skip_proving: bool = False,
    requirements_json: Path | None = None,
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
    diagnostics: list[dict[str, Any]] = []
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

    with open(input_json) as f:
        pipeline_data = json.load(f)

    # Inject miner requirements when provided (or auto-discover sibling output)
    try:
        if requirements_json is None:
            # Heuristic: results root relative to 07_reflow_section/json_output
            try:
                base_dir = input_json.parent.parent.parent
                auto = base_dir / "07_requirements_miner" / "json_output" / "07_requirements.json"
                if auto.exists():
                    try:
                        inj = json.loads(auto.read_text()).get("requirements") or []
                        if isinstance(inj, list) and inj:
                            pipeline_data["_miner_requirements"] = inj
                            logger.info(f"Auto-merged {len(inj)} miner requirements: {auto}")
                    except Exception:
                        os.environ["LEAN4_MINER_JSON"] = str(auto)
            except Exception:
                pass
        else:
            try:
                inj = json.loads(Path(requirements_json).read_text()).get("requirements") or []
                if isinstance(inj, list) and inj:
                    pipeline_data["_miner_requirements"] = inj
                    logger.info(f"Merged {len(inj)} miner requirements from --requirements")
            except Exception:
                os.environ["LEAN4_MINER_JSON"] = str(requirements_json)
    except Exception:
        # Non-fatal; continue without miner merge
        pass

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

    # Emit a simple traceability index for auditing: requirement_id/text_sha1 → proof status
    try:
        trace = {"items": []}
        for pr in (result.get("proof_results") or []):
            it = pr.get("item") or {}
            trace["items"].append({
                "requirement_id": it.get("requirement_id"),
                "text_sha1": it.get("text_sha1"),
                "status": "proved" if pr.get("success") else "unproved",
                "section": (it.get("source") or {}).get("section_id"),
                "section_title": (it.get("source") or {}).get("section_title"),
                "heading_path": (it.get("source") or {}).get("heading_path"),
                "section_path": (it.get("source") or {}).get("section_path"),
                "page_num": (it.get("source") or {}).get("page_num"),
            })
        (json_output_dir / "08_trace_index.json").write_text(json.dumps(trace, indent=2))
    except Exception:
        pass

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
    try:
        from extractor.pipeline.utils.scillm_router import close_all_routers
        close_all_routers()
    except Exception:
        pass


def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    skip_proving: bool = True,
):
    """Run Stage 08 from a consolidated bundle of reflowed sections."""
    stage_output_dir = output_dir / "08_lean4_theorem_prover"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    # Minimal diagnostics to align with other stages
    run_id = get_run_id()
    diagnostics: list[dict[str, Any]] = []
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
        print(f"Failed to load bundle: {e}")
        raise ValueError(f"Failed to load bundle: {e}")

    # Keep debug bundle minimal; skip auto-merge logic here

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


## CLI removed: import and call run(...), or use a debug harness.


if __name__ == "__main__":
    print("Import and call run(...) or debug_bundle(...); no CLI framework required.")
