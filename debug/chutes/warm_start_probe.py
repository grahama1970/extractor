#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, sys, time, traceback
from pathlib import Path
from datetime import datetime
from ._preflight import ensure_env
from extractor.pipeline.utils.litellm_call import litellm_call


def log_line(fp: Path, msg: str) -> None:
    ts = datetime.utcnow().isoformat()
    line = f"[{ts}] {msg}\n"
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def main():
    # Prepare artifacts
    artifacts_dir = Path("debug/artifacts")
    log_fp = artifacts_dir / "warm_probe_text.log"
    out_fp = artifacts_dir / "warm_probe_text.json"

    log_line(log_fp, "warm_start_probe: starting")
    log_line(log_fp, f"python={sys.executable} cwd={os.getcwd()}")

    # Ensure venv + .env present
    try:
        ensure_env()
        log_line(log_fp, "preflight OK (.venv active, .env loaded)")
    except SystemExit as e:
        log_line(log_fp, f"preflight FAILED: {e}")
        raise

    # Parse args
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--count', type=int, default=10)
    ap.add_argument('--interval', type=float, default=5.0)
    ap.add_argument('--timeout', type=float, default=120)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--output', type=Path, default=out_fp)
    args = ap.parse_args()

    # Log critical env wiring
    env_keys = [
        'CHUTES_API_BASE','CHUTES_API_KEY','OPENAI_BASE_URL','OPENAI_API_KEY',
        'LITELLM_DEFAULT_MODEL','STAGE07B_MODEL','STAGE07C_MODEL','STAGE07D_MODEL',
        'LITELLM_ROUTER_TIMEOUT','STAGE07_REQUEST_TIMEOUT','ENABLE_WARM_START_METRICS',
    ]
    for k in env_keys:
        v = os.getenv(k)
        if not v:
            log_line(log_fp, f"env {k}=<unset>")
        elif 'KEY' in k:
            log_line(log_fp, f"env {k}=<set:{len(v)}chars>")
        else:
            log_line(log_fp, f"env {k}={v}")

    # Force LiteLLM verbose debug if requested
    if os.getenv('LITELLM_DEBUG','0').lower() in {'1','true','yes','y'}:
        log_line(log_fp, 'LITELLM_DEBUG is enabled')

    lat, sts, errs = [], [], []
    for i in range(args.count):
        log_line(log_fp, f"attempt {i+1}/{args.count} model={args.model} timeout={args.timeout}s retries={args.retries}")
        t0 = time.perf_counter()
        try:
            import asyncio as _asyncio
            async def _once():
                return await litellm_call([
                    {"model": args.model,
                     "messages":[{"role":"user","content":"ping"}],
                     "kwargs": {"temperature":0}}
                ], wrap_json=False, concurrency=1, request_timeout=args.timeout,
                   num_retries=args.retries, desc='warm_probe', show_progress=False)
            res = _asyncio.run(_asyncio.wait_for(_once(), args.timeout + 10))
            elapsed = (time.perf_counter()-t0)*1000.0
            lat.append(elapsed); sts.append('ok'); errs.append(None)
            # Log short content preview if available
            preview = None
            try:
                if res and hasattr(res[0], 'content'):
                    preview = (res[0].content or '')[:120].replace('\n',' ')
            except Exception:
                preview = None
            log_line(log_fp, f"result ok in {elapsed:.1f}ms content_preview={json.dumps(preview)}")
        except Exception as e:
            elapsed = (time.perf_counter()-t0)*1000.0
            lat.append(elapsed); sts.append('error'); errs.append(repr(e))
            log_line(log_fp, f"result error in {elapsed:.1f}ms exc={e.__class__.__name__}: {e}")
            tb = traceback.format_exc(limit=5)
            log_line(log_fp, f"traceback: {tb.strip()}")
        time.sleep(args.interval)

    out = {
        'model': args.model,
        'timestamp': datetime.utcnow().isoformat(),
        'latencies_ms': lat,
        'statuses': sts,
        'errors': errs,
        'p50_ms': sorted(lat)[int(0.5*(len(lat)-1))] if lat else 0,
        'p95_ms': sorted(lat)[int(0.95*(len(lat)-1))] if lat else 0,
        'env': {k: ('<set>' if 'KEY' in k and os.getenv(k) else os.getenv(k) or '<unset>') for k in env_keys}
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2))
    log_line(log_fp, f'warm probe written: {args.output}')

if __name__ == '__main__':
    main()
