#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-arango>=7.6.0",
# ]
# ///
from __future__ import annotations

import json
import os
from pathlib import Path
import typer

try:
    from arango import ArangoClient  # type: ignore
except Exception:  # pragma: no cover
    ArangoClient = None  # type: ignore

app = typer.Typer(add_completion=False)


def _load_json(p: Path):
    """Load JSON from path."""
    return json.loads(p.read_text())


def _edge_hints_to_edges(hints: dict) -> dict:
    """Extract edge relationships from a hints dictionary."""
    sections = {s["key"]: s for s in hints.get("nodes", {}).get("sections", [])}
    lemmas = {lemma["key"]: lemma for lemma in hints.get("nodes", {}).get("lemmas", [])}
    depends_on = hints.get("edges", {}).get("depends_on", [])
    contradicts = hints.get("edges", {}).get("contradicts_candidates", [])
    refines = hints.get("edges", {}).get("refines_candidates", [])
    return {
        "nodes": {"sections": list(sections.values()), "lemmas": list(lemmas.values())},
        "edges": {"depends_on": depends_on, "contradicts": contradicts, "refines": refines},
    }


def _flat10_to_edges(flat10: dict) -> dict:
    """Extract edges from a flat10 dictionary structure."""
    items = flat10.get("items") or []
    sections = {}
    lemmas = {}
    contradicts = []
    refines = []
    by_core = {}
    for it in items:
        sid = (it.get("section_id") or "").strip()
        if not sid:
            continue
        rtm = it.get("rtm") or {}
        norm = (rtm.get("lean4_norm") or "").strip()
        pol = rtm.get("lean4_polarity")
        pre = None  # Stage 10 currently doesn’t pass preconditions; optional
        sections.setdefault(
            sid, {"key": sid, "doc_id": it.get("doc_id"), "normalized_prop": norm, "polarity": pol}
        )
        # negate-insensitive core
        low = norm.lower()
        core = (
            low.replace("shall not", "shall")
            .replace("must not", "must")
            .replace(" cannot ", " can ")
            .replace(" can't ", " can ")
        )
        core = core.replace(" not ", " ")
        core = " ".join(core.split())
        by_core.setdefault(core, []).append(
            {"section_id": sid, "polarity": pol, "precondition": pre}
        )
        # lemmas
        for nm in rtm.get("lean4_lemmas") or []:
            name = str(nm).strip()
            if not name:
                continue
            key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
            lemmas.setdefault(key, {"key": key, "name": name})
    # contradicts
    for core, arr in by_core.items():
        for i in range(len(arr)):
            for j in range(i + 1, len(arr)):
                ai, aj = arr[i], arr[j]
                if ai.get("polarity") and aj.get("polarity") and ai["polarity"] != aj["polarity"]:
                    contradicts.append(
                        {
                            "a": ai["section_id"],
                            "b": aj["section_id"],
                            "reason": "opposite_polarity_same_prop",
                        }
                    )
    # refines (simple precondition presence heuristic)
    # not available here; keep empty list
    depends_on = []
    for it in items:
        sid = (it.get("section_id") or "").strip()
        for nm in it.get("rtm", {}).get("lean4_lemmas") or []:
            name = str(nm).strip()
            key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
            depends_on.append({"from": sid, "to": key, "source": "used_lemmas"})
    return {
        "nodes": {"sections": list(sections.values()), "lemmas": list(lemmas.values())},
        "edges": {"depends_on": depends_on, "contradicts": contradicts, "refines": refines},
    }


