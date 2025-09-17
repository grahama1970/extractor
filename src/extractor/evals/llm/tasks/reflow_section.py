from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from extractor.evals.llm.harness import chat_call, calc_cost, write_json, load_yaml
from extractor.evals.llm.metrics.reflow_metrics import eval_reflow
from extractor.pipeline.utils.model_params import image_file_to_data_url
from extractor.pipeline.utils.vision import preflight_vision_support


def build_user_text(context_text: str, hints: Dict[str, Any]) -> str:
    hint_cols = hints.get("columns") or []
    hint_shape = hints.get("shape")
    hint_text = ""
    if hint_cols or hint_shape:
        hint_text = f"\n\nTable Hints:\n- columns: {json.dumps(hint_cols, ensure_ascii=False)}\n- shape: {json.dumps(hint_shape)}\n"
    return (context_text[:2400] + hint_text).strip()


async def run_reflow_eval(
    models_file: Path,
    ratecards_file: Path,
    registry_file: Path,
    system_text: str,
    run_dir: Path,
    *,
    text_min_chars: int = 150,
    row_tolerance: float = 0.10,
    require_top_keys: bool = True,
    require_vision: bool = True,
    max_cost: float | None = None,
) -> Dict[str, Any]:
    models = load_yaml(models_file).get("models") or []
    pricing = load_yaml(ratecards_file).get("models") or {}
    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    datasets = registry.get("datasets") or []

    results: List[Dict[str, Any]] = []
    cumulative_cost = 0.0
    for model in models:
        model_dir = run_dir / model.replace("/", "__")
        model_dir.mkdir(parents=True, exist_ok=True)
        model_ok = True
        total_cost = 0.0
        per_items: List[Dict[str, Any]] = []
        # Vision preflight once per model
        vis_ok = True
        try:
            vis_ok = await preflight_vision_support(model, timeout_sec=10)
        except Exception:
            vis_ok = False
        if require_vision and not vis_ok:
            # Mark all dataset items as failed due to vision rejection
            for item in datasets:
                cid = item.get("id")
                metrics = {
                    "vision_capable": False,
                    "fail_reason": "vision_rejected",
                    "has_reflowed_json": False,
                    "table_count": 0,
                    "figure_count": 0,
                    "titles_inferred": False,
                    "table_columns_ok": None,
                    "rows_within_tolerance": None,
                    "has_good_text": False,
                    "has_required_top_keys": False,
                    "ok": False,
                }
                write_json(model_dir / f"{cid}__metrics.json", metrics)
                per_items.append({"id": cid, "metrics": metrics, "cost": 0.0})
            results.append({"model": model, "ok": False, "total_cost_usd": 0.0, "items": per_items})
            # Continue to next model without attempting calls
            continue
        for item in datasets:
            cid = item.get("id")
            ctext = Path(item["context_path"]).read_text(encoding="utf-8")
            image_url = None
            ipath = item.get("image_path")
            if ipath and Path(ipath).exists():
                image_url = image_file_to_data_url(Path(ipath))
            user_text = build_user_text(ctext, item.get("hints") or {})
            call = await chat_call(model, system_text, user_text, image_url)
            # Save artifacts
            (model_dir / f"{cid}__raw.txt").write_text(call.content or "", encoding="utf-8")
            if call.parsed:
                write_json(model_dir / f"{cid}__parsed.json", call.parsed)
            write_json(model_dir / f"{cid}__usage.json", call.usage)

            metrics = eval_reflow(
                call.parsed or {},
                {k: item.get(k) for k in ["expected_tables", "expected_figures"]},
                item.get("hints") or {},
                text_min_chars=text_min_chars,
                row_tolerance=row_tolerance,
                require_top_keys=require_top_keys,
            )
            metrics["vision_capable"] = vis_ok
            if not metrics.get("ok") and "fail_reason" not in metrics:
                # derive a simple fail reason
                reasons: List[str] = []
                if not metrics.get("has_required_top_keys"):
                    reasons.append("missing_top_keys")
                if not metrics.get("titles_inferred"):
                    reasons.append("missing_titles")
                if metrics.get("table_columns_ok") is False:
                    reasons.append("columns_mismatch")
                if metrics.get("rows_within_tolerance") is False:
                    reasons.append("rows_out_of_tolerance")
                if not metrics.get("has_good_text"):
                    reasons.append("insufficient_text")
                if not metrics.get("has_reflowed_json"):
                    reasons.append("no_reflowed_json")
                metrics["fail_reason"] = ",".join(reasons) if reasons else "unknown"
            write_json(model_dir / f"{cid}__metrics.json", metrics)
            cost = calc_cost(model, call.usage, call.provider_cost_reported, pricing)
            write_json(
                model_dir / f"{cid}__cost.json",
                {
                    "provider_cost_reported": call.provider_cost_reported,
                    "estimated_cost_usd": cost,
                },
            )
            per_items.append({"id": cid, "metrics": metrics, "cost": cost})
            model_ok = model_ok and bool(metrics.get("ok"))
            total_cost += float(cost or 0.0)
            cumulative_cost += float(cost or 0.0)
            if max_cost is not None and cumulative_cost >= float(max_cost):
                # Stop adding more model work; return partial summary
                break
        results.append(
            {
                "model": model,
                "ok": model_ok,
                "total_cost_usd": total_cost if total_cost > 0 else None,
                "items": per_items,
            }
        )
        if max_cost is not None and cumulative_cost >= float(max_cost):
            break
    # choose recommendation: first all-ok sorted by cost, else cheapest overall
    ok_models = [r for r in results if r.get("ok")]
    if ok_models:
        best = sorted(ok_models, key=lambda r: (r.get("total_cost_usd") or 1e9))[0]
    else:
        best = sorted(results, key=lambda r: (r.get("total_cost_usd") or 1e9))[0]
    summary = {"results": results, "recommendation": best}
    return summary
