This step manages complex interactions between **LLM extraction**, **External CLI calls**, **Docker containers**, and **Remote APIs**.

I recommend refactoring this into `extractor/pipeline/utils/prover/`.

### Recommended Directory Structure

```text
extractor/pipeline/
├── steps/
│   └── 08_lean4_theorem_prover.py   <-- Orchestration & Configuration
└── utils/
    └── prover/
        ├── __init__.py
        ├── extraction.py            <-- LLM Requirement extraction (Prompts)
        ├── core.py                  <-- High-level proof logic & Data structures
        ├── execution.py             <-- Low-level CLI & Docker runners
        └── remote.py                <-- Certainly/Lean4 Bridge API
```

---

### 1\. `extraction.py` (LLM/Prompts)

Isolates the logic that reads the text sections and asks the LLM to find requirements.

- **Move:** `identify_requirements_in_section` (This contains the massive prompt definition).

### 2\. `execution.py` (CLI & Docker)

This module handles the "dirty work" of spawning subprocesses, writing temp files, and parsing `stdout`/`stderr`.

- **Move:** `_prove_via_cli`
- **Move:** `_prove_batch_via_cli`
- **Move:** `execute_lean_code` (The Docker fallback).

### 3\. `remote.py` (API Bridge)

Isolates the calls to the external "Certainly" API.

- **Move:** `prove_with_certainly_batch`
- **Move:** `_certainly_health`

### 4\. `core.py` (Business Logic)

This acts as the dispatcher. It decides whether to use the CLI, the Remote API, or Docker, and standardizes the result.

- **Move:** `prove_requirement` (The switch statement logic).
- **Move:** `prove_with_feedback` (The high-level loop).
- **Move:** `ProofResult` (The dataclass definition).

---

### The New `08_lean4_theorem_prover.py`

The orchestrator becomes a clean async loop:

```python
# ... imports ...
import extractor.pipeline.utils.prover.extraction as extract
import extractor.pipeline.utils.prover.core as prover_core

async def process_reflowed_sections(pipeline_data, ...):
    # 1. Extract (Phase A)
    extraction_tasks = [
        extract.identify_requirements_in_section(s, llm_semaphore)
        for s in sections
    ]
    # ... gather results ...

    # 2. Prove (Phase B)
    proof_tasks = []
    for item in all_items:
        # Core handles dispatching to Remote/CLI/Docker based on env vars
        task = prover_core.prove_with_feedback(
            item["item"],
            item["type"],
            lean4_semaphore
        )
        proof_tasks.append(task)

    # ... gather results ...
```

### Next Step

The **`execution.py`** file contains the most complex I/O logic (handling JSONL batches over stdin/files). Would you like me to generate that file first?

Here is the code for **`extractor/pipeline/utils/prover/execution.py`**.

This module isolates the low-level execution logic, handling the complexity of interacting with external processes (CLI stdin/stdout, File I/O, and Docker containers).

### `extractor/pipeline/utils/prover/execution.py`

