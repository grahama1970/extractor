"""
Stage 07 Orchestrator
=====================

Deterministic structural pass + optional plugin chain.
Outputs (for compatibility):
  data/results/pipeline/07_reflow_section/json_output/07_reflowed.json
  data/results/pipeline/07_reflow_section/json_output/07_reflow_manifest.json
  data/results/pipeline/07_reflow_section/stage_07_reflow.log
"""

from __future__ import annotations
import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Optional

import typer
from rich.console import Console
from loguru import logger

# Safe-load structural pass despite numeric filename using importlib
import importlib.util as _ilu

_STRUCT_PATH = Path(__file__).resolve().parent / "07_structural_pass.py"
_spec = _ilu.spec_from_file_location("steps_07_structural_pass", str(_STRUCT_PATH))
if _spec and _spec.loader:
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
    build_structural_reflow = getattr(_mod, "build_structural_reflow")  # type: ignore[assignment]
else:
    raise ImportError("Failed to load 07_structural_pass.py")

app = typer.Typer(add_completion=False, help="Stage 07 Orchestrator")
console = Console()


@dataclass
class PipelineState:
    sections: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    run_id: str = ""
    deterministic_hash: Optional[str] = None


PluginFn = Callable[[PipelineState, Dict[str, Any]], PipelineState]
PLUGIN_REGISTRY: Dict[str, PluginFn] = {}


def plugin(name: str):
    def _wrap(fn: PluginFn) -> PluginFn:
        PLUGIN_REGISTRY[name] = fn
        return fn
    return _wrap


@plugin("table_titles")
def plugin_table_titles(state: PipelineState, ctx: Dict[str, Any]) -> PipelineState:
    last_heading_fallback = ""
    for sec in state.sections:
        last_heading = sec.get("title") or last_heading_fallback
        # Scan for heading-like blocks to update context
        for blk in sec.get("blocks", []):
            if isinstance(blk, dict) and blk.get("type") == "heading" and blk.get("text"):
                last_heading = blk["text"]
        for t in sec.get("tables", []):
            if not t.get("title") and last_heading:
                t["title"] = f"INFERRED: {last_heading[:80]}"
        last_heading_fallback = last_heading or last_heading_fallback
    state.diagnostics.append({"plugin": "table_titles", "status": "ok"})
    return state


@plugin("figure_captions")
def plugin_figure_captions(state: PipelineState, ctx: Dict[str, Any]) -> PipelineState:
    for sec in state.sections:
        for f in sec.get("figures", []):
            cap = (f.get("caption") or f.get("alt") or "").strip()
            if not cap:
                f["caption"] = "Figure"
    state.diagnostics.append({"plugin": "figure_captions", "status": "ok"})
    return state


