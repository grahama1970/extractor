#!/usr/bin/env python3
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional

import typer

from extractor.pipeline.utils.deprecated_codex_call import run_codex_exec
import aiohttp
import asyncio

app = typer.Typer(
    help="Request research via Codex exec using MCP Perplexity + Context7 (JSON output)"
)


async def _post_log(api_base: Optional[str], payload: dict) -> None:
    if not api_base:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_base.rstrip("/") + "/ingest/log", json=payload, timeout=10
            ) as _:
                pass
    except Exception:
        pass


@app.command()
def run(
    topic: str = typer.Option(..., help="Research topic/problem statement"),
    context_file: Optional[Path] = typer.Option(
        None, help="Optional context file to include in the prompt"
    ),
    api_base: Optional[str] = typer.Option(None, help="Optional ingest API base for logging"),
    run_id: str = typer.Option("run-research", help="Run id for logging"),
    variant: str = typer.Option("research", help="Variant tag for logging"),
    codex_bin: str = typer.Option("codex", help="Codex CLI binary"),
    yolo: bool = typer.Option(True, help="--dangerously-bypass-approvals-and-sandbox"),
    sandbox: Optional[str] = typer.Option(None, help="--sandbox value"),
    save_to: Optional[Path] = typer.Option(
        None,
        help="Optional path to save the full research JSON (e.g., data/research/research_YYYYMMDD.json)",
    ),
    docs_dir: Optional[Path] = typer.Option(
        None, help="Optional directory to write docs summaries (Context7) as individual JSON files"
    ),
):
    ctx_text = ""
    if context_file and context_file.exists():
        try:
            ctx_text = context_file.read_text(encoding="utf-8")
        except Exception:
            ctx_text = ""

    system = (
        "You are a precise research agent. Use MCP Perplexity Ask for evidence-backed heuristics and "
        "MCP Context7 to fetch authoritative docs. Return strict JSON only."
    )
    user = {
        "task": topic,
        "context": ctx_text[:8000],
        "schema": {
            "schema": "research_v1",
            "heuristics": [],
            "docs": [],
            "takeaways": [],
            "sources": [],
        },
        "instructions": [
            "Use Perplexity MCP for external evidence; include citations.",
            "Use Context7 MCP for exact API docs/limits.",
            "Output one JSON object only following schema.",
        ],
    }

    prompt = (
        f"System:\n{system}\n\n"
        f"User:\n{json.dumps(user, ensure_ascii=False)}\n\n"
        "Return JSON only."
    )

    async def _go():
        await _post_log(
            api_base,
            {
                "ts": time.time(),
                "run_id": run_id,
                "variant": variant,
                "stream": "app",
                "source": "codex_research",
                "message": f"Research start: {topic}",
                "meta": {},
            },
        )

        res = await run_codex_exec(
            script_or_path=prompt,
            codex_bin=codex_bin,
            bypass_approvals_and_sandbox=yolo,
            sandbox_mode=sandbox,
            stdout_capture_limit=512 * 1024,
            stderr_capture_limit=512 * 1024,
        )
        out = (res.stdout or "").strip()
        print(out)
        # Try to persist JSON if requested
        try:
            obj = json.loads(out)
        except Exception:
            obj = None
        if obj is not None and save_to:
            try:
                save_to.parent.mkdir(parents=True, exist_ok=True)
                save_to.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
                await _post_log(
                    api_base,
                    {
                        "ts": time.time(),
                        "run_id": run_id,
                        "variant": variant,
                        "stream": "app",
                        "source": "codex_research",
                        "message": f"Saved research to {save_to}",
                        "meta": {},
                    },
                )
            except Exception:
                pass
        if obj is not None and docs_dir:
            try:
                docs = obj.get("docs") if isinstance(obj, dict) else None
                if isinstance(docs, list):
                    docs_dir.mkdir(parents=True, exist_ok=True)
                    for i, d in enumerate(docs):
                        name = None
                        if isinstance(d, dict):
                            name = d.get("id") or d.get("library") or d.get("name")
                        if not name:
                            name = f"doc_{i+1}"
                        safe = "".join(
                            c if c.isalnum() or c in ("-", "_", ".") else "_" for c in str(name)
                        )
                        (docs_dir / f"{safe}.json").write_text(
                            json.dumps(d, ensure_ascii=False, indent=2)
                        )
                    await _post_log(
                        api_base,
                        {
                            "ts": time.time(),
                            "run_id": run_id,
                            "variant": variant,
                            "stream": "app",
                            "source": "codex_research",
                            "message": f"Saved {len(docs)} docs to {docs_dir}",
                            "meta": {},
                        },
                    )
            except Exception:
                pass
        await _post_log(
            api_base,
            {
                "ts": time.time(),
                "run_id": run_id,
                "variant": variant,
                "stream": "stdout",
                "source": "codex_research",
                "message": out[-800] if out else "",
                "meta": {"rc": res.returncode},
            },
        )

    asyncio.run(_go())


if __name__ == "__main__":
    app()
