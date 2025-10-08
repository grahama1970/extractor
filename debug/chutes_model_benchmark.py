#!/usr/bin/env python3
"""Benchmark Chutes vision-capable models against Stage 03 suspicious-header verification.

For each candidate model discovered via the public Chutes catalog, we:
1. Run Stage 03 with a configurable limit of suspicious headers.
2. Capture the generated metrics JSON (if successful).
3. Print a consolidated summary and persist results for later analysis.

Usage (example):
    python debug/chutes_model_benchmark.py --limit 8 --keywords vl vision

Results are stored under data/results/pipeline/chutes_benchmark/<model_slug> and
summaries dumped to debug/chutes_benchmark_summary.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import requests
except ImportError as exc:  # pragma: no cover
    print("requests is required (pip install requests)", file=sys.stderr)
    raise

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore

CHUTES_CATALOG_URL = "https://api.chutes.ai/chutes/?include_public=true&page=0&limit=200&include_schemas=false"
DEFAULT_OUTPUT_ROOT = Path("data/results/pipeline/chutes_benchmark")
DEFAULT_INPUT_JSON = Path("data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json")
DEFAULT_PDF_DIR = Path("data/results/pipeline/tmp_pdf")
SUMMARY_PATH = Path("debug/chutes_benchmark_summary.json")


@dataclass
class ModelCandidate:
    alias: str
    remote: str
    description: str

    @property
    def slug(self) -> str:
        slug = self.alias.replace("chutes/", "")
        slug = slug.replace("/", "-")
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug)
        return slug.lower()


def load_env() -> None:
    """Best-effort load of .env file."""
    if load_dotenv is not None:
        load_dotenv(dotenv_path=".env", override=False)


def fetch_catalog(api_key: str, api_base: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(CHUTES_CATALOG_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("Unexpected catalog schema: 'items' missing")
    return items


def filter_candidates(items: Iterable[dict], keywords: Iterable[str]) -> List[ModelCandidate]:
    keywords = [kw.lower() for kw in keywords]
    candidates: List[ModelCandidate] = []
    for item in items:
        name = item.get("name")
        if not isinstance(name, str):
            continue
        lower_name = name.lower()
        if keywords and not any(kw in lower_name for kw in keywords):
            continue
        description = item.get("tagline") or ""
        alias_tail = name.split('/')[-1]
        alias = f"openai/chutes/{alias_tail}"
        candidates.append(ModelCandidate(alias=alias, remote=name, description=str(description)))
    return candidates


def run_stage03(candidate: ModelCandidate, args: argparse.Namespace) -> dict:
    out_dir = (args.output_root / candidate.slug).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    activate = "source .venv/bin/activate"
    source_env = "set -a && [ -f .env ] && source .env && set +a"
    env_exports = (
        f"STAGE03_MODEL='{candidate.alias}' "
        f"CHUTES_MODEL='{candidate.alias}' "
        f"CHUTES_REMOTE_MODEL='{candidate.remote}' "
        f"CHUTES_PROVIDER='{os.environ.get('CHUTES_PROVIDER', 'openai')}'"
    )
    cmd = (
        f"{activate} && {source_env} && "
        f"{env_exports} "
        f"python -m extractor.pipeline.steps.03_suspicious_headers run "
        f"{args.input_json} --pdf-dir {args.pdf_dir} --limit {args.limit} "
        f"--timeout {args.timeout} --dpi {args.dpi} -c {args.concurrency} "
        f"-o {out_dir}"
    )

    print(f"\n→ Benchmarking {candidate.alias} (remote={candidate.remote})")
    key_preview = os.environ.get('CHUTES_API_KEY', '')[:8]
    print(f"    using CHUTES_API_KEY prefix: {key_preview}***")
    result = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
    metrics_path = out_dir / "03_suspicious_headers" / "json_output" / "03_metrics.json"

    summary: dict = {
        "alias": candidate.alias,
        "remote": candidate.remote,
        "description": candidate.description,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "metrics_path": str(metrics_path) if metrics_path.exists() else None,
        "log_path": str(out_dir / "03_suspicious_headers" / "stage_03_suspicious_headers.log"),
    }

    if result.returncode == 0 and metrics_path.exists():
        try:
            with metrics_path.open() as fh:
                summary["metrics"] = json.load(fh)
        except Exception as exc:  # pragma: no cover
            summary["metrics_error"] = str(exc)
    else:
        summary["metrics"] = None

    if result.returncode != 0:
        print(f"  ✖ Stage 03 failed (code {result.returncode}); see {summary['log_path']}")
    else:
        metrics = summary.get("metrics", {}) or {}
        stats = metrics.get("stats", {}) if isinstance(metrics, dict) else {}
        success = stats.get("llm_success")
        requests_count = stats.get("llm_requests")
        duration_ms = stats.get("llm_batch_duration_ms")
        if success is not None:
            print(
                f"  ✓ Success {success}/{requests_count} | batch {duration_ms} ms | metrics: {metrics_path}"
            )
        else:
            print("  ✓ Stage completed but metrics missing")

    return summary


def summarize(results: List[dict]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_PATH.open("w") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nSummary written to {SUMMARY_PATH}")

    # Pretty console summary
    print("\n=== Benchmark Summary ===")
    for res in results:
        alias = res["alias"]
        rc = res["returncode"]
        metrics = res.get("metrics")
        if rc != 0 or not metrics:
            print(f"- {alias}: FAILED (rc={rc})")
            continue
        stats = metrics.get("stats", {})
        timing = metrics.get("timings", {})
        success = stats.get("llm_success")
        reqs = stats.get("llm_requests")
        duration = stats.get("llm_batch_duration_ms")
        stage_duration = timing.get("stage_duration_ms")
        print(
            f"- {alias}: success {success}/{reqs}, batch={duration} ms, stage={stage_duration} ms"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Chutes models for Stage 03")
    parser.add_argument("--limit", type=int, default=8, help="Suspicious headers to evaluate per model")
    parser.add_argument("--timeout", type=int, default=600, help="Stage timeout (seconds)")
    parser.add_argument("--dpi", type=int, default=150, help="Rendering DPI for context images")
    parser.add_argument("--concurrency", type=int, default=1, help="LLM concurrency")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=["vl", "vision"],
        help="Keywords to filter Chutes catalog (case-insensitive)",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=5,
        help="Maximum number of models to benchmark after filtering",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=DEFAULT_INPUT_JSON,
        help="Stage 02 JSON path",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing clean PDFs",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Base directory to store run artifacts",
    )
    parser.add_argument(
        "--model-names",
        nargs="*",
        default=None,
        help="Explicit model names to benchmark (skip catalog filter)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.input_json = args.input_json.expanduser().resolve()
    args.pdf_dir = args.pdf_dir.expanduser().resolve()
    args.output_root = args.output_root.expanduser().resolve()

    load_env()
    api_key = os.getenv("CHUTES_API_KEY")
    api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
    if not api_key:
        print("CHUTES_API_KEY not set", file=sys.stderr)
        return 2

    if args.model_names:
        items = [{"name": name, "tagline": "(explicit)"} for name in args.model_names]
    else:
        items = fetch_catalog(api_key, api_base)

    candidates = filter_candidates(items, args.keywords)
    if not candidates:
        print("No candidates matched the provided keywords.")
        return 1

    if args.max_models and len(candidates) > args.max_models:
        candidates = candidates[: args.max_models]

    args.output_root.mkdir(parents=True, exist_ok=True)
    results: List[dict] = []
    for candidate in candidates:
        summary = run_stage03(candidate, args)
        results.append(summary)

    summarize(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