@plugin("requirements")
def plugin_requirements(state: PipelineState, ctx: Dict[str, Any]) -> PipelineState:
    import re
    MODALITY_RE = re.compile(r"\b(shall|must|should|will)\b", re.IGNORECASE)
    REQID_RE = re.compile(r"\bREQ[-_][A-Z0-9]+[-_]?\d+\b")
    COND_RE = re.compile(r"\b(if|when|unless)\b.*?\b(shall|must|will|should)\b", re.IGNORECASE | re.DOTALL)

    def sentences(text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
        return [p.strip() for p in parts if p.strip()]

    candidates: List[Dict[str, Any]] = []
    for sec in state.sections:
        sid = sec.get("id") or sec.get("section_id")
        for b in sec.get("blocks", []):
            btype = (b.get("type") or "").lower()
            if btype not in {"paragraph", "text", "listitem"}:
                continue
            raw = (b.get("text") or "").strip()
            if not raw:
                continue
            for sent in sentences(raw):
                if not MODALITY_RE.search(sent):
                    continue
                rid = REQID_RE.search(sent)
                cond = COND_RE.search(sent)
                candidates.append({
                    "from": "paragraph",
                    "text_raw": sent,
                    "text_canonical": sent,
                    "modality": MODALITY_RE.search(sent).group(1).lower(),  # type: ignore
                    "condition": cond.group(0) if cond else None,
                    "confidence": 0.7 + (0.2 if rid else 0.0),
                    "source": {"section_id": sid},
                    "req_id_hint": rid.group(0) if rid else None,
                })
        for t in sec.get("tables", []):
            rows = t.get("pandas_df") or []
            if not isinstance(rows, list):
                continue
            for r in rows:
                if not isinstance(r, dict):
                    continue
                for cell in r.values():
                    txt = str(cell).strip()
                    if not txt or not MODALITY_RE.search(txt):
                        continue
                    rid = REQID_RE.search(txt)
                    cond = COND_RE.search(txt)
                    candidates.append({
                        "from": "table_cell",
                        "text_raw": txt,
                        "text_canonical": txt,
                        "modality": MODALITY_RE.search(txt).group(1).lower(),  # type: ignore
                        "condition": cond.group(0) if cond else None,
                        "confidence": 0.5 + (0.2 if rid else 0.0),
                        "source": {"section_id": sid},
                        "req_id_hint": rid.group(0) if rid else None,
                    })
    for i, c in enumerate(candidates):
        c["id"] = f"req_{i:06d}"
    state.metadata["requirements"] = {
        "total": len(candidates),
        "by_source": {
            "paragraph": sum(1 for c in candidates if c["from"] == "paragraph"),
            "table_cell": sum(1 for c in candidates if c["from"] == "table_cell"),
        },
    }
    # Also emit legacy artifacts so run_all can skip standalone miner.
    out_root = Path(ctx["output_dir"]) / "07_requirements_miner" / "json_output"
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "07_requirements.json").write_text(
        json.dumps({"requirements": candidates}, indent=2, ensure_ascii=False)
    )
    (out_root / "07_requirements_summary.json").write_text(
        json.dumps({
            "total": len(candidates),
            "by_source": state.metadata["requirements"]["by_source"],
            "timestamp": datetime.utcnow().isoformat(),
        }, indent=2, ensure_ascii=False)
    )
    state.metadata["requirements_list"] = candidates
    state.diagnostics.append({"plugin": "requirements", "status": "ok"})
    return state


