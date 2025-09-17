#!/usr/bin/env python3
"""
Prompt Optimizer CLI
- Validates and optimizes gamified run specs prior to launching Codex instances.
- Uses rules from prototypes/gamified/rules/prompt_optimization.yaml

Usage:
  python -m prototypes.gamified.tools.prompt_opt optimize prompt.md -o optimized.md --show-diff
  python -m prototypes.gamified.tools.prompt_opt validate prompt.md --strict
  python -m prototypes.gamified.tools.prompt_opt lint prompt.md
"""
from __future__ import annotations

import json
import re
import sys
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer

try:
    import yaml  # PyYAML
except Exception as e:  # pragma: no cover
    yaml = None

try:
    from loguru import logger
except Exception:  # pragma: no cover
    class _MiniLogger:
        def info(self, *a, **k): print(*a)
        def warning(self, *a, **k): print("WARN:", *a)
        def error(self, *a, **k): print("ERR:", *a, file=sys.stderr)
        def debug(self, *a, **k): print("DBG:", *a)
    logger = _MiniLogger()

app = typer.Typer(add_completion=False, invoke_without_command=True, no_args_is_help=False)

RULES_DEFAULT = Path("prototypes/gamified/rules/prompt_optimization.yaml")

@dataclass
class LintIssue:
    level: str   # "error" | "warning" | "info"
    code: str
    message: str

@dataclass
class OptimizationReport:
    added_sections: List[str] = field(default_factory=list)
    normalized_sections: bool = False
    normalized_weights: bool = False
    renamed_approaches: List[Tuple[str, str]] = field(default_factory=list)
    built_evidence_checklists: bool = False
    added_tasks: bool = False
    warnings: List[LintIssue] = field(default_factory=list)
    errors: List[LintIssue] = field(default_factory=list)

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.M)
_CODEBLOCK_RE = re.compile(r"```(\w+)?\n(.*?)\n```", re.S)

def _snake(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^\w\s-]+", "", s)
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).lower()
    return s

def _sum_weights(weights: Dict[str, float]) -> float:
    return float(sum(float(v) for v in weights.values()))

