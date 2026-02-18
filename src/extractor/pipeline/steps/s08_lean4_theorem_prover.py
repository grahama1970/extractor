#!/usr/bin/env python3
"""
Pipeline Stage 8: Lean 4 Theorem Proving for Requirements
=========================================================

What this stage does (read before editing)
- Input: Stage 07 reflowed sections (07_reflowed.json).
- Step A: For each section, call SciLLM (Router, chutes/text, JSON mode) to extract
  requirement candidates + table constraints (single LLM call per section).
- Step B: Prove each requirement via:
    * SciLLM extras `certainly_prove` (preferred paved path) — flow:
        1) send requirement + strategy to Certainly/Lean4 bridge (LLM writes Lean code),
        2) bridge returns multiple candidate theorems,
        3) container compiles each in Lean4,
        4) pick a compiling candidate (or return failure with compiler feedback).
    * OR external CLI if `LEAN4_CLI_CMD` is set (stdin/file JSON/JSONL contracts).
- Output: 08_theorems.json (proof results, diagnostics).

Paved-path + safety
- No manual headers or raw HTTP; SciLLM Router handles auth/headers.
- Preflight enforced via `require_scillm_preflight`.
- Heavy calls are throttled by MAX_CONCURRENT_LLM and MAX_CONCURRENT_LEAN4 envs.
- Long-running proofs: 30–300s each; treat as LLM-like service.

When this stage runs
- Only when proving is enabled (not in deterministic/offline runs).
- If Lean4 CLI or SciLLM extras aren’t available, proofs will fail; ensure one of them
  is configured (LEAN4_CLI_CMD or certainly_prove via scillm extras).
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import find_dotenv, load_dotenv
from loguru import logger
from rich.console import Console

# Import dependencies
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.utils.content_query import ContentRepository
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
from extractor.pipeline.steps.s08_extract_requirements import run_extract_requirements as _run_miner

# Prover utilities


# --- Initialization ---
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)

console = Console()
STEP_NAME = "08_lean4_theorem_prover"

# Configuration
LEAN4_MODEL = os.getenv("LEAN4_MODEL", "openai/gpt-5-mini")
LEAN4_PROVER_MODEL = os.getenv("LEAN4_PROVER_MODEL", os.getenv("LEAN4_MODEL", "certainly/lean4"))
MAX_CONCURRENT_PROOFS = int(os.getenv("MAX_CONCURRENT_LEAN4_CALLS", 1))
LEAN4_CLI_CMD = os.getenv("LEAN4_CLI_CMD", "").strip()
# Max theorems to prove (0 = unlimited, useful for testing)
MAX_THEOREMS = int(os.getenv("LEAN4_MAX_THEOREMS", 0))


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


async def prove_requirements(db_path: Path, output_dir: Path):
    """
    Fetch requirements from DB and attempt to prove them using Lean 4.
    """
    logger.info(f"Starting formal verification for DB: {db_path}")

    # Load requirements from assembled_content.json
    repo = ContentRepository(db_path)
    reqs = repo.requirements

    logger.info(f"Found {len(reqs)} requirements to verify.")

    # Prepare Items for certainly_prove_iter
    # User contract: items=[{"requirement_text": "..."}]
    # We pass ID to track it back.
    items = [
        {"requirement_text": r.get("text", ""), "id": r.get("id", ""), "section_id": r.get("section_id", "")}
        for r in reqs
    ]

    # Apply MAX_THEOREMS limit if set
    if MAX_THEOREMS > 0 and len(items) > MAX_THEOREMS:
        logger.info(f"Limiting to first {MAX_THEOREMS} theorems (MAX_THEOREMS env)")
        items = items[:MAX_THEOREMS]

    logger.info(
        f"Proving {len(items)} requirements via certainly_prove_iter (Model: {LEAN4_PROVER_MODEL})..."
    )
    if not items:
        logger.warning("No requirements found in DB; skipping Lean4 proving loop.")
    # Diagnostics to catch zero-yield regressions
    try:
        logger.info(f"Sample item: {items[0] if items else None}")
        logger.info(
            "Bridge base: %s",
            os.getenv("CERTAINLY_BRIDGE_BASE") or os.getenv("LEAN4_BRIDGE_BASE") or "(unset)",
        )
    except Exception:
        pass

    # 2. Stream Results
    from scillm.extras.providers import certainly_prove_iter
    import scillm

    # Force use of local bridge for this step if env var missing
    if not os.getenv("SCILLM_API_BASE"):
        start_url = "http://localhost:8787/v1"  # Updated to match sanity check default
        scillm.api_base = start_url
        scillm.api_key = "sk-placeholder"
        # Also set environment variables for the current process
        os.environ["SCILLM_API_BASE"] = start_url
        os.environ["SCILLM_API_KEY"] = "sk-placeholder"
        logger.info(f"Configured SciLLM for Local Bridge: {start_url}")
    else:
        logger.info(f"Using existing SciLLM config: {os.getenv('SCILLM_API_BASE')}")

    results = []
    total_proved = 0

    # 1.1 Verify bridge connectivity before starting
    # Prevents hanging indefinitely if the bridge is down (common issue)
    api_base = scillm.api_base or os.getenv("SCILLM_API_BASE")
    if not api_base:
        api_base = "http://localhost:8787/v1"  # Fallback guess

    import aiohttp

    logger.info(f"Checking bridge connectivity at {api_base}...")
    try:
        async with aiohttp.ClientSession() as session:
            # Try a lightweight endpoint or just the base
            # Most OpenAI-like bridges have /v1/models or root
            # We set a strict 2s timeout to fail fast
            test_url = api_base.rstrip("/") + "/healthz"
            if "/v1" in test_url:
                test_url = test_url.replace("/v1/healthz", "/healthz")
            async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status >= 500:
                    logger.warning(f"Bridge returned {resp.status}; proving might fail.")
                else:
                    logger.info("Bridge is reachable.")
    except Exception as e:
        logger.error(f"Bridge unreachable at {api_base}: {e}")
        raise RuntimeError(f"Lean4 bridge unreachable at {api_base}. No skipping allowed.")

    if items:

        try:
            logger.info("Starting certainly_prove_iter loop...")
            async for res in certainly_prove_iter(
                items=items,
                response_format={"type": "json_object"},
                concurrency=MAX_CONCURRENT_PROOFS,
            ):
                logger.info(f"Received result: {res.keys()}")
                # Inspect result

                req_id = None
                status = "failed"
                proof_out = ""
                lean_code = ""

                # Try to identify which item this result corresponds to.
                # Spec says "yields results like parallel_acompletions_iter", so likely contains 'request' or 'item' metadata?
                # Or reliance on FIFO order (dangerous for async)?
                # Inspect res to find ID.

                if "item" in res and isinstance(res.get("item"), dict):
                    req_id = res["item"].get("id")
                elif "request" in res and isinstance(res.get("request"), dict):
                    req_id = res["request"].get("id")
                    if req_id is None:
                        try:
                            req_items = res["request"].get("items") or []
                            if req_items and isinstance(req_items[0], dict):
                                req_id = req_items[0].get("id")
                        except Exception:
                            req_id = None

                # If ID missing, log warning
                if not req_id:
                    logger.warning(f"Result without ID: {res.keys()}")
                    continue

                if res.get("ok") or res.get("success"):
                    status = "verified"
                    summary = res.get("content", "") or ""
                    resp_obj = res.get("response")
                    payload = {}
                    if isinstance(resp_obj, dict):
                        payload = resp_obj.get("additional_kwargs", {}) or {}
                    else:
                        payload = getattr(resp_obj, "additional_kwargs", {}) or {}
                    certainly = payload.get("certainly", {}) if isinstance(payload, dict) else {}
                    results_payload = (
                        certainly.get("results") if isinstance(certainly, dict) else None
                    )

                    if isinstance(results_payload, list) and results_payload:
                        data = results_payload[0]
                        lean_code = data.get("lean_code", "") or data.get("code", "")
                        proof_out = data.get("stdout", "") or data.get("proof", "") or summary
                        success_flag = data.get("success")
                        if success_flag is False:
                            status = "failed"
                            proof_out = (
                                data.get("error") or data.get("stdout") or "Verification failed."
                            )
                    else:
                        status = "error"
                        proof_out = f"Missing certainly results; summary={summary[:200]}"
                else:
                    status = "error"
                    err = res.get("error") or res.get("status") or "Unknown error"
                    reason = res.get("reason")
                    fix = res.get("fix")
                    detail = res.get("detail")
                    parts = [str(err)]
                    if reason:
                        parts.append(f"reason: {reason}")
                    if fix:
                        parts.append(f"fix: {fix}")
                    if detail and detail != err:
                        parts.append(f"detail: {detail}")
                    proof_out = " | ".join(parts)

                # Save logic
                results.append(
                    {
                        "id": req_id,
                        "requirement_id": req_id,
                        "status": status,
                        "lean_code": lean_code,
                        "proof_output": proof_out,
                        "fix": res.get("fix"),
                    }
                )

                total_proved += 1
                if total_proved % 5 == 0:
                    logger.info(f"Progress: {total_proved}/{len(reqs)}")

        except Exception as e:
            logger.error(f"Stream error: {e}")
            # Add remaining as error?

    # Save results to JSON (Legacy artifact)
    out_json = output_dir / "08_theorems.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"theorems": results}, indent=2))
    logger.info(f"Proof results saved to {out_json}")

    # Save proofs to assembled_content.json via ContentRepository
    logger.info(f"Saving {len(results)} results to assembled content...")

    json_path = db_path.parent / "07_assembled" / "assembled_content.json"
    if not json_path.exists():
        json_path = db_path  # ContentRepository handles redirect
    repo = ContentRepository(json_path)

    existing_ids = {p.get("id") for p in repo.lean4_proofs}
    new_proofs = []
    for res in results:
        if not res["id"]:
            logger.warning("Skipping result with no ID")
            continue
        if res["id"] in existing_ids:
            logger.warning(f"Skipping existing proof {res['id']}")
            continue
        new_proofs.append({
            "id": res["id"],
            "requirement_id": res["id"],
            "theorem_strategy": "scillm-certainly-iter",
            "lean4_code": res.get("lean_code"),
            "compilation_status": res.get("status"),
            "proof_result": res.get("proof_output"),
        })

    if new_proofs:
        repo.add_lean4_proofs(new_proofs)
        repo.save()

    logger.info(
        f"Proof results saved to assembled_content.json. Inserted: {len(new_proofs)}/{len(results)}"
    )


def run_extract_requirements(
    pipeline_dir: Path,
    db_path: Path,
    preset_config: Optional[Dict[str, Any]] = None,
):
    """
    Main entry point invoked by run_pipeline.py when proving is enabled.
    1. Runs the standard requirements miner (_s08).
    2. Runs the formal verifier (Prover).
    """
    logger.info(">>> Stage 08: Requirements Mining (delegated)")
    # 1. Mine requirements
    _run_miner(pipeline_dir, db_path)

    logger.info(">>> Stage 08: Formal Verification (Lean 4)")
    # 2. Prove them (async wrapper)
    try:
        require_scillm_preflight()
        asyncio.run(prove_requirements(db_path, pipeline_dir / "08_lean4_theorem_prover"))
    except Exception as e:
        logger.error(f"Formal verification failed: {e}")
        # We don't crash the pipeline if proving fails, unless strictly required?
        # But run_pipeline expects success. Let's re-raise to be safe/noisy.
        raise e


# Alias for smoke tests / generic runners
run = run_extract_requirements

if __name__ == "__main__":
    import sys

    # Simple sanity check entry point
    if len(sys.argv) > 1 and sys.argv[1] == "sanity":
        sys.exit(sanity())

    # Deprecation for all other usage
    print("❌ DIRECT EXECUTION DEPRECATED", file=sys.stderr)
    print("Please use the pipeline orchestrator:", file=sys.stderr)
    print("  python -m extractor.pipeline --pdf <PDF> --out <DIR>", file=sys.stderr)
    sys.exit(1)
