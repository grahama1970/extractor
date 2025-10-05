#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, time
from pathlib import Path
from ._preflight import ensure_env
from extractor.pipeline.utils.litellm_call import litellm_call

def main():
    ensure_env()
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--count', type=int, default=10)
    ap.add_argument('--interval', type=float, default=5.0)
    ap.add_argument('--timeout', type=float, default=120)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--output', type=Path, default=Path('debug/artifacts/warm_probe.json'))
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    lat, sts, errs = [], [], []
    for i in range(args.count):
        t0 = time.perf_counter()
        try:
            __import__('asyncio').run(litellm_call([
                {"model": args.model, "messages":[{"role":"user","content":[{"type":"text","text":"ping"}]}], "kwargs": {"temperature":0}}
            ], wrap_json=False, concurrency=1, request_timeout=args.timeout, num_retries=args.retries, desc='warm_probe', show_progress=False))
            lat.append((time.perf_counter()-t0)*1000.0); sts.append('ok'); errs.append(None)
        except Exception as e:
            lat.append((time.perf_counter()-t0)*1000.0); sts.append('error'); errs.append(str(e))
        time.sleep(args.interval)

    out = {
        'model': args.model,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
        'latencies_ms': lat,
        'statuses': sts,
        'errors': errs,
        'p50_ms': sorted(lat)[int(0.5*(len(lat)-1))] if lat else 0,
        'p95_ms': sorted(lat)[int(0.95*(len(lat)-1))] if lat else 0,
    }
    args.output.write_text(json.dumps(out, indent=2))
    print(f'warm probe written: {args.output}')

if __name__ == '__main__':
    main()