def _load_rules(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _extract_sections(md: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(md))
    if not matches:
        return {"__body__": md}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        title = m.group(2).strip().lower()
        sections[title] = md[start:end].strip()
    return sections

def _get_code_block(md: str, language: str) -> Optional[str]:
    for m in _CODEBLOCK_RE.finditer(md):
        lang = (m.group(1) or "").lower()
        if lang == language.lower():
            return m.group(2)
    return None

def _ensure_order(keys: List[str], desired: List[str]) -> List[str]:
    seen = set()
    ordered = [k for k in desired if k in keys and not (k in seen or seen.add(k))]
    for k in keys:
        if k not in seen:
            ordered.append(k)
    return ordered

def _yaml_load_block(text: str) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML required to parse YAML blocks. pip install pyyaml")
    return yaml.safe_load(text)

def _yaml_dump(obj: Any) -> str:
    if yaml is None:
        raise RuntimeError("PyYAML required to dump YAML. pip install pyyaml")
    return yaml.safe_dump(obj, sort_keys=False)

class PromptOptimizer:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules

    def validate_and_optimize(self, raw_md: str) -> Tuple[str, OptimizationReport]:
        r = self.rules
        rep = OptimizationReport()
        sec = _extract_sections(raw_md)

        # Required sections
        for must in r["required_sections"]["must_exist"]:
            if must not in sec:
                rep.added_sections.append(must)
                sec[must] = self._default_section(must)

        # Order
        desired_order = r["required_sections"]["order"]
        current_keys = list(sec.keys())
        ordered = _ensure_order(current_keys, desired_order)
        if ordered != current_keys:
            rep.normalized_sections = True

        # Approaches
        approaches_yaml = self._extract_approaches_yaml(sec.get("approaches", ""))
        approaches = self._parse_approaches(approaches_yaml, rep)
        self._enforce_approach_counts(approaches, rep)
        approaches_yaml_out = _yaml_dump(approaches)

        # Scoring
        scoring_yaml = self._extract_scoring_yaml(sec.get("scoring", ""))
        weights = scoring_yaml.get("weights") or r["scoring"]["defaults"]["weights"]
        weights_norm, changed = self._normalize_weights(weights)
        scoring_yaml["weights"] = weights_norm
        if changed:
            rep.normalized_weights = True
        sec["scoring"] = self._render_yaml_section("weights", scoring_yaml["weights"])

        # Constraints
        sec["constraints"] = self._ensure_constraints(sec.get("constraints", ""), rep)

        # Evidence
        sec["evidence"] = self._build_evidence(sec.get("evidence", ""), approaches, rep)

        # Execution
        if not sec.get("execution"):
            sec["execution"] = self._render_yaml_section("execution", r["execution_defaults"])

        # Tasks
        if not sec.get("tasks"):
            rep.added_tasks = True
            pre_tasks = [
                {"type": "run_python", "name": "log_context", "scope": "pre",
                 "code": "print('Tokamak approaches: fueling_mpc, edge_stability_mhd, heat_extraction_adaptive')"},
                {"type": "run_python", "name": "emit_references", "scope": "pre",
                 "code": "print('Key refs in References section')"},
            ]
            sec["tasks"] = "```json\n" + json.dumps(pre_tasks, indent=2) + "\n```"

        # Style lints
        self._lint_style(raw_md, rep)

        # Rebuild Markdown
        pies = []
        for key in ordered:
            title = key if key != "__body__" else "Gamified Run Spec"
            pies.append(f"## {title.capitalize()}\n\n{sec[key].strip()}\n")
        optimized_md = "\n".join(pies).strip()

        # Replace approaches section with YAML list form
        optimized_md = re.sub(
            r"(## Approaches\s*\n\n).*?(?=## |\Z)",
            r"\1```yaml\n" + approaches_yaml_out + "```\n\n",
            optimized_md,
            flags=re.S
        )

        return optimized_md, rep

    # Helpers
    def _default_section(self, name: str) -> str:
        r = self.rules
        if name == "execution":
            return self._render_yaml_section("execution", r["execution_defaults"])
        if name == "scoring":
            return self._render_yaml_section("weights", r["scoring"]["defaults"]["weights"])
        if name == "constraints":
            defaults = r["constraints"]["defaults"]
            return self._render_yaml_section("constraints", defaults)
        if name == "evidence":
            return ""
        if name == "approaches":
            return "```yaml\n- name: placeholder\n  summary: TBD\n  verification: []\n  outputs: []\n```\n"
        return ""

    def _render_yaml_section(self, root_key: str, data: Any) -> str:
        return "```yaml\n" + _yaml_dump({root_key: data}) + "```"

    def _extract_approaches_yaml(self, approaches_md: str) -> str:
        block = _get_code_block(approaches_md, "yaml")
        if block:
            return block
        # Fallback: collect "- name:" lines
        lines = []
        for line in approaches_md.splitlines():
            if line.strip().startswith("- name:"):
                lines.append(line.strip())
        return "\n".join(lines) if lines else "- name: placeholder"

    def _parse_approaches(self, yaml_text: str, rep: OptimizationReport) -> List[Dict[str, Any]]:
        try:
            data = _yaml_load_block(yaml_text)
        except Exception as e:
            rep.errors.append(LintIssue("error", "yaml_parse", f"Failed to parse approaches YAML: {e}"))
            data = [{"name": "placeholder"}]
        if not isinstance(data, list):
            data = [data]
        rules = self.rules["approach"]
        out = []
        for item in data:
            name_raw = str(item.get("name", "placeholder"))
            name_snake = _snake(name_raw)
            pref = rules.get("canonical_prefix") or ""
            new_name = name_snake if not pref or name_snake.startswith(pref) else f"{pref}{name_snake}"
            if new_name != name_raw:
                rep.renamed_approaches.append((name_raw, new_name))
            item["name"] = new_name[:40]
            for f in rules["required_fields"]:
                if f not in item or item[f] in (None, "", []):
                    if f == "summary":
                        item["summary"] = "TBD"
                    elif f == "verification":
                        item["verification"] = []
                    elif f == "outputs":
                        item["outputs"] = []
            out.append(item)
        return out

    def _enforce_approach_counts(self, approaches: List[Dict[str, Any]], rep: OptimizationReport) -> None:
        rules = self.rules["approach"]
        n = len(approaches)
        min_c, max_c = rules["min_count"], rules["max_count"]
        if n < min_c:
            rep.errors.append(LintIssue("error", "approach_count", f"Need at least {min_c} approaches; found {n}."))
        if n > max_c:
            rep.errors.append(LintIssue("error", "approach_count", f"At most {max_c} approaches; found {n}."))

    def _extract_scoring_yaml(self, scoring_md: str) -> Dict[str, Any]:
        block = _get_code_block(scoring_md, "yaml")
        if block:
            try:
                val = _yaml_load_block(block)
                return val if isinstance(val, dict) else {}
            except Exception:
                return {}
        m = re.search(r"weights:\s*\{([^\}]+)\}", scoring_md)
        if m:
            items = [x.strip() for x in m.group(1).split(",")]
            kv = {}
            for it in items:
                if ":" in it:
                    k, v = it.split(":")
                    kv[k.strip()] = float(v.strip())
            return {"weights": kv}
        return {"weights": self.rules["scoring"]["defaults"]["weights"]}

    def _normalize_weights(self, weights: Dict[str, float]) -> Tuple[Dict[str, float], bool]:
        bounds = self.rules["scoring"]["bounds_per_axis"]
        total_required = float(self.rules["scoring"]["sum_must_equal"])
        changed = False
        clamped = {}
        for k, v in weights.items():
            lo, hi = bounds.get(k, [0, 100])
            vv = max(lo, min(hi, float(v)))
            if vv != v:
                changed = True
            clamped[k] = vv
        s = _sum_weights(clamped)
        if abs(s - total_required) > 1e-6 and self.rules["scoring"]["normalize_if_needed"]:
            if s == 0:
                clamped = self.rules["scoring"]["defaults"]["weights"].copy()
                s = _sum_weights(clamped)
            factor = total_required / s
            clamped = {k: round(v * factor, 6) for k, v in clamped.items()}
            changed = True
        return clamped, changed

    def _ensure_constraints(self, constraints_md: str, rep: OptimizationReport) -> str:
        r = self.rules["constraints"]
        block = _get_code_block(constraints_md, "yaml")
        if not block:
            defaults = r["defaults"]
            out = self._render_yaml_section("constraints", defaults)
            rep.errors.append(LintIssue("error", "constraints_missing", "Constraints injected with placeholders; define required globals."))
            return out
        try:
            data = _yaml_load_block(block) or {}
            # Error if any placeholder remains
            for k in r["global_keys"]:
                v = data.get(k)
                if v in (None, "", "define"):
                    rep.errors.append(LintIssue("error", "constraint_undefined", f"Constraint '{k}' is undefined"))
        except Exception as e:
            rep.errors.append(LintIssue("error", "constraints_parse", f"Failed to parse constraints: {e}"))
        return constraints_md

    def _build_evidence(self, evidence_md: str, approaches: List[Dict[str, Any]], rep: OptimizationReport) -> str:
        schema = self.rules["evidence_schema"]
        keys = schema["required"]
        checklist = []
        for a in approaches:
            checklist.append({
                "approach": a["name"],
                "expected": [{k["key"]: f"({k['type']})"} for k in keys]
            })
        rep.built_evidence_checklists = True
        return "```yaml\n" + _yaml_dump(checklist) + "```"

    def _lint_style(self, raw_md: str, rep: OptimizationReport) -> None:
        style = self.rules.get("style", {})
        forbid = style.get("forbid_words", [])
        for w in forbid:
            if re.search(rf"\b{re.escape(w)}\b", raw_md, flags=re.I):
                rep.warnings.append(LintIssue("warning", "forbidden_word", f"Found discouraged word: '{w}'"))
        summaries = re.findall(r"summary:\s*(.+)", raw_md)
        max_chars = style.get("max_summary_chars", 10**6)
        for s in summaries:
            if len(s.strip()) > max_chars:
                rep.warnings.append(LintIssue("warning", "summary_length", f"Summary exceeds {max_chars} chars."))

def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def _show_diff(a: str, b: str) -> str:
    diff = difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile="raw", tofile="optimized", lineterm="")
    return "\n".join(diff)

