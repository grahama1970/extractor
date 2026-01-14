import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", required=True)
    args = parser.parse_args()
    print("failing step running")
    print("simulated failure", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
