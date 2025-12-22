#!/usr/bin/env python3
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Optional

import typer
from loguru import logger
from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec
import aiohttp
import asyncio

app = typer.Typer(help="Run expert-level code review via Codex exec with strict, structured markdown output")


def _read_files(paths: List[Path], max_chars: int = 80000) -> str:
    parts: List[str] = []
    used = 0
    for p in paths:
        try:
            t = p.read_text(encoding='utf-8')
        except Exception:
            continue
        header = f"\n\n---\nFILE: {p}\n---\n"
        chunk = header + t
        if used + len(chunk) > max_chars:
            parts.append(header + t[: max(0, max_chars - used - len(header))])
            break
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts)


async def _post_log(api_base: Optional[str], payload: dict) -> None:
    if not api_base:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_base.rstrip('/') + '/ingest/log', json=payload, timeout=10) as _:
                pass
    except Exception:
        pass


@app.command()
def run(
    files: List[Path] = typer.Argument(..., exists=True, readable=True),
    api_base: Optional[str] = typer.Option(None, help="Optional ingest API base"),
    run_id: str = typer.Option("run-review", help="Run id for logging"),
    variant: str = typer.Option("codereview", help="Variant tag"),
    codex_bin: str = typer.Option("codex", help="Codex CLI binary"),
    yolo: bool = typer.Option(True, help="--dangerously-bypass-approvals-and-sandbox"),
    sandbox: Optional[str] = typer.Option(None, help="--sandbox value"),
):
    persona = (
        "You are an expert-level llm agent architect and senior developer, specializing in production-readiness, "
        "system reliability, and maintainability. Perform a comprehensive code review."
    )
    structure = (
        "Output strict markdown per file using this template exactly. For each file provided, generate:\n"
        "---\n### File: `[Full Path to File]`\n\n"
        "**Overall Assessment:** ...\n\n"
        "| 🔴 **CRITICAL / WILL BREAK IN PRODUCTION** |\n| :--- |\n| **1. ...** |\n\n"
        "| 🟡 **MEDIUM / WILL BITE LATER** |\n| :--- |\n| **1. ...** |\n\n"
        "| 🔵 **REFINEMENT / CODE HYGIENE** |\n| :--- |\n| **1. ...** |\n\n"
        "| ✅ **STRENGTHS / GOOD PRACTICES** |\n| :--- |\n| **1. ...** |\n\n---\n"
        "Be exhaustive. Provide concrete fixes with diffs when possible."
    )

    content = _read_files(files)
    prompt = f"System:\n{persona}\n\nUser:\nReview the following files.\n{content}\n\n{structure}\nReturn only the markdown."

    async def _go():
        await _post_log(api_base, {"ts": time.time(), "run_id": run_id, "variant": variant, "stream": "app", "source": "codex_code_review", "message": f"Starting code review for {len(files)} files", "meta": {}})
        res = await run_codex_exec(
            script_or_path=prompt,
            codex_bin=codex_bin,
            bypass_approvals_and_sandbox=yolo,
            sandbox_mode=sandbox,
            stdout_capture_limit=1024*1024,
            stderr_capture_limit=256*1024,
        )
        out = (res.stdout or "").strip()
        print(out)
        await _post_log(api_base, {"ts": time.time(), "run_id": run_id, "variant": variant, "stream": "stdout", "source": "codex_code_review", "message": out[-800] if out else "", "meta": {"rc": res.returncode}})

    asyncio.run(_go())


if __name__ == "__main__":
    app()