@app.command()
def main(
    source: Path = typer.Argument(
        ..., help="edge_hints.json from Lean4 or Stage 10 flattened JSON"
    ),
    out_edges: Path = typer.Argument(..., help="Output edges JSON"),
    arango_db: str = typer.Option(
        "",
        "--arangodb",
        help="If set, upsert nodes/edges into this DB (requires ARANGODB_URL/USERNAME/PASSWORD)",
    ),
    fallback_lemma_candidates: bool = typer.Option(
        False,
        "--fallback-lemma-candidates/--no-fallback-lemma-candidates",
        help="Use lemma_candidates when used_lemmas is empty",
    ),
):
    """Process edge hints from Lean4 or Stage 10 JSON and output edges."""
    obj = _load_json(source)
    edges = obj
    if "nodes" in obj and "edges" in obj and "depends_on" in obj.get("edges", {}):
        # edge hints already
        edges = _edge_hints_to_edges(obj)
    elif "items" in obj:
        edges = _flat10_to_edges(obj)
        if fallback_lemma_candidates:
            # If no depends_on edges found, try candidates
            if not edges["edges"]["depends_on"]:
                items = obj.get("items") or []
                for it in items:
                    sid = (it.get("section_id") or "").strip()
                    cand = it.get("rtm", {}).get("lemma_candidates") or []
                    for nm in cand:
                        name = str(nm).strip()
                        if not name:
                            continue
                        key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
                        edges["nodes"]["lemmas"].append({"key": key, "name": name})
                        edges["edges"]["depends_on"].append(
                            {"from": sid, "to": key, "source": "lemma_candidates"}
                        )
    else:
        typer.secho(
            "Unrecognized input; expected edge_hints or Stage 10 flattened JSON",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)
    out_edges.write_text(json.dumps(edges, indent=2, ensure_ascii=False))
    typer.secho(f"OK: wrote {out_edges}", fg=typer.colors.GREEN)

    if arango_db:
        if ArangoClient is None:
            typer.secho("python-arango not installed; skipping DB upsert", fg=typer.colors.YELLOW)
            return
        url = os.getenv("ARANGODB_URL", "http://localhost:8529")
        user = os.getenv("ARANGODB_USERNAME", os.getenv("ARANGODB_USER", "root"))
        pwd = os.getenv("ARANGODB_PASSWORD")
        if not pwd:
            typer.secho("Set ARANGODB_PASSWORD for DB upsert", fg=typer.colors.RED)
            return
        client = ArangoClient(hosts=url)  # type: ignore
        sys_db = client.db("_system", username=user, password=pwd)
        if not sys_db.has_database(arango_db):
            sys_db.create_database(arango_db)
        db = client.db(arango_db, username=user, password=pwd)
        for col in ("sections", "lemmas"):
            if not db.has_collection(col):
                db.create_collection(col)
        for ecol in ("depends_on", "contradicts", "refines"):
            if not db.has_collection(ecol):
                db.create_collection(ecol, edge=True)
        # upsert nodes
        sec = db.collection("sections")
        lem = db.collection("lemmas")
        for s in edges["nodes"]["sections"]:
            s2 = dict(s)
            s2.setdefault("_key", s2.pop("key"))
            sec.insert(s2, overwrite=True)
        for lemma in edges["nodes"]["lemmas"]:
            lemma_payload = dict(lemma)
            lemma_payload.setdefault("_key", lemma_payload.pop("key"))
            lem.insert(lemma_payload, overwrite=True)
        # edges
        dep = db.collection("depends_on")
        con = db.collection("contradicts")
        ref = db.collection("refines")
        for e in edges["edges"]["depends_on"]:
            dep.insert(
                {
                    "_from": f"sections/{e['from']}",
                    "_to": f"lemmas/{e['to']}",
                    "source": e.get("source"),
                }
            )
        for e in edges["edges"]["contradicts"]:
            con.insert(
                {
                    "_from": f"sections/{e['a']}",
                    "_to": f"sections/{e['b']}",
                    "reason": e.get("reason"),
                }
            )
        for e in edges["edges"]["refines"]:
            ref.insert(
                {
                    "_from": f"sections/{e['refiner']}",
                    "_to": f"sections/{e['refined']}",
                    "reason": e.get("reason"),
                }
            )
        typer.secho(f"OK: upserted into ArangoDB db={arango_db}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
