import importlib.util
import sys
from dotenv import load_dotenv, find_dotenv


def main():
    try:
        load_dotenv(find_dotenv())
        p = "src/extractor/pipeline/steps/s08_lean4_theorem_prover.py"
        spec = importlib.util.spec_from_file_location("stage08", p)
        if not spec or not spec.loader:
            raise RuntimeError("Failed to load Stage 08 module")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]

        # Consider it OK if module imports and exposes a CLI builder or run function
        # We added 'run' alias specifically for this check
        ok = hasattr(mod, "build_cli") or hasattr(mod, "run")
        if not ok:
            raise RuntimeError("Stage 08 lacks CLI/run entrypoints")
        print("OK: Stage 08 module imported and has CLI/run entrypoint")
    except Exception as e:
        print(f"Smoke failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