def _print_report(rep: OptimizationReport) -> None:
    if rep.added_sections:
        logger.info(f"Added sections: {', '.join(rep.added_sections)}")
    if rep.normalized_sections:
        logger.info("Normalized section order.")
    if rep.normalized_weights:
        logger.info("Normalized scoring weights (sum==100).")
    if rep.renamed_approaches:
        changes = ", ".join([f"{a}->{b}" for a, b in rep.renamed_approaches])
        logger.info(f"Canonicalized approach names: {changes}")
    if rep.built_evidence_checklists:
        logger.info("Built evidence checklists.")
    if rep.added_tasks:
        logger.info("Injected pre-run tasks.")
    for w in rep.warnings:
        logger.warning(f"[{w.code}] {w.message}")
    for e in rep.errors:
        logger.error(f"[{e.code}] {e.message}")

@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    if ctx.invoked_subcommand is not None:
        return
    logger.info("No subcommand provided; running DEBUG optimize on inline sample.")
    sample = """# Gamified Run Spec — Tokamak Efficiency (3 Approaches)

## Approaches
- name: fueling_density_mpc
  summary: Increase core density while keeping confinement.
  verification: [MPC, PDE]
  outputs: [density_profile, constraints_ok]

## Scoring
weights: { correctness: 35, speed: 25, robustness: 25, brevity: 15 }
"""
    rules = _load_rules(RULES_DEFAULT)
    opt = PromptOptimizer(rules)
    optimized, rep = opt.validate_and_optimize(sample)
    _print_report(rep)
    print("\n--- Optimized Markdown ---\n")
    print(optimized)

