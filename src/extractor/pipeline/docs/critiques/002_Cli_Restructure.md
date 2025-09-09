You’re right—this got too fancy. Here’s the **sane, minimal** approach that works for both you and the agent.

# 1) One file per step. Logic first. Typer only in `__main__`.

* Put **all real work** in a `run(...)` function using only stdlib imports at the top.
* Import Typer **only inside** the `if __name__ == "__main__":` block.
* Result: the agent can import and call `run()` directly (no Typer needed). Humans still get Typer UX.

```python
# src/extractor/pipeline/steps/section_summarizer.py
from pathlib import Path

def run(input_path: str | Path, out_dir: str | Path, *, verbose: bool = False) -> None:
    input_path = Path(input_path); out_dir = Path(out_dir)
    # ... business logic only; no Typer/tqdm at import time ...

if __name__ == "__main__":
    # Typer is imported only when launching as a CLI
    import typer
    app = typer.Typer(add_completion=False)

    @app.command()
    def cli(
        input_path: Path,
        out_dir: Path,
        verbose: bool = typer.Option(False, "--verbose", "-v"),
    ):
        run(input_path, out_dir, verbose=verbose)

    app()
```

Why this is sane:

* **Humans**: `python section_summarizer.py cli ...` → full Typer experience.
* **Agent**: `from ...section_summarizer import run` → calls function directly; no Typer import occurs at import time.

# 2) VS Code (for you): pin the venv once

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Section Summarizer (Typer)",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/extractor/pipeline/steps/section_summarizer.py",
      "args": [
        "cli",
        "${workspaceFolder}/data/results/pipeline/07_reflow_section/json_output/07_reflow.json",
        "--out-dir", "${workspaceFolder}/data/results/pipeline",
        "--verbose"
      ],
      "python": "${workspaceFolder}/.venv/bin/python",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal"
    }
  ]
}
```

# 3) Agent (for everything): call functions directly

No extra files needed. Two simple ways:

* **Dotted import one-liner** (per step):

```bash
python -c "from extractor.pipeline.steps.section_summarizer import run; \
run('path/to/in.json','path/to/out', verbose=True)"
```

* **(Optional) tiny stdlib runner** (single generic file if you want a helper):

```python
# src/extractor/function_runner.py  (≈20 lines)
import argparse, importlib, json, sys
p = argparse.ArgumentParser(); p.add_argument("--call", required=True); p.add_argument("--json", default="{}")
a = p.parse_args()
mod, fn = a.call.split(":"); f = getattr(importlib.import_module(mod), fn)
kwargs = json.loads(a.json or "{}")
res = f(**kwargs)
if res is not None: print(json.dumps(res, default=str))
```

Use:

```bash
python -m extractor.function_runner \
  --call extractor.pipeline.steps.section_summarizer:run \
  --json '{"input_path":"path/to/in.json","out_dir":"path/to/out","verbose":true}'
```

# 4) Checklist to implement (5 minutes)

1. For each step file, move work into `run(...)` and keep top-level imports stdlib-only.
2. Put Typer inside `if __name__ == "__main__":` (as shown).
3. Pin `.venv` interpreter in VS Code (config above).
4. (Optional) Add `function_runner.py` if you want a generic agent entrypoint; otherwise the agent just imports and calls.

That’s it—**simple, predictable, minimal**. Humans use Typer; the agent calls the same functions directly. No extra directories, no wrappers, no complexity.