```python
import asyncio
import json
import os
import shlex
import tempfile
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

from loguru import logger
from extractor.pipeline.utils.prover.core import ProofResult

def _get_cli_cmd() -> str:
    return os.getenv("LEAN4_CLI_CMD", "").strip()

async def prove_via_cli(requirement: str, strategy: Any) -> Dict[str, Any]:
    """
    Invoke external Lean4 CLI when LEAN4_CLI_CMD is set.

    Supports two contract styles:
      - Stdin JSON: command contains "{stdin}" placeholder -> write to stdin, read JSON from stdout
      - File I/O:   command has both "{input}" and "{output}" -> write temp input.json, read temp output.json

    Returns a dict (raw result) to be normalized by the Core module.
    """
    cmd_template = _get_cli_cmd()
    if not cmd_template:
        return {"error": "LEAN4_CLI_CMD not configured"}

    # Prepare payload
    # Strategy might be a namespace object or dict
    strat_dict = getattr(strategy, "__dict__", strategy)
    payload = {
        "requirement": requirement,
        "strategy": strat_dict,
    }

    # Mode 1: Stdin JSON
    if "{stdin}" in cmd_template:
        cmd_str = cmd_template.replace("{stdin}", "").strip()
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

            out_str = stdout.decode("utf-8", errors="ignore")
            err_str = stderr.decode("utf-8", errors="ignore")

            try:
                result = json.loads(out_str) if out_str.strip() else {}
            except Exception:
                result = {"success": False, "stderr": "Non-JSON output from CLI", "stdout": out_str}

            # Return raw dict; Core will wrap in ProofResult/SimpleNamespace
            return {
                "success": bool(result.get("success", False)),
                "lean_code": result.get("lean_code", ""),
                "stdout": result.get("stdout", out_str),
                "stderr": result.get("stderr", err_str),
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

    # Mode 2: File I/O
    if "{input}" in cmd_template and "{output}" in cmd_template:
        with tempfile.TemporaryDirectory() as td:
            in_path = Path(td) / "requirement.json"
            out_path = Path(td) / "proof.json"

            in_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

            cmd_str = cmd_template.replace("{input}", str(in_path)).replace("{output}", str(out_path))
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
                        "stdout": stdout.decode("utf-8", errors="ignore")
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


async def prove_batch_via_cli(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Invoke external Lean4 CLI once with JSONL input for batch processing.

    Contracts supported:
      - {stdin_jsonl}
      - {input_jsonl} / {output_jsonl}
      - {input_json} / {output_json} (Array mode)
    """
    cmd_template = _get_cli_cmd()
    if not cmd_template:
        return []

    results: List[Dict[str, Any]] = []

    try:
        # Mode 1: Stdin JSONL
        if "{stdin_jsonl}" in cmd_template:
            cmd_str = cmd_template.replace("{stdin_jsonl}", "").strip()
            argv = shlex.split(cmd_str)
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            data = "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n"
            stdout, stderr = await proc.communicate(data.encode("utf-8"))
            out_str = stdout.decode("utf-8", errors="ignore")

            for line in out_str.splitlines():
                line = line.strip()
                if not line: continue
                try:
                    obj = json.loads(line)
                except Exception:
                    obj = {"success": False, "stderr": "Non-JSON line from CLI", "raw": line}
                results.append(obj)
            return results

        # Mode 2: File JSONL
        if "{input_jsonl}" in cmd_template and "{output_jsonl}" in cmd_template:
            with tempfile.TemporaryDirectory() as td:
                in_path = Path(td) / "batch_in.jsonl"
                out_path = Path(td) / "batch_out.jsonl"

                with open(in_path, "w", encoding="utf-8") as f:
                    for it in items:
                        f.write(json.dumps(it, ensure_ascii=False) + "\n")

                cmd_str = cmd_template.replace("{input_jsonl}", str(in_path)).replace("{output_jsonl}", str(out_path))
                argv = shlex.split(cmd_str)
                proc = await asyncio.create_subprocess_exec(
                    *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

                if out_path.exists():
                    content = out_path.read_text(encoding="utf-8", errors="ignore")
                    for line in content.splitlines():
                        line = line.strip()
                        if not line: continue
                        try:
                            results.append(json.loads(line))
                        except Exception:
                            results.append({"success": False, "stderr": "Non-JSON line from CLI", "raw": line})
                return results

        # Mode 3: File JSON Array
        if "{input_json}" in cmd_template and "{output_json}" in cmd_template:
            # Transform items for array mode
            batch_array = []
            for it in items:
                entry = {}
                entry["requirement"] = it.get("requirement") or it.get("constraint_text") or it.get("text") or ""

                strat = it.get("strategy")
                if isinstance(strat, dict):
                    name = strat.get("name") or strat.get("strategy")
                    if isinstance(name, str) and name:
                        entry["strategies"] = [name]
                elif isinstance(strat, str) and strat:
                    entry["strategies"] = [strat]

                entry["metadata"] = {k: it.get(k) for k in ("id", "item_type", "source", "section_id") if k in it}
                batch_array.append(entry)

            with tempfile.TemporaryDirectory() as td:
                in_json = Path(td) / "batch_in.json"
                out_json = Path(td) / "batch_out.json"
                in_json.write_text(json.dumps(batch_array, ensure_ascii=False), encoding="utf-8")

                cmd_str = cmd_template.replace("{input_json}", str(in_json)).replace("{output_json}", str(out_json))
                argv = shlex.split(cmd_str)
                proc = await asyncio.create_subprocess_exec(
                    *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

                if out_json.exists():
                    try:
                        arr = json.loads(out_json.read_text(encoding="utf-8", errors="ignore"))
                        if isinstance(arr, list):
                            results.extend(arr)
                        else:
                            results.append({"success": False, "stderr": "Output JSON not a list"})
                    except Exception as e:
                        results.append({"success": False, "stderr": f"Invalid JSON output: {e}"})
                return results

    except Exception as e:
        return [{"success": False, "stderr": f"Batch CLI failed: {e}"}]

    return results


async def execute_lean_code_docker(lean_code: str) -> ProofResult:
    """
    Execute Lean code using a local Docker container (lean_runner).
    This serves as the fallback mechanism if CLI/Remote are not configured.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "lean_runner",
            "sh", "-c", "cd /workspace/mathlib_project && lake env lean --stdin",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate(lean_code.encode())

        stdout_str = stdout.decode("utf-8", errors="ignore")
        stderr_str = stderr.decode("utf-8", errors="ignore")

        # Lean outputs errors to stdout
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
        logger.error(f"Lean Docker execution failed: {e}")
        return ProofResult(
            success=False,
            lean_code=lean_code,
            stdout="",
            stderr=str(e),
            return_code=1,
            test_filename="<stdin>",
            error_messages=[str(e)],
        )
```
