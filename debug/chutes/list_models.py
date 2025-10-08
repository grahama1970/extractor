#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os
from pathlib import Path
import requests
from ._preflight import ensure_env

def main():
    ensure_env()
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', choices=['text','json'], default='text')
    args = ap.parse_args()
    base = os.environ['CHUTES_API_BASE'].rstrip('/')
    key = os.environ['CHUTES_API_KEY']
    r = requests.get(base + '/models', headers={'Authorization': f'Bearer {key}'}, timeout=10)
    r.raise_for_status()
    data = r.json().get('data', [])
    models = [m.get('id') for m in data]
    if args.output == 'json':
        print(json.dumps({'count': len(models), 'models': models}, indent=2))
    else:
        print(f'models_count= {len(models)}')
        for mid in models:
            print(mid)

if __name__ == '__main__':
    main()

