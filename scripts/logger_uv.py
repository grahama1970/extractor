#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi>=0.111.0",
#   "uvicorn>=0.30.0",
#   "python-arango>=7.6.3",
#   "tenacity>=9.0.0",
#   "python-dotenv>=1.0.1",
# ]
# ///

import argparse
import uvicorn

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    uvicorn.run("prototypes.gamified.logger:app", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
