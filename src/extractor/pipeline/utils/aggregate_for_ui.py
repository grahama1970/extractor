from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


def _sha12(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except Exception:
        return None


def _mini_hash(block: Dict[str, Any]) -> str:
    core = {
        "p": block.get("page") or block.get("page_idx"),
        "t": block.get("block_type"),
        "txt": (block.get("text") or "")[:80],
        "b": block.get("bbox"),
    }
    try:
        payload = json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = b""
    return hashlib.sha1(payload).hexdigest()[:8]


def build_ui_bundle(results_dir: Path, fail_soft: bool = True) -> None:
    """Aggregate stage artifacts into a single UI-facing JSON bundle.

    Writes: <results_dir>/ui/blocks_full.json
    """
    rd = Path(results_dir)
    try:
        stage02 = rd / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
        stage03 = rd / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
        tables_f = rd / "05_table_extractor" / "json_output" / "05_tables.json"
        figs_f = rd / "06_figure_extractor" / "json_output" / "06_figures.json"
        suspects_f = rd / "suspects.json"
        pdf_guess = list((rd / "01_annotation_processor").glob("*_clean.pdf"))[:1]
        pdf_path = pdf_guess[0] if pdf_guess else None
        # Optional page sizes for UI scaling
        page_sizes = []
        if pdf_path and pdf_path.exists():
            try:
                import fitz  # type: ignore
                _doc = fitz.open(pdf_path)
                for i, p in enumerate(_doc):
                    page_sizes.append({
                        "page": i,
                        "width": float(p.rect.width),
                        "height": float(p.rect.height),
                    })
                _doc.close()
            except Exception:
                pass

        s02 = json.loads(stage02.read_text()) if stage02.exists() else {}
        s03 = json.loads(stage03.read_text()) if stage03.exists() else {}
        tjs = json.loads(tables_f.read_text()) if tables_f.exists() else {}
        fjs = json.loads(figs_f.read_text()) if figs_f.exists() else {}
        sus = json.loads(suspects_f.read_text()) if suspects_f.exists() else {}

        # Prefer Stage 03 verified blocks when present
        blocks = (s03.get("blocks") if isinstance(s03, dict) else None) or (s02.get("blocks") if isinstance(s02, dict) else None) or []
        if not isinstance(blocks, list):
            blocks = []
        for b in blocks:
            if isinstance(b, dict):
                b["page"] = b.get("page_idx", b.get("page"))
                b["type"] = b.get("block_type", b.get("type"))
                b["mini_hash"] = _mini_hash(b)
                # Flatten Stage 03 reasoning if present
                try:
                    if isinstance(b.get("llm_verification"), dict):
                        res = b["llm_verification"].get("result") or {}
                        if isinstance(res, dict):
                            b["reasoning"] = res.get("reasoning")
                            b["is_header_verified"] = res.get("is_header")
                except Exception:
                    pass
                # Provide a decision key useful for UI mapping
                try:
                    b.setdefault(
                        "decision_key",
                        f"{b.get('page')}:{b.get('block_id') or b.get('id') or b['mini_hash']}",
                    )
                except Exception:
                    pass

        doc_id = None
        if pdf_path:
            h = _sha12(pdf_path)
            stem = pdf_path.stem.lower().replace(" ", "_")
            doc_id = f"{stem}__{h}" if h else stem

        out_dir = rd / "ui"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Try to include/import PDF gold annotations (overlay-only fallback)
        pdf_gold_f = out_dir / "gold_from_pdf.json"
        if not pdf_gold_f.exists() and pdf_path and pdf_path.exists():
            try:
                from extractor.pipeline.tools.pdf_annot_import import import_pdf as _import_pdf  # type: ignore
                _import_pdf(results_dir=rd, pdf_path=pdf_path)
            except Exception:
                pass
        pdf_gold = {}
        try:
            if pdf_gold_f.exists():
                pdf_gold = json.loads(pdf_gold_f.read_text()) or {}
        except Exception:
            pdf_gold = {}

        bundle = {
            "doc_id": doc_id,
            "generated_at": datetime.utcnow().isoformat(),
            "pdf_sha256_12": _sha12(pdf_path),
            "blocks": blocks,
            "tables": tjs.get("tables", []) if isinstance(tjs, dict) else [],
            "figures": fjs.get("figures", []) if isinstance(fjs, dict) else [],
            "suspects": sus if isinstance(sus, dict) else {},
            "page_sizes": page_sizes,
            # default gold shape; will be filled below from Stage-01 or pdf overlay
            "gold": {"blocks": [], "metrics": {}},
            "source": {
                "stage02": str(stage02) if stage02.exists() else None,
                "stage03": str(stage03) if stage03.exists() else None,
                "tables": str(tables_f) if tables_f.exists() else None,
                "figures": str(figs_f) if figs_f.exists() else None,
                "suspects": str(suspects_f) if suspects_f.exists() else None,
                "gold_from_pdf": str(pdf_gold_f) if pdf_gold_f.exists() else None,
            },
            "counts": {
                "blocks": len(blocks),
                "tables": len(tjs.get("tables", [])) if isinstance(tjs, dict) else 0,
                "figures": len(fjs.get("figures", [])) if isinstance(fjs, dict) else 0,
                "gold": int(pdf_gold.get("count") or 0),
                "suspicious_total": (sus.get("suspicious_total") if isinstance(sus, dict) else None),
            },
            "table_coverage": None,
            "gold_imported": False,
        }
        # Table coverage heuristic
        try:
            verify_root = rd / "05_table_extractor" / "verify"
            tlist = tjs.get("tables", []) if isinstance(tjs, dict) else []
            if tlist:
                verified = 0
                for t in tlist:
                    rid = t.get("raw_table_id") or t.get("table_id")
                    if not rid:
                        continue
                    if (verify_root / rid.replace("rawtbl_", "table_") / "view.html").exists():
                        verified += 1
                bundle["table_coverage"] = verified / max(1, len(tlist))
        except Exception:
            pass

        # ---------------- Stage‑01 GOLD import, matching, metrics ----------------
        try:
            gold_enabled = os.getenv("GOLD_IMPORT_ENABLED", "1").lower() in {"1","true","yes","y"}
            ann_json = rd / "01_annotation_processor" / "json_output" / "01_annotations.json"
            if gold_enabled and ann_json.exists():
                anns = json.loads(ann_json.read_text()).get("annotations", [])
                stage01_gold = []
                for a in anns:
                    rect = a.get("expanded_rect") or a.get("original_rect")
                    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                        continue
                    try:
                        bbox = [float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])]
                    except Exception:
                        continue
                    gtype = (((a.get("interpretation") or {}).get("inferred_object") or {}).get("type") or a.get("type") or "Text")
                    stage01_gold.append({
                        "gold_id": a.get("id"),
                        "page": a.get("page"),
                        "type": str(gtype),
                        "bbox": bbox,
                    })
                # Thresholds
                base = float(os.getenv("GOLD_IOU_DEFAULT", "0.50"))
                th = {
                    "SectionHeader": float(os.getenv("GOLD_IOU_SECTIONHEADER", str(base))),
                    "Table": float(os.getenv("GOLD_IOU_TABLE", "0.60")),
                    "Figure": float(os.getenv("GOLD_IOU_FIGURE", "0.55")),
                    "ListItem": float(os.getenv("GOLD_IOU_LISTITEM", str(base))),
                    "Text": float(os.getenv("GOLD_IOU_TEXT", str(base))),
                }
                # Index model blocks by page
                by_page: Dict[int, list] = {}
                for mb in blocks:
                    try:
                        by_page.setdefault(int(mb.get("page") or 0), []).append(mb)
                    except Exception:
                        continue
                # IoU helper
                def iou(b1, b2):
                    try:
                        x0 = max(b1[0], b2[0]); y0 = max(b1[1], b2[1])
                        x1 = min(b1[2], b2[2]); y1 = min(b1[3], b2[3])
                        if x1 <= x0 or y1 <= y0:
                            return 0.0
                        inter = (x1 - x0) * (y1 - y0)
                        a1 = max(0, (b1[2]-b1[0])) * max(0, (b1[3]-b1[1]))
                        a2 = max(0, (b2[2]-b2[0])) * max(0, (b2[3]-b2[1]))
                        if a1 <= 0 or a2 <= 0:
                            return 0.0
                        return inter / (a1 + a2 - inter)
                    except Exception:
                        return 0.0
                # Candidates
                cands = []
                for gb in stage01_gold:
                    plist = by_page.get(int(gb.get("page") or 0), [])
                    best = None; best_iou = 0.0
                    ttype = str(gb.get("type") or "Text")
                    thresh = th.get(ttype, base)
                    for mb in plist:
                        if str(mb.get("type")) != ttype:
                            continue
                        biou = iou(gb["bbox"], mb.get("bbox") or [0,0,0,0])
                        if biou > best_iou:
                            best_iou = biou; best = mb
                    if best and best_iou >= thresh:
                        cands.append((gb, best, best_iou))
                # Greedy one-to-one
                used_g=set(); used_m=set(); matches=[]
                for gb, mb, sc in sorted(cands, key=lambda x: x[2], reverse=True):
                    gid = gb.get("gold_id"); mid = mb.get("mini_hash")
                    if gid in used_g or mid in used_m:
                        continue
                    used_g.add(gid); used_m.add(mid); matches.append((gb, mb, sc))
                # Annotate model blocks
                for gb, mb, sc in matches:
                    mb["gold_match"] = {"gold_id": gb.get("gold_id"), "iou": round(sc,4), "type": gb.get("type")}
                # Metrics
                track = {"SectionHeader", "Table", "Figure"}
                if os.getenv("GOLD_INCLUDE_LISTITEM","0").lower() in {"1","true","yes","y"}:
                    track.add("ListItem")
                tp = {t:0 for t in track}; fp = {t:0 for t in track}; fn = {t:0 for t in track}
                matched_gids = {gb.get("gold_id") for gb,_,_ in matches}
                matched_mini = {mb.get("mini_hash") for _,mb,_ in matches if mb.get("mini_hash")}
                for t in track:
                    tp[t] = sum(1 for gb,mb,_ in matches if gb.get("type")==t)
                    fn[t] = sum(1 for gb in stage01_gold if gb.get("type")==t and gb.get("gold_id") not in matched_gids)
                    fp[t] = sum(1 for mb in blocks if mb.get("type")==t and mb.get("mini_hash") not in matched_mini)
                def _prf(TP, FP, FN):
                    p = TP/(TP+FP) if (TP+FP)>0 else 0.0
                    r = TP/(TP+FN) if (TP+FN)>0 else 0.0
                    f1 = (2*p*r/(p+r)) if (p+r)>0 else 0.0
                    return round(p,4), round(r,4), round(f1,4)
                precision={}; recall={}; f1={}
                for t in track:
                    p,r,f = _prf(tp[t], fp[t], fn[t]); precision[t]=p; recall[t]=r; f1[t]=f
                macro_f1 = round(sum(f1[t] for t in track)/len(track),4) if track else 0.0
                total_tp=sum(tp.values()); total_fp=sum(fp.values()); total_fn=sum(fn.values())
                mp = total_tp/(total_tp+total_fp) if (total_tp+total_fp)>0 else 0.0
                mr = total_tp/(total_tp+total_fn) if (total_tp+total_fn)>0 else 0.0
                mf1 = (2*mp*mr/(mp+mr)) if (mp+mr)>0 else 0.0
                bundle["gold"] = {
                    "blocks": stage01_gold,
                    "metrics": {
                        "tp_by_type": tp,
                        "fp_by_type": fp,
                        "fn_by_type": fn,
                        "precision_by_type": precision,
                        "recall_by_type": recall,
                        "f1_by_type": f1,
                        "macro_f1": macro_f1,
                        "micro_precision": round(mp,4),
                        "micro_recall": round(mr,4),
                        "micro_f1": round(mf1,4),
                        "track_types": sorted(list(track)),
                        "matched": len(matches),
                        "gold_total": len(stage01_gold),
                        "model_total_tracked": sum(1 for b in blocks if b.get("type") in track),
                    }
                }
                bundle["gold_imported"] = True
            else:
                # Fallback: pdf annotation gold overlay only
                if isinstance(pdf_gold.get("items"), list):
                    bundle["gold"] = {"blocks": pdf_gold.get("items", []), "metrics": {}}
                    bundle["counts"]["gold"] = int(pdf_gold.get("count") or 0)
        except Exception:
            if not fail_soft:
                raise
            # keep bundle as-is on failure
        (out_dir / "blocks_full.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    except Exception:
        if fail_soft:
            return
        raise
