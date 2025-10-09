#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from pathlib import Path
from ._preflight import ensure_env
from extractor.pipeline.utils.litellm_call import litellm_call

def main():
    ensure_env()
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--batch-size', type=int, default=8)
    ap.add_argument('--concurrency', type=int, default=2)
    ap.add_argument('--timeout', type=float, default=90)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--output', type=Path, default=Path('debug/artifacts/router_probe.json'))
    args = ap.parse_args()

    prompts = [{"model": args.model, "messages":[{"role":"user","content":[{"type":"text","text":f"probe {i}"}]}], "kwargs": {"temperature":0}} for i in range(args.batch_size)]
    res = __import__('asyncio').run(litellm_call(prompts, wrap_json=False, concurrency=args.concurrency, request_timeout=args.timeout, num_retries=args.retries, desc='router_probe', show_progress=False))
    ok = sum(1 for r in res if r)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'model': args.model, 'batch_size': args.batch_size, 'concurrency': args.concurrency, 'ok': ok, 'errors': args.batch_size-ok}, indent=2))
    print(f'router probe written: {args.output}')

if __name__ == '__main__':
    main()

