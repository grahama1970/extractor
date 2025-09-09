# Debuggable Typer CLI: Patterns and Playbook

This guide shows how to build a Typer-based CLI that is easy to run, debug, and test without a specialized harness. It references `tests/stage07_manual/images/qwen3_smoke.py` as a concrete example.

## Goals

- Fast to run from terminal and editors (VS Code, PyCharm) without a launch.json
- Breakpoint-friendly: no top-level side effects; pure runner functions
- Import-safe: `if __name__ == "__main__": app()`
- Clear separation of CLI parsing vs business logic
- Sensible defaults + env var overrides for quick iteration

## Minimal Project Pattern

- File layout:
  - `your_tool.py` (Typer app + thin CLI)
  - `your_module.py` (pure functions used by CLI)
- Entry pattern:
  - `app = typer.Typer()`
  - Define commands with `@app.command()`
  - Guard: `if __name__ == "__main__": app()`

## Example: Single-command CLI (no subcommand needed)

```
import typer

app = typer.Typer(help="My debuggable CLI")

def core_run(arg: str) -> str:
    # Pure logic (easy to unit test)
    return arg.upper()

@app.command()
def main(arg: str = typer.Option("hello", "--arg", "-a", envvar="MY_ARG")):
    """Run the core function with options/env overrides."""
    out = core_run(arg)
    print(out)

if __name__ == "__main__":
    app()
```

Run/debug:
- Terminal: `python your_tool.py -a world`
- VS Code: “Run Python File” works; breakpoints fire in both CLI and `core_run`.
- Env override: `MY_ARG=world python your_tool.py`

## Example: Our Qwen Multimodal Smoke CLI

File: `tests/stage07_manual/images/qwen3_smoke.py`

Highlights:
- `run_mm(...)`: pure runner; safe to import and unit test
- CLI options with defaults and env vars: `--image/-i`, `--model/-m`, `--prompt/-p`, `--temperature`, `--max-tokens`, `--max-side`
- Robust image handling: path or URL → data URI; optional downscale (Pillow)
- `.env` loading inside the runner to avoid editor configuration steps

Invocation:
- Default (uses repo panda image + qwen-vl-max):
  - `python tests/stage07_manual/images/qwen3_smoke.py`
- Custom image and model:
  - `python tests/stage07_manual/images/qwen3_smoke.py -i tests/stage07_manual/images/smoke/panda.png -m openrouter/qwen/qwen-vl-max`
- Using env vars:
  - `SMOKE_IMAGE=... SMOKE_MODEL=... python tests/stage07_manual/images/qwen3_smoke.py`

## Best Practices Checklist

- Import-safety
  - `if __name__ == "__main__": app()` at file end
  - Move real work into pure functions; keep CLI thin

- Debuggability
  - Load `.env` in the runner; avoid relying on editor profiles
  - Provide defaults so running without args “just works”
  - Keep network/image dependencies optional or self-contained (data URIs)

- Options and Env Vars
  - Use `envvar="VAR_NAME"` on Typer options for frictionless overrides
  - Keep option defaults explicit and discoverable via `--help`

- Testing
  - Unit test the pure functions (no Typer involved)
  - Add a tiny integration test that calls the CLI via `subprocess.run`

- Performance/Robustness
  - Downscale large images; prefer `JPEG` for size if alpha not required
  - Bound network calls or provide offline paths (data URIs)

## Optional: Subcommands vs Single Command

- Single root command (this guide’s examples): simplest to run/debug
- Subcommands: use when you have multiple distinct actions
  - `app = typer.Typer()` then `@app.command("describe")` etc.
  - Call as: `python tool.py describe --flag ...`

## Optional: VS Code launch.json (when needed)

You don’t need one for simple cases, but if you want a curated config:

```
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Qwen Smoke",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/tests/stage07_manual/images/qwen3_smoke.py",
      "console": "integratedTerminal",
      "args": ["-i", "tests/stage07_manual/images/smoke/panda.png", "-m", "openrouter/qwen/qwen-vl-max"],
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

## Troubleshooting

- 400 errors fetching remote images: embed as data URIs instead of URLs
- Provider/model issues: try a smaller/alternate model (e.g., qwen-vl-plus or qwen-2.5-vl)
- Large payloads: reduce `--max-side` or compress to JPEG

## Conclusion

Keep CLIs thin and import-safe, centralize logic in pure functions, and offer pragmatic defaults + env overrides. This combination makes tools debuggable without extra editor setup and keeps integration simple.

