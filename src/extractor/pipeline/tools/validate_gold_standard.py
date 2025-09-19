#!/usr/bin/env python3
"""
Validate pipeline outputs against the gold-standard reference.

Compares Stage 07 (reflowed sections) and Stage 08 (Lean4 theorem results)
with data/gold_standards/pipeline/gold_standard_output.json.

Exit code: 0 on pass, 1 on fail (or missing required files).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import typer


# ---- Helper utilities for item-level assertions ----

# Optional similarity tools
try:
    from rapidfuzz.fuzz import token_set_ratio as _token_set_ratio  # type: ignore
except Exception:  # pragma: no cover
    def _token_set_ratio(a: str, b: str) -> float:  # type: ignore
        return 0.0

try:
    from jsonpath_ng.ext import parse as _jp_parse  # type: ignore
except Exception:  # pragma: no cover
    _jp_parse = None  # type: ignore


def _dict_subset_equal(expected: dict, actual: dict) -> bool:
    """Return True if expected is a (recursive) subset of actual."""
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return expected == actual
    for k, v in expected.items():
        if k not in actual:
            return False
        if isinstance(v, dict):
            if not _dict_subset_equal(v, actual.get(k)):
                return False
        elif isinstance(v, list):
            av = actual.get(k)
            if not isinstance(av, list) or len(v) != len(av):
                return False
            for vv, aa in zip(v, av):
                if isinstance(vv, dict):
                    if not _dict_subset_equal(vv, aa):
                        return False
                else:
                    if vv != aa:
                        return False
        else:
            if v != actual.get(k):
                return False
    return True


app = typer.Typer(help="Validate pipeline outputs against gold standards")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load JSON {path}: {e}")


def ci_title_set(items: List[Dict[str, Any]], key: str = "title") -> set[str]:
    s: set[str] = set()
    for it in items or []:
        t = (it.get(key) or "").strip().lower()
        if t:
            s.add(t)
    return s


def compare_sections(gs: Dict[str, Any], run07: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    report: Dict[str, Any] = {"checks": []}
    ok = True

    gs_total = gs.get("total_sections")
    if gs_total is None:
        gs_total = len(gs.get("reflowed_sections", []))
    run_total = len(run07.get("reflowed_sections", []))
    ok_total = gs_total == run_total
    report["checks"].append(
        {"name": "sections_total", "gold": gs_total, "run": run_total, "pass": ok_total}
    )
    ok &= ok_total

    # Titles parity (case-insensitive)
    gst = ci_title_set(gs.get("reflowed_sections", []))
    rnt = ci_title_set(run07.get("reflowed_sections", []))
    missing = sorted(gst - rnt)
    extra = sorted(rnt - gst)
    ok_titles = not missing  # tolerate extra titles but flag missing
    report["checks"].append(
        {
            "name": "section_titles",
            "missing_vs_gold": missing,
            "extra_vs_gold": extra,
            "pass": ok_titles,
        }
    )
    ok &= ok_titles

    # Successful reflows parity
    gs_ok = gs.get("successful_reflows")
    if gs_ok is None:
        gs_ok = sum(
            1 for s in gs.get("reflowed_sections", []) if s.get("reflow_status") == "success"
        )
    rn_ok = sum(
        1 for s in run07.get("reflowed_sections", []) if s.get("reflow_status") == "success"
    )
    ok_sr = gs_ok == rn_ok
    report["checks"].append(
        {"name": "successful_reflows", "gold": gs_ok, "run": rn_ok, "pass": ok_sr}
    )
    ok &= ok_sr

    report["pass"] = ok
    return ok, report


def compare_lean4(gs: Dict[str, Any], run08: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    report: Dict[str, Any] = {"checks": []}
    ok = True

    gs_list = gs.get("lean4_proofs", [])
    rn_list = run08.get("proof_results", [])

    gs_n = len(gs_list)
    rn_n = len(rn_list)
    ok_n = gs_n == rn_n
    report["checks"].append({"name": "lean4_total_items", "gold": gs_n, "run": rn_n, "pass": ok_n})
    ok &= ok_n

    gs_ok = sum(1 for p in gs_list if p.get("success"))
    rn_ok = sum(1 for p in rn_list if p.get("success"))
    ok_s = gs_ok == rn_ok
    report["checks"].append(
        {"name": "lean4_success_count", "gold": gs_ok, "run": rn_ok, "pass": ok_s}
    )
    ok &= ok_s

    report["pass"] = ok
    return ok, report


@app.command()
def run(
    gold_path: Path = typer.Option(
        Path("data/gold_standards/pipeline/gold_standard_output.json"),
        "--gold",
        help="Path to gold standard JSON",
    ),
    reflow_path: Path = typer.Option(
        Path("data/results/pipeline/07_reflow_section/json_output/07_reflowed.json"),
        "--reflow",
        help="Path to Stage 07 reflowed JSON",
    ),
    theorems_path: Path = typer.Option(
        Path("data/results/pipeline/08_lean4_theorem_prover/json_output/08_theorems.json"),
        "--theorems",
        help="Path to Stage 08 theorems JSON",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Output JSON summary instead of pretty text"
    ),
):
    """Validate Stage 07/08 against the gold standard and print a summary."""
    summary: Dict[str, Any] = {
        "gold": str(gold_path),
        "run": {
            "reflow": str(reflow_path),
            "theorems": str(theorems_path),
        },
        "sections": {},
        "lean4": {},
    }

    try:
        gs = load_json(gold_path)
    except Exception as e:
        typer.secho(f"Gold standard load error: {e}", fg=typer.colors.RED)
        if json_out:
            print(json.dumps({"error": str(e)}, indent=2))
        raise typer.Exit(1)

    overall_ok = True

    # Stage 07
    try:
        run07 = load_json(reflow_path)
        ok_sec, sec_rep = compare_sections(gs, run07)
        summary["sections"] = sec_rep
        overall_ok &= ok_sec
    except Exception as e:
        summary["sections"] = {"error": str(e), "pass": False}
        overall_ok = False

    # Stage 08
    try:
        run08 = load_json(theorems_path)
        ok_l4, l4_rep = compare_lean4(gs, run08)
        summary["lean4"] = l4_rep
        overall_ok &= ok_l4
    except Exception as e:
        summary["lean4"] = {"error": str(e), "pass": False}
        overall_ok = False

    summary["pass"] = overall_ok

    if json_out:
        print(json.dumps(summary, indent=2))
    else:
        # Pretty console output
        print("\n=== Gold-standard Validation ===")
        print(f"Gold:     {gold_path}")
        print(f"Reflow:   {reflow_path}")
        print(f"Theorems: {theorems_path}")

        sec = summary.get("sections", {})
        if "error" in sec:
            print(f"\n[Sections] ERROR: {sec['error']}")
        else:
            for c in sec.get("checks", []):
                name = c.get("name")
                passed = "PASS" if c.get("pass") else "FAIL"
                print(
                    f"[Sections] {name}: {passed} -> { {k:v for k,v in c.items() if k not in ('name','pass')} }"
                )

        l4 = summary.get("lean4", {})
        if "error" in l4:
            print(f"\n[Lean4] ERROR: {l4['error']}")
        else:
            for c in l4.get("checks", []):
                name = c.get("name")
                passed = "PASS" if c.get("pass") else "FAIL"
                print(
                    f"[Lean4]  {name}: {passed} -> { {k:v for k,v in c.items() if k not in ('name','pass')} }"
                )

    raise typer.Exit(0 if summary.get("pass") else 1)


# ------------------------------------------------------------
# Per‑stage validator (generic) — used by other tools
# ------------------------------------------------------------

_STAGE_TO_GS: dict[str, str] = {
    "01": "001_annotation_processor_gs.json",
    "02": "002_marker_extractor_gs.json",
    "03": "003_suspicious_headers_gs.json",
    "04": "004_section_builder_gs.json",
    "05": "005_table_extractor_gs.json",
    "06": "006_figure_extractor_gs.json",
    "07": "007_reflow_section_gs.json",
    "08": "008_lean4_theorem_prover_gs.json",
    "09": "009_section_summarizer_gs.json",
    "10": "010_arangodb_exporter_gs.json",
    "11": "011_arango_create_graph_gs.json",
    "12": "012_insert_annotations_gs.json",
    "14": "014_report_generator_gs.json",
}


def _stage_name_for_print(sid: str) -> str:
    mapping = {
        "01": "01_annotation_processor",
        "02": "02_marker_extractor",
        "03": "03_suspicious_headers",
        "04": "04_section_builder",
        "05": "05_table_extractor",
        "06": "06_figure_extractor",
        "07": "07_reflow_section",
        "08": "08_lean4_theorem_prover",
        "09": "09_section_summarizer",
        "10": "10_arangodb_exporter",
        "11": "11_arango_create_graph",
        "12": "12_insert_annotations",
        "14": "14_report_generator",
    }
    return mapping.get(sid, sid)


 



@app.command()
def stage(
    stage_id: str = typer.Argument(..., help="Stage identifier, e.g., 01,02,03,...,11,14"),
    path: Path = typer.Argument(..., help="Path to the stage JSON to validate"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON summary"),
):
    """Validate a single stage file against structural contracts (shape/invariants)."""
    stage_id = stage_id.strip()
    res: Dict[str, Any] = {"stage": stage_id, "path": str(path), "checks": []}

    def add(name: str, cond: bool, detail: Dict[str, Any] | None = None):
        entry = {"name": name, "pass": bool(cond)}
        if detail:
            entry.update(detail)
        res["checks"].append(entry)
        return cond

    try:
        data = load_json(path)
    except Exception as e:
        res["error"] = str(e)
        res["pass"] = False
        if json_out:
            print(json.dumps(res, indent=2))
        else:
            print(f"ERROR: {e}")
        raise typer.Exit(1)

    ok = True
    sid = stage_id

    if sid == "01":
        ok &= add("has_clean_pdf_path", bool(data.get("clean_pdf_path")))
        ok &= add(
            "has_annotations_array",
            isinstance(data.get("annotations"), list),
            {"count": len(data.get("annotations", []))},
        )
        ok &= add(
            "annotation_count_matches",
            data.get("annotation_count") == len(data.get("annotations", [])),
        )
    elif sid == "02":
        ok &= add(
            "has_blocks_array",
            isinstance(data.get("blocks"), list),
            {"count": len(data.get("blocks", []))},
        )
        ok &= add("block_count_matches", data.get("block_count") == len(data.get("blocks", [])))
    elif sid == "03":
        blocks = data.get("blocks", [])
        ok &= add("has_blocks_array", isinstance(blocks, list), {"count": len(blocks)})
        # No remaining suspicious_header
        remain = sum(1 for b in blocks if b.get("suspicious_header") is True)
        ok &= add("no_remaining_suspicious_header", remain == 0, {"remaining": remain})
    elif sid == "04":
        ok &= add("section_count_present", data.get("section_count") is not None)
        ok &= add("sections_array_present", isinstance(data.get("sections"), list))
    elif sid == "05":
        ok &= add("table_count_present", data.get("table_count") is not None)
        ok &= add("tables_array_present", isinstance(data.get("tables", []), list))
    elif sid == "06":
        ok &= add("figure_count_present", data.get("figure_count") is not None)
        ok &= add("figures_array_present", isinstance(data.get("figures", []), list))
    elif sid == "07":
        ok &= add("reflowed_sections_present", isinstance(data.get("reflowed_sections"), list))
        ok &= add("section_count_present", data.get("section_count") is not None)
    elif sid == "08":
        stats = data.get("statistics", {})
        ok &= add("has_statistics", isinstance(stats, dict))
        ok &= add("proof_results_present", isinstance(data.get("proof_results", []), list))
    elif sid == "09":
        ok &= add("summaries_present", isinstance(data.get("summaries", []), list))
    elif sid == "10":
        # Accept either flattened array or confirmation object
        if isinstance(data, list):
            ok &= add("flattened_array_present", len(data) >= 0, {"count": len(data)})
        else:
            ok &= add(
                "has_confirmation_keys",
                any(
                    k in data
                    for k in ("documents_created", "export_success", "exported_collections")
                ),
            )
    elif sid == "11":
        # Accept either edges array or confirmation object
        if isinstance(data, list):
            ok &= add("edges_array_present", len(data) >= 0, {"count": len(data)})
        else:
            ok &= add(
                "has_confirmation_keys",
                any(k in data for k in ("edges_created", "graph_created", "node_counts")),
            )
    elif sid == "14":
        ok &= add(
            "final_report_structure",
            all(
                k in data
                for k in ("overall_quality_score", "sections", "tables", "reflow", "arangodb")
            ),
        )
    else:
        res["error"] = f"Unknown stage id: {sid}"
        res["pass"] = False
        if json_out:
            print(json.dumps(res, indent=2))
        else:
            print(res["error"])
        raise typer.Exit(1)

    res["pass"] = ok
    if json_out:
        print(json.dumps(res, indent=2))
    else:
        print(f"\nStage {sid} validation:")
        for c in res["checks"]:
            print(f" - {c['name']}: {'PASS' if c['pass'] else 'FAIL'}")
        print("Overall:", "PASS" if ok else "FAIL")

    raise typer.Exit(0 if ok else 1)


# -------------------------------------------------------------
# Gold subcommand: auto-map stage -> *_gs.json and compare
# -------------------------------------------------------------

# Mapping of stage id -> gold filename
STAGE_TO_GS: Dict[str, str] = {
    "01": "001_annotation_processor_gs.json",
    "02": "002_marker_extractor_gs.json",
    "03": "003_suspicious_headers_gs.json",
    "04": "004_section_builder_gs.json",
    "05": "005_table_extractor_gs.json",
    "06": "006_figure_extractor_gs.json",
    "07": "007_reflow_section_gs.json",
    "08": "008_lean4_theorem_prover_gs.json",
    "09": "009_section_summarizer_gs.json",
    "10": "010_arangodb_exporter_gs.json",
    "11": "011_arango_create_graph_gs.json",
    "14": "014_report_generator_gs.json",
}


def _gs_dir() -> Path:
    return Path("data/gold_standards/pipeline")


def _has_keys(d: Dict[str, Any], keys: List[str]) -> bool:
    return all(k in d for k in keys)


def compare_against_gs_invariants(
    stage_id: str, run_data: Dict[str, Any], gs_data: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any]]:
    report: Dict[str, Any] = {"stage": stage_id, "checks": []}
    ok = True

    invariants = gs_data.get("expected_invariants", {}) or {}
    sample = gs_data.get("sample", {}) or {}

    def add(name: str, cond: bool, info: Dict[str, Any] | None = None):
        nonlocal ok
        ok = ok and bool(cond)
        entry = {"name": name, "pass": bool(cond)}
        if info:
            entry.update(info)
        report["checks"].append(entry)

    # Generic top-level key presence (only for dict-shaped outputs)
    top_keys = invariants.get("top_level_keys")
    if top_keys and isinstance(run_data, dict):
        add("top_level_keys_present", _has_keys(run_data, top_keys), {"required": top_keys})

    # Status value check (tolerant: only compare if present)
    status_value = invariants.get("status_value")
    if status_value is not None and isinstance(run_data, dict):
        add(
            "status_value_matches",
            run_data.get("status") == status_value,
            {"expected": status_value, "actual": run_data.get("status")},
        )

    # -------- Generalized numeric field checks (non-determinism-friendly) --------
    # numeric_fields_exact/min/max: { field_name: number }
    for field, val in (invariants.get("numeric_fields_exact", {}) or {}).items():
        actual = run_data.get(field)
        add(f"numeric_exact:{field}", actual == val, {"expected": val, "actual": actual})
    for field, val in (invariants.get("numeric_fields_min", {}) or {}).items():
        actual = run_data.get(field)
        ok_field = isinstance(actual, (int, float)) and actual >= val
        add(f"numeric_min:{field}", ok_field, {"min": val, "actual": actual})
    for field, val in (invariants.get("numeric_fields_max", {}) or {}).items():
        actual = run_data.get(field)
        ok_field = isinstance(actual, (int, float)) and actual <= val
        add(f"numeric_max:{field}", ok_field, {"max": val, "actual": actual})

    # -------- Array length checks (exact/min/max) --------
    # array_len_exact/min/max: { array_key: number }
    def _arr_len(d: Dict[str, Any], key: str) -> Optional[int]:
        v = d.get(key)
        return len(v) if isinstance(v, list) else None

    for k, n in (invariants.get("array_len_exact", {}) or {}).items():
        ln = _arr_len(run_data, k)
        add(f"array_len_exact:{k}", ln == n, {"expected": n, "actual": ln})
    for k, n in (invariants.get("array_len_min", {}) or {}).items():
        ln = _arr_len(run_data, k)
        add(f"array_len_min:{k}", (ln is not None and ln >= n), {"min": n, "actual": ln})
    for k, n in (invariants.get("array_len_max", {}) or {}).items():
        ln = _arr_len(run_data, k)
        add(f"array_len_max:{k}", (ln is not None and ln <= n), {"max": n, "actual": ln})

    # -------- Item-level expectations --------
    # Schema:
    # expected_invariants.item_expectations = {
    #   "tables": [
    #       {
    #         "select": {"page_index": 0},
    #         "require": "one",  # one | at_least_one | exactly_n
    #         "exactly_n": 1,     # used when require == exactly_n
    #         "assert": {
    #            "equals": { ... expected partial or full dict ... },
    #            "exact": false   # false => subset match; true => full equality
    #         }
    #       },
    #       ...
    #   ]
    # }
    try:
        item_specs = invariants.get("item_expectations") or {}
        for arr_key, specs in item_specs.items() if isinstance(item_specs, dict) else []:
            items = run_data.get(arr_key)
            if not isinstance(items, list):
                add(
                    f"item_expectations:{arr_key}_is_array",
                    False,
                    {"actual_type": type(items).__name__},
                )
                continue
            for spec in specs or []:
                sel = spec.get("select") or {}
                req = (spec.get("require") or "one").strip()
                n_exact = int(spec.get("exactly_n") or 1)
                assertion = spec.get("assert") or {}
                expected = assertion.get("equals") or {}
                exact = bool(assertion.get("exact", False))

                # filter by simple equality on top-level fields
                def _match(it: dict) -> bool:
                    for k, v in sel.items():
                        if it.get(k) != v:
                            return False
                    return True

                matches = [it for it in items if isinstance(it, dict) and _match(it)]

                # requirement check
                ok_req = True
                if req == "one":
                    ok_req = len(matches) == 1
                elif req == "at_least_one":
                    ok_req = len(matches) >= 1
                elif req == "exactly_n":
                    ok_req = len(matches) == n_exact
                else:
                    ok_req = len(matches) >= 1
                add(
                    f"item_expectations:{arr_key}:select:{sel}",
                    ok_req,
                    {"found": len(matches), "require": req, "exactly_n": n_exact},
                )

                # assertion check against first match if present
                if matches and isinstance(expected, dict) and expected:
                    actual = matches[0]
                    if exact:
                        ok_assert = actual == expected
                    else:
                        ok_assert = _dict_subset_equal(expected, actual)
                    add(f"item_assert:{arr_key}:select:{sel}", ok_assert, {"exact": exact})
    except Exception as _e:
        add("item_expectations_error", False, {"error": str(_e)})

    # -------- Tolerant content similarity / range families --------
    # token_similarity: [{ path, sample_path, threshold(0-1), method? }]
    # list_similarity_coverage: [{ select, sample_select, threshold, coverage }]
    # count_delta_max: [{ select, sample_select, max_delta }]
    # word_count_pct_delta_max: [{ path, sample_path, max_pct }]

    def _jp(values: Dict[str, Any], expr: str) -> List[Any]:
        if not expr or _jp_parse is None:
            return []
        try:
            return [m.value for m in _jp_parse(expr).find(values)]
        except Exception:
            return []

    def _to_text(val: Any) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, (list, tuple)):
            parts: List[str] = []
            for x in val:
                t = _to_text(x)
                if t:
                    parts.append(t)
            return " ".join(parts)
        if isinstance(val, dict):
            return " ".join(str(v) for v in val.values() if isinstance(v, str))
        return ""

    # token similarity checks
    for spec in invariants.get("token_similarity", []) or []:
        path = spec.get("path") or ""
        spath = spec.get("sample_path") or ""
        thr = float(spec.get("threshold") or 0.6)
        run_vals = _jp(run_data, path)
        gold_vals = _jp(sample, spath)
        run_txt = _to_text(run_vals[0] if run_vals else "")
        gold_txt = _to_text(gold_vals[0] if gold_vals else "")
        sim = (_token_set_ratio(run_txt, gold_txt) or 0.0) / 100.0
        add(
            f"token_similarity:{path}",
            sim >= thr,
            {"similarity": round(sim, 3), "threshold": thr},
        )

    # list similarity coverage
    for spec in invariants.get("list_similarity_coverage", []) or []:
        path = spec.get("select") or ""
        spath = spec.get("sample_select") or ""
        thr = float(spec.get("threshold") or 0.6)
        cov = float(spec.get("coverage") or 0.8)
        run_list = _jp(run_data, path)
        gold_list = _jp(sample, spath)
        n = min(len(run_list), len(gold_list))
        hits = 0
        for i in range(n):
            a = _to_text(run_list[i])
            b = _to_text(gold_list[i])
            sim = (_token_set_ratio(a, b) or 0.0) / 100.0
            if sim >= thr:
                hits += 1
        cov_ok = (n > 0) and (hits / max(1, n) >= cov)
        add(
            f"list_similarity_coverage:{path}",
            cov_ok,
            {"hits": hits, "n": n, "threshold": thr, "coverage": cov},
        )

    # count delta max
    for spec in invariants.get("count_delta_max", []) or []:
        path = spec.get("select") or ""
        spath = spec.get("sample_select") or ""
        maxd = int(spec.get("max_delta") or 0)
        run_list = _jp(run_data, path)
        gold_list = _jp(sample, spath)
        d = abs(len(run_list) - len(gold_list))
        add(f"count_delta_max:{path}", d <= maxd, {"delta": d, "max": maxd})

    # word count percentage delta
    def _wc(s: str) -> int:
        return len((s or "").split())
    for spec in invariants.get("word_count_pct_delta_max", []) or []:
        path = spec.get("path") or ""
        spath = spec.get("sample_path") or ""
        maxpct = float(spec.get("max_pct") or 0.25)
        run_txt = _to_text(_jp(run_data, path))
        gs_txt = _to_text(_jp(sample, spath))
        wr, wg = max(1, _wc(run_txt)), max(1, _wc(gs_txt))
        pct = abs(wr - wg) / float(wg)
        add(
            f"word_count_pct_delta_max:{path}",
            pct <= maxpct,
            {"pct": round(pct, 3), "max_pct": maxpct},
        )

    # Stage-specific invariant families
    if stage_id == "01":
        add(
            "has_clean_pdf_path",
            isinstance(run_data.get("clean_pdf_path"), str)
            and len(run_data.get("clean_pdf_path")) > 0,
        )
        anns = run_data.get("annotations", [])
        add("annotations_is_array", isinstance(anns, list), {"count": len(anns)})
        add("annotation_count_matches_len", run_data.get("annotation_count") == len(anns))
        item_keys = invariants.get("annotation_item_keys") or []
        if anns and item_keys:
            add(
                "annotation_item_keys_present",
                all(_has_keys(a, item_keys) for a in anns[: min(5, len(anns))]),
                {"checked_items": min(5, len(anns)), "required": item_keys},
            )

    elif stage_id == "02":
        blocks = run_data.get("blocks", [])
        add("blocks_is_array", isinstance(blocks, list), {"count": len(blocks)})
        add("block_count_matches_len", run_data.get("block_count") == len(blocks))
        req = invariants.get("block_item_keys_min") or []
        if blocks and req:
            add(
                "block_item_keys_present",
                all(_has_keys(b, req) for b in blocks[: min(10, len(blocks))]),
                {"required": req},
            )

    elif stage_id == "03":
        blocks = run_data.get("blocks", [])
        add("blocks_is_array", isinstance(blocks, list), {"count": len(blocks)})
        remain = sum(1 for b in blocks if b.get("suspicious_header") is True)
        add("no_remaining_suspicious_header", remain == 0, {"remaining": remain})

    elif stage_id == "04":
        sections = run_data.get("sections", [])
        add("sections_is_array", isinstance(sections, list), {"count": len(sections)})
        add("section_count_matches_len", run_data.get("section_count") == len(sections))
        req = invariants.get("section_item_keys_min") or []
        if sections and req:
            add(
                "section_item_keys_present",
                all(_has_keys(s, req) for s in sections[: min(5, len(sections))]),
                {"required": req},
            )
        # Check enriched section metadata keys
        meta_keys = invariants.get("section_metadata_keys") or []
        if sections and meta_keys:
            metas_ok = True
            for s in sections[: min(3, len(sections))]:
                md = s.get("metadata", {}) or {}
                if not _has_keys(md, meta_keys):
                    metas_ok = False
                    break
            add("section_metadata_keys_present", metas_ok, {"required": meta_keys})
        # Check per-block hierarchy keys on a sample of blocks
        blk_keys = invariants.get("block_hierarchy_keys") or []
        if sections and blk_keys:
            blocks = sections[0].get("blocks", []) if sections else []
            n = min(5, len(blocks))
            blk_ok = True
            for b in blocks[:n]:
                if not _has_keys(b, blk_keys):
                    blk_ok = False
                    break
            add("block_hierarchy_keys_present", blk_ok, {"required": blk_keys, "checked_blocks": n})

    elif stage_id == "05":
        tables = run_data.get("tables", [])
        add("tables_is_array", isinstance(tables, list), {"count": len(tables)})
        add("table_count_matches_len", run_data.get("table_count") == len(tables))

    elif stage_id == "06":
        figs = run_data.get("figures", [])
        add("figures_is_array", isinstance(figs, list), {"count": len(figs)})
        add("figure_count_matches_len", run_data.get("figure_count") == len(figs))

    elif stage_id == "07":
        sections = run_data.get("reflowed_sections", [])
        add("reflowed_sections_is_array", isinstance(sections, list), {"count": len(sections)})
        add("section_count_matches_len", run_data.get("section_count") == len(sections))
        req = invariants.get("reflowed_item_keys_min") or []
        allowed = set(invariants.get("reflow_status_values", ["success", "fallback"]))
        if sections:
            add(
                "reflow_item_keys_present",
                all(_has_keys(s, req) for s in sections[: min(5, len(sections))]),
                {"required": req},
            )
            add(
                "reflow_status_valid_values",
                all(s.get("reflow_status") in allowed for s in sections),
                {"allowed": sorted(allowed)},
            )
            # Optional keys presence summary
            opt = invariants.get("reflow_optional_keys") or []
            if opt:
                present = sum(1 for s in sections if all(k in s for k in opt))
                add(
                    "optional_reflow_keys_presence",
                    True,
                    {"optional": opt, "present_in": present, "total": len(sections)},
                )

    elif stage_id == "08":
        stats = run_data.get("statistics", {})
        add("statistics_present", isinstance(stats, dict))
        keys = invariants.get("statistics_keys") or []
        if keys:
            add("statistics_keys_present", _has_keys(stats, keys), {"required": keys})
        add("proof_results_array", isinstance(run_data.get("proof_results", []), list))

    elif stage_id == "09":
        sums = run_data.get("summaries", [])
        add("summaries_is_array", isinstance(sums, list), {"count": len(sums)})
        req = invariants.get("summary_item_keys_min") or []
        if sums and req:
            add(
                "summary_item_keys_present",
                all(_has_keys(s, req) for s in sums[: min(5, len(sums))]),
                {"required": req},
            )

    elif stage_id == "10":
        if isinstance(run_data, list):
            add("flattened_array_present", len(run_data) >= 0, {"count": len(run_data)})
        else:
            add(
                "has_confirmation_or_flattened",
                any(
                    k in run_data
                    for k in ("documents_created", "pdf_objects_to_load", "export_success")
                ),
            )

    elif stage_id == "11":
        if isinstance(run_data, list):
            add("edges_array_present", len(run_data) >= 0, {"count": len(run_data)})
        else:
            add("has_edges_or_confirmation", any(k in run_data for k in ("edges_created", "edges")))

    elif stage_id == "14":
        qa = run_data.get("quality_assessment", {})
        add("quality_assessment_present", isinstance(qa, dict))
        keys = invariants.get("quality_assessment_keys") or []
        if keys:
            add("quality_assessment_keys_present", _has_keys(qa, keys), {"required": keys})

    report["pass"] = ok
    return ok, report


@app.command()
def gold(
    stage_id: str = typer.Argument(..., help="Stage identifier, e.g., 01, 02, 03, ... 11, 14"),
    path: Path = typer.Argument(..., help="Path to the stage JSON to compare"),
    gold_dir: Path = typer.Option(
        _gs_dir(), "--gold-dir", help="Directory containing *_gs.json files"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON summary"),
):
    """Auto-map stage -> *_gs.json and compare against expected invariants.

    Tolerant by design: focuses on structure, keys, and counts. Does not require exact content matches.
    """
    sid = stage_id.strip()
    res: Dict[str, Any] = {"stage": sid, "path": str(path)}

    if sid not in STAGE_TO_GS:
        msg = f"Unknown or unsupported stage id: {sid}"
        if json_out:
            print(json.dumps({"error": msg}, indent=2))
        else:
            print(msg)
        raise typer.Exit(1)

    gs_file = gold_dir / STAGE_TO_GS[sid]
    try:
        run_data = load_json(path)
        gs_data = load_json(gs_file)
        ok, report = compare_against_gs_invariants(sid, run_data, gs_data)
        res.update(report)
    except Exception as e:
        res.update({"error": str(e), "pass": False})
        if json_out:
            print(json.dumps(res, indent=2))
        else:
            print(f"ERROR: {e}")
        raise typer.Exit(1)

    if json_out:
        print(json.dumps(res, indent=2))
    else:
        print(f"\nGold compare (stage {sid}): {gs_file}")
        for c in res.get("checks", []):
            print(f" - {c['name']}: {'PASS' if c['pass'] else 'FAIL'}")
        print("Overall:", "PASS" if res.get("pass") else "FAIL")

    raise typer.Exit(0 if res.get("pass") else 1)


if __name__ == "__main__":
    app()
