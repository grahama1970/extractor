#!/usr/bin/env python3
"""CLI and Docker execution utilities for Stage 08 (Lean4 Theorem Prover).

Handles low-level subprocess execution for proving.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class ProofResult:
    """Result of a Lean 4 proof attempt."""

    success: bool
    lean_code: str
    stdout: str
    stderr: str
    return_code: int
    test_filename: str = "<stdin>"
    error_messages: Optional[List[str]] = None
    proof_output: Optional[str] = None


def get_cli_cmd() -> str:
    """Get the configured Lean4 CLI command."""
    return os.getenv("LEAN4_CLI_CMD", "").strip()


async def prove_via_cli(requirement: str, strategy: Any) -> Dict[str, Any]:
    """Invoke external Lean4 CLI when LEAN4_CLI_CMD is set.

    Supports two contract styles:
    - Stdin JSON: command contains "{stdin}" placeholder
    - File I/O: command has both "{input}" and "{output}"
    """
    cmd_template = get_cli_cmd()
    if not cmd_template:
        return {"error": "LEAN4_CLI_CMD not configured"}

    strat_dict = getattr(strategy, "__dict__", strategy) if strategy else {}
    payload = {"requirement": requirement, "strategy": strat_dict}

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
                result = {"success": False, "stderr": "Non-JSON output", "stdout": out_str}

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

            cmd_str = cmd_template.replace("{input}", str(in_path)).replace(
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
                    result = {"success": False, "stderr": "Output file missing or invalid"}

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
        "stderr": "LEAN4_CLI_CMD missing required placeholders",
        "return_code": 1,
        "lean_code": "",
        "stdout": "",
    }


async def prove_batch_via_cli(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Invoke external Lean4 CLI with JSONL batch input."""
    cmd_template = get_cli_cmd()
    if not cmd_template:
        return []

    results: List[Dict[str, Any]] = []

    try:
        # Mode: Stdin JSONL
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
            stdout, _ = await proc.communicate(data.encode("utf-8"))
            out_str = stdout.decode("utf-8", errors="ignore")

            for line in out_str.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except Exception:
                    results.append({"success": False, "raw": line})
            return results

        # Mode: File JSONL
        if "{input_jsonl}" in cmd_template and "{output_jsonl}" in cmd_template:
            with tempfile.TemporaryDirectory() as td:
                in_path = Path(td) / "batch_in.jsonl"
                out_path = Path(td) / "batch_out.jsonl"

                with open(in_path, "w", encoding="utf-8") as f:
                    for it in items:
                        f.write(json.dumps(it, ensure_ascii=False) + "\n")

                cmd_str = cmd_template.replace("{input_jsonl}", str(in_path)).replace(
                    "{output_jsonl}", str(out_path)
                )
                argv = shlex.split(cmd_str)
                proc = await asyncio.create_subprocess_exec(
                    *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

                if out_path.exists():
                    for line in out_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            results.append(json.loads(line))
                        except Exception:
                            results.append({"success": False, "raw": line})
                return results

    except Exception as e:
        return [{"success": False, "stderr": f"Batch CLI failed: {e}"}]

    return results


async def execute_lean_code_docker(lean_code: str) -> ProofResult:
    """Execute Lean code using Docker container fallback."""
    try:
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
        stdout, stderr = await proc.communicate(lean_code.encode())
        stdout_str = stdout.decode("utf-8", errors="ignore")
        stderr_str = stderr.decode("utf-8", errors="ignore")

        error_messages = [stdout_str] if proc.returncode != 0 and stdout_str else None

        return ProofResult(
            success=proc.returncode == 0,
            lean_code=lean_code,
            stdout=stdout_str,
            stderr=stderr_str,
            return_code=int(proc.returncode or 1),
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
            error_messages=[str(e)],
        )


__all__ = [
    "ProofResult",
    "get_cli_cmd",
    "prove_via_cli",
    "prove_batch_via_cli",
    "execute_lean_code_docker",
]
