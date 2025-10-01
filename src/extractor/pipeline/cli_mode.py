from __future__ import annotations
import os
import json
import time
import shlex
import subprocess
from pathlib import Path
import typer


def build_cli() -> typer.Typer:
    app = typer.Typer(add_completion=False)

    @app.command()
    def run(
        pdf: str = typer.Option(..., help="Absolute path to input PDF"),
        results: str = typer.Option(..., help="Output directory for pipeline results"),
        mode: str = typer.Option("fast", help="Extraction mode: fast|accurate", show_default=True),
        json_out: bool = typer.Option(False, "--json", help="Print a short JSON envelope"),
        deterministic: bool = typer.Option(False, help="Force deterministic settings where possible"),
        dry_run: bool = typer.Option(False, help="Print command and exit"),
    ):
        pdf_path = Path(pdf).expanduser().resolve()
        out_dir = Path(results).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        mode = (mode or os.getenv("EXTRACTOR_MODE", "fast")).strip().lower()
        if mode not in ("fast", "accurate"):
            mode = "fast"

        # Deterministic / fast defaults (Happy Path)
        env = os.environ.copy()
        if mode == "fast" or deterministic:
            env.setdefault("LITELLM_DISABLE", "1")
            env.setdefault("CUDA_VISIBLE_DEVICES", "")
            env.setdefault("TOKENIZERS_PARALLELISM", "false")
            env.setdefault("PYTHONHASHSEED", "0")
            try:
                import random
                random.seed(0)
            except Exception:
                pass
            try:
                import numpy as _np
                _np.random.seed(0)
            except Exception:
                pass
            try:
                import torch as _torch  # type: ignore
                _torch.manual_seed(0)
            except Exception:
                pass

        if mode == "fast":
            cmd = ["pipeline-happy", "--pdf", str(pdf_path), "--results", str(out_dir)]
        else:
            cmd = [
                "python",
                "-m",
                "extractor.pipeline.run_all",
                "run",
                "--pdf",
                str(pdf_path),
                "--results",
                str(out_dir),
            ]

        if dry_run:
            typer.echo("CMD: " + " ".join(shlex.quote(c) for c in cmd))
            raise typer.Exit(code=0)

        t0 = time.time()
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        took_ms = int((time.time() - t0) * 1000)
        if proc.returncode != 0 and mode == "accurate":
            typer.echo("\n[hint] Accurate mode failed. Ensure optional deps are installed: 'pip install extractor[accurate]'\n", err=True)

        # Build a minimal final_report.json if none exists
        meta = {
            "pdf": str(pdf_path),
            "results": str(out_dir),
            "mode": mode,
            "took_ms": took_ms,
        }
        report = {"meta": meta, "items": [], "errors": []}
        fr_json = out_dir / "final_report.json"
        if fr_json.exists():
            try:
                existing = json.loads(fr_json.read_text())
                if isinstance(existing, dict):
                    report = existing
                    report.setdefault("meta", {}).update(meta)
                    report.setdefault("items", [])
                    report.setdefault("errors", [])
            except Exception:
                pass
        else:
            try:
                fr_md = out_dir / "final_report.md"
                if fr_md.exists():
                    txt = fr_md.read_text(encoding="utf-8", errors="ignore")[:2000]
                    report["items"].append({"type": "text", "data": txt})
            except Exception:
                pass
            fr_json.write_text(json.dumps(report, indent=2))

        if json_out:
            payload = {
                "ok": proc.returncode == 0,
                "meta": meta,
                "results": str(out_dir),
                "returncode": proc.returncode,
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            stdout_tail = "\n".join((proc.stdout or "").splitlines()[-20:])
            stderr_tail = "\n".join((proc.stderr or "").splitlines()[-20:])
            if stdout_tail:
                typer.echo(stdout_tail)
            if stderr_tail:
                typer.echo(stderr_tail, err=True)
        raise typer.Exit(code=proc.returncode)


    @app.command()
    def doctor():
        """Print available optional extras/capabilities and exit 0/1."""
        caps = {}
        def _probe(name: str, mod: str):
            try:
                __import__(mod)
                caps[name] = True
            except Exception:
                caps[name] = False
        _probe("torch", "torch")
        _probe("transformers", "transformers")
        _probe("sentence_transformers", "sentence_transformers")
        _probe("spacy", "spacy")
        _probe("opencv", "cv2")
        _probe("camelot", "camelot")
        _probe("pandas", "pandas")
        try:
            caps["faiss"] = True
        except Exception:
            caps["faiss"] = False
        print(json.dumps({"caps": caps}, indent=2))
        raise typer.Exit(code=0 if any(caps.values()) else 1)

    return app


def main() -> None:
    build_cli()()


if __name__ == "__main__":
    main()