@app.command()
def print_rules(
    rules_path: Path = typer.Option(RULES_DEFAULT, "--rules", "-r", help="Path to rules YAML")
):
    rules = _load_rules(rules_path)
    if yaml is None:
        print(json.dumps(rules, indent=2))
    else:
        print(_yaml_dump(rules))

@app.command()
def validate(
    prompt_path: Path = typer.Argument(..., help="Path to raw prompt (Markdown)"),
    rules_path: Path = typer.Option(RULES_DEFAULT, "--rules", "-r"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors")
):
    raw = _load_text(prompt_path)
    rules = _load_rules(rules_path)
    opt = PromptOptimizer(rules)
    optimized, rep = opt.validate_and_optimize(raw)
    _print_report(rep)
    failed = len(rep.errors) > 0 or (strict and len(rep.warnings) > 0)
    raise typer.Exit(code=1 if failed else 0)

@app.command()
def optimize(
    prompt_path: Path = typer.Argument(..., help="Path to raw prompt (Markdown)"),
    out_path: Optional[Path] = typer.Option(None, "--out", "-o", help="Write optimized prompt here"),
    rules_path: Path = typer.Option(RULES_DEFAULT, "--rules", "-r"),
    show_diff: bool = typer.Option(False, "--show-diff", help="Print unified diff")
):
    raw = _load_text(prompt_path)
    rules = _load_rules(rules_path)
    opt = PromptOptimizer(rules)
    optimized, rep = opt.validate_and_optimize(raw)
    _print_report(rep)
    if show_diff:
        print("\n--- Diff (raw → optimized) ---")
        print(_show_diff(raw, optimized))
    if out_path:
        _write_text(out_path, optimized)
        logger.info(f"Wrote optimized prompt → {out_path}")
    else:
        print("\n--- Optimized Markdown ---\n")
        print(optimized)

@app.command()
def lint(
    prompt_path: Path = typer.Argument(..., help="Path to raw prompt (Markdown)"),
    rules_path: Path = typer.Option(RULES_DEFAULT, "--rules", "-r")
):
    raw = _load_text(prompt_path)
    rules = _load_rules(rules_path)
    opt = PromptOptimizer(rules)
    _, rep = opt.validate_and_optimize(raw)
    _print_report(rep)

if __name__ == "__main__":
    app()