def compute_deterministic_hash(sections: List[Dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for s in sections:
        sid = str(s.get("id") or "")
        rt = (s.get("reflowed_text") or "")[:128]
        h.update(f"{sid}:{rt}".encode("utf-8", "ignore"))
    return h.hexdigest()


def run_plugins(state: PipelineState, ordered_plugins: List[str], ctx: Dict[str, Any]) -> PipelineState:
    for name in ordered_plugins:
        fn = PLUGIN_REGISTRY.get(name)
        if not fn:
            state.diagnostics.append({"plugin": name, "status": "skipped_missing"})
            continue
        t0 = time.monotonic()
        try:
            state = fn(state, ctx)
            elapsed = int((time.monotonic() - t0) * 1000)
            state.diagnostics.append({"plugin": name, "elapsed_ms": elapsed})
        except Exception as e:
            state.diagnostics.append({"plugin": name, "status": "error", "error": str(e)})
    return state


@app.command()
def run(
    sections: Path = typer.Option(..., "--sections", exists=True, readable=True),
    tables: Path = typer.Option(..., "--tables", exists=True, readable=True),
    figures: Path = typer.Option(..., "--figures", exists=True, readable=True),
    annotations: Optional[Path] = typer.Option(None, "--annotations", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
    summary_only: bool = typer.Option(False, "--summary-only"),
):
    start_ts = time.monotonic()
    summary_only = summary_only or (os.getenv("SUMMARY_ONLY07", "").lower() in ("1", "true", "yes", "y"))
    out_root = output_dir / "07_reflow_section"
    json_out = out_root / "json_output"
    out_root.mkdir(parents=True, exist_ok=True)
    json_out.mkdir(exist_ok=True)

    console.print("[cyan]Stage 07 Orchestrator starting...[/cyan]")
    logger.info("Stage 07 start summary_only=%s", summary_only)

    struct_res = build_structural_reflow(
        sections_path=sections,
        tables_path=tables,
        figures_path=figures,
        annotations_path=annotations,
        summary_only=summary_only,
    )
    state = PipelineState(
        sections=struct_res["sections"],
        metadata={"struct_metrics": struct_res["metrics"], "summary_only": summary_only},
        diagnostics=struct_res.get("diagnostics", []),
        run_id=struct_res.get("run_id", ""),
    )

    plugin_env = os.getenv("STAGE07_PLUGINS", "").strip()
    ordered_plugins: List[str] = []
    if not summary_only:
        if plugin_env:
            ordered_plugins = [p.strip() for p in plugin_env.split(",") if p.strip()]
        else:
            ordered_plugins = ["table_titles", "figure_captions"]
        if os.getenv("STAGE07_ENABLE_REQUIREMENTS", "1").lower() in {"1", "true", "yes", "y"} and "requirements" not in ordered_plugins:
            ordered_plugins.append("requirements")

    ctx = {"output_dir": str(output_dir), "summary_only": summary_only}
    state = run_plugins(state, ordered_plugins, ctx)

    try:
        state.deterministic_hash = compute_deterministic_hash(state.sections)
    except Exception as e:
        state.diagnostics.append({"phase": "hash", "error": str(e)})

    final_payload = {
        "timestamp": datetime.now().isoformat(),
        "status": "Completed",
        "summary_only": summary_only,
        "sections_count": len(state.sections),
        "deterministic_hash": state.deterministic_hash,
        "reflowed_sections": state.sections,
        "metadata": state.metadata,
        "diagnostics": state.diagnostics,
        "plugins_executed": ordered_plugins,
    }
    out_path = json_out / "07_reflowed.json"
    out_path.write_text(json.dumps(final_payload, indent=2, ensure_ascii=False))

    manifest = {
        "run_id": state.run_id,
        "plugins": ordered_plugins,
        "hash": state.deterministic_hash,
        "summary_only": summary_only,
        "generated_at": datetime.now().isoformat(),
    }
    (json_out / "07_reflow_manifest.json").write_text(json.dumps(manifest, indent=2))

    (out_root / "stage_07_reflow.log").write_text(json.dumps({
        "sections": len(state.sections),
        "plugins": ordered_plugins,
        "elapsed_ms": int((time.monotonic() - start_ts) * 1000),
        "hash": state.deterministic_hash,
    }, indent=2))

    # Deterministic sidecar for resume logic
    try:
        det_side = {
            "hash": state.deterministic_hash,
            "sections": len(state.sections),
            "plugins": ordered_plugins,
        }
        (json_out / "deterministic.json").write_text(json.dumps(det_side, indent=2))
    except Exception as e:
        state.diagnostics.append({"phase": "deterministic_sidecar", "error": str(e)})

    # Optional schema validation artifact
    if os.getenv("STAGE07_VALIDATE", "0").lower() in {"1", "true", "yes", "y"}:
        def _validate_sections_shape(state_: PipelineState) -> List[Dict[str, Any]]:
            issues: List[Dict[str, Any]] = []
            for idx, s in enumerate(state_.sections):
                if "id" not in s:
                    issues.append({"section_index": idx, "problem": "missing_id"})
                if not isinstance(s.get("blocks"), list):
                    issues.append({"section_index": idx, "problem": "blocks_not_list"})
                for b_i, b in enumerate(s.get("blocks", [])):
                    if not isinstance(b, dict):
                        issues.append({"section_index": idx, "block_index": b_i, "problem": "block_not_dict"})
                        continue
                    if "text" not in b or "type" not in b:
                        issues.append({"section_index": idx, "block_index": b_i, "problem": "missing_text_or_type"})
            return issues

        issues = _validate_sections_shape(state)
        (json_out / "07_reflow_validate.json").write_text(json.dumps({"issues": issues, "count": len(issues)}, indent=2))

    console.print(f"[green]Stage 07 complete[/green] -> {out_path}")


def build_cli():
    return app


if __name__ == "__main__":
    app()
