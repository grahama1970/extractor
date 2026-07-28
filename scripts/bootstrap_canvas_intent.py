#!/usr/bin/env python3
"""Bootstrap canvas-intent training data from datalake scenarios + scillm teacher.

Step 1: Auto-map 210 datalake_query_scenarios.json → canvas-intent labels
Step 2: Extract clean queries from ~/.pi/sessions/ask/*.jsonl
Step 3: Bulk-label ambiguous queries via scillm (DeepSeek V3.2)
Step 4: Merge all sources into training JSONL

Usage:
    python scripts/bootstrap_canvas_intent.py --step map-scenarios
    python scripts/bootstrap_canvas_intent.py --step extract-ask
    python scripts/bootstrap_canvas_intent.py --step label-with-scillm
    python scripts/bootstrap_canvas_intent.py --step merge
    python scripts/bootstrap_canvas_intent.py --all
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCENARIOS_PATH = Path("scenarios/datalake_query_scenarios.json")
ASK_SESSIONS_DIR = Path.home() / ".pi" / "sessions" / "ask"
TRAINING_DIR = Path.home() / ".pi" / "assistant" / "training_data" / "canvas-intent"
SCILLM_DIR = Path.home() / "workspace/experiments/pi-mono/.pi/skills/scillm"

# Level → canvas-intent mapping (deterministic for clear cases)
LEVEL_MAP = {
    "discovery": "SEARCH",
    "table_ops": "QUERY",
    "cross_doc": "COMPARE",
    "requirements": "QUERY",
    "quality": "QUERY",
    "corrective": "NAVIGATE",
    "learning": "EXPLAIN",
    "code": "CODE",
    "pipeline": "CODE",
    "architecture": "CODE",
}

# Override patterns — some queries in a level are actually a different intent
# CODE checked before EXPLAIN — "how does the pipeline work" is CODE, not EXPLAIN
OVERRIDE_PATTERNS = [
    (r"\b(show me|display|chart|graph|plot|visualize|trend|heatmap|pie chart|bar chart|timeline)\b", "VISUALIZE"),
    (r"\b(compare|versus|vs|difference between|rank|which.*(?:most|highest|lowest|best|worst))\b", "COMPARE"),
    (r"\b(pipeline|step|stage|s0[0-9]|s1[0-4]|module|function|class|handler|endpoint|extractor|\.py)\b", "CODE"),
    (r"\b(codebase|source code|implementation|architecture)\b.{0,30}\b(work|do|implement|process)\b", "CODE"),
    (r"\b(merge.?classifier|table.?extractor|section.?builder|figure.?extractor)\b", "CODE"),
    (r"\b(explain|what does|why|describe|tell me about|how does|what is the difference)\b", "EXPLAIN"),
    (r"\b(open|go to|navigate|review the|show me page)\b.*\b(document|pdf|file|page|report)\b", "NAVIGATE"),
]


def map_scenarios() -> list[dict]:
    """Step 1: Map datalake scenarios to canvas-intent labels."""
    with open(SCENARIOS_PATH) as f:
        data = json.load(f)

    results = []
    for s in data["scenarios"]:
        query = s["query"]
        level = s["level"]

        # Start with level-based mapping
        label = LEVEL_MAP.get(level, "QUERY")

        # Apply override patterns (more specific wins)
        q_lower = query.lower()
        for pattern, override_label in OVERRIDE_PATTERNS:
            if re.search(pattern, q_lower):
                label = override_label
                break

        entry = {
            "input": {"text": query},
            "output": {"prediction": label, "confidence": 0.85},
            "teacher_grade": label,
            "source": "scenario_map",
            "meta": {"scenario_id": s["id"], "level": level, "persona": s["persona"]},
        }
        results.append(entry)

    # Write output
    out_path = TRAINING_DIR / "labels_scenarios.jsonl"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Report class distribution
    from collections import Counter
    dist = Counter(r["teacher_grade"] for r in results)
    print(f"Mapped {len(results)} scenarios → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return results


def extract_ask_queries() -> list[dict]:
    """Step 2: Extract clean single-intent queries from /ask sessions."""
    if not ASK_SESSIONS_DIR.exists():
        print(f"No ask sessions at {ASK_SESSIONS_DIR}")
        return []

    queries = []
    seen = set()

    for session_file in sorted(ASK_SESSIONS_DIR.glob("*.jsonl")):
        for line in session_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Sessions have {"messages": [{"from": "user", "message": "..."}]}
            messages = entry.get("messages", [])
            for msg in messages:
                if msg.get("from") != "user":
                    continue
                query = msg.get("message", "")
                if not isinstance(query, str):
                    continue

                # Clean up persona prefixes like "[margaret_chen] Asked: ..."
                query = re.sub(r'^\[?\w+[\]_]\s*Asked:\s*', '', query).strip()
                # Also handle "What other documents discuss the same topic as: [persona] Asked: X"
                # Extract the inner query if it's a wrapper
                inner_match = re.search(r'(?:same topic as|similar to|related to):\s*(?:\[[\w_]+\]\s*Asked:\s*)?(.*)', query)
                if inner_match:
                    query = inner_match.group(1).strip()

                if len(query) < 10 or len(query) > 300:
                    continue
                if query in seen:
                    continue
                # Skip remaining noise
                if any(noise in query for noise in ["```", "{", "}", "Error:", "FAIL", "traceback"]):
                    continue

                seen.add(query)
                queries.append({"input": {"text": query}, "source": "ask_session"})

    # Write unlabeled for scillm
    out_path = TRAINING_DIR / "unlabeled_ask.jsonl"
    with open(out_path, "w") as f:
        for q in queries:
            f.write(json.dumps(q) + "\n")

    print(f"Extracted {len(queries)} clean queries → {out_path}")
    return queries


def label_with_scillm(max_queries: int = 600) -> list[dict]:
    """Step 3: Bulk-label queries using scillm (DeepSeek V3.2)."""
    unlabeled_path = TRAINING_DIR / "unlabeled_ask.jsonl"
    if not unlabeled_path.exists():
        print("No unlabeled queries. Run --step extract-ask first.")
        return []

    queries = []
    for line in unlabeled_path.read_text().splitlines():
        if line.strip():
            queries.append(json.loads(line))

    if len(queries) > max_queries:
        queries = queries[:max_queries]

    system_prompt = """You are an intent classifier for a voice-activated data visualization canvas.

Classify the user query into exactly ONE of these 7 intents:
- CODE: User asks about codebase, pipeline implementation, functions, modules, debugging, or architecture
- VISUALIZE: User wants a chart, graph, plot, trend line, heatmap, or visual representation
- QUERY: User wants a numeric answer, count, percentage, statistic, or data lookup
- SEARCH: User wants to find/locate specific documents, content, or entities
- COMPARE: User wants to compare, rank, or diff items across documents or dimensions
- NAVIGATE: User wants to open, go to, or view a specific document/page/section
- EXPLAIN: User wants an explanation of how something works, why something happened, or what a term means

Note: If query uses slash-command syntax (e.g. "/assess X"), that is NOT a classification task — it's direct skill invocation. Only classify natural language queries without slash commands.

Respond as JSON: {"label": "CLASS", "confidence": 0.0-1.0}"""

    # Build prompts JSONL for scillm batch
    # scillm batch reads {"prompt": "..."} per line — embed system prompt inline
    prompts_path = TRAINING_DIR / "scillm_prompts.jsonl"
    with open(prompts_path, "w") as f:
        for i, q in enumerate(queries):
            combined = f"{system_prompt}\n\nClassify this query: \"{q['input']['text']}\""
            prompt = {"prompt": combined}
            f.write(json.dumps(prompt) + "\n")

    print(f"Prepared {len(queries)} prompts → {prompts_path}")

    # Call scillm batch (run.sh batch → batch.py, then "batch" subcommand)
    scillm_run = SCILLM_DIR / "run.sh"
    if not scillm_run.exists():
        print(f"scillm not found at {scillm_run}. Label manually or copy prompts.")
        return []

    output_path = TRAINING_DIR / "scillm_output.jsonl"
    cmd = [
        str(scillm_run), "batch", "batch",
        "--input", str(prompts_path),
        "--output", str(output_path),
        "--json",
        "--concurrency", "6",
    ]
    print(f"Running: {' '.join(cmd)}")
    env = {**os.environ}
    env.pop("VIRTUAL_ENV", None)  # avoid venv conflict with scillm's uv
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=env)
    if result.returncode != 0:
        print(f"scillm batch failed: {result.stderr[:500]}")
        return []

    # Parse scillm output and create labeled entries
    labeled = []
    if output_path.exists():
        for i, line in enumerate(output_path.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Extract label from response
            label_data = _parse_label(resp)
            if not label_data or i >= len(queries):
                continue

            entry = {
                "input": queries[i]["input"],
                "output": {"prediction": label_data["label"], "confidence": label_data.get("confidence", 0.8)},
                "teacher_grade": label_data["label"],
                "source": "scillm_teacher",
            }
            labeled.append(entry)

    out_path = TRAINING_DIR / "labels_scillm.jsonl"
    with open(out_path, "w") as f:
        for e in labeled:
            f.write(json.dumps(e) + "\n")

    from collections import Counter
    dist = Counter(e["teacher_grade"] for e in labeled)
    print(f"Labeled {len(labeled)} queries via scillm → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return labeled


def _parse_label(resp: dict) -> Optional[dict]:
    """Extract label from scillm response (may be nested)."""
    VALID = {"VISUALIZE", "QUERY", "SEARCH", "COMPARE", "NAVIGATE", "EXPLAIN", "CODE"}

    # Try direct fields
    text = resp.get("text") or resp.get("content") or resp.get("response") or ""
    if isinstance(text, dict):
        label = text.get("label", "")
        if label in VALID:
            return {"label": label, "confidence": text.get("confidence", 0.8)}

    # Try parsing JSON from text
    if isinstance(text, str):
        # Find JSON in response
        match = re.search(r'\{[^}]+\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
                label = parsed.get("label", "")
                if label in VALID:
                    return {"label": label, "confidence": parsed.get("confidence", 0.8)}
            except json.JSONDecodeError:
                pass

        # Fallback: look for class name in text
        for cls in VALID:
            if cls in text:
                return {"label": cls, "confidence": 0.7}

    return None



def merge_all():
    """Step 4: Merge all label sources into one training file."""
    all_entries = []
    seen_texts = set()

    for label_file in sorted(TRAINING_DIR.glob("labels_*.jsonl")):
        if label_file.name == "labels_merged.jsonl":
            continue
        for line in label_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = entry.get("input", {}).get("text", "")
            if text and text not in seen_texts:
                seen_texts.add(text)
                all_entries.append(entry)

    out_path = TRAINING_DIR / "labels_merged.jsonl"
    with open(out_path, "w") as f:
        for e in all_entries:
            f.write(json.dumps(e) + "\n")

    from collections import Counter
    dist = Counter(e.get("teacher_grade", e.get("output", {}).get("prediction", "UNKNOWN")) for e in all_entries)
    print(f"Merged {len(all_entries)} unique labels → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    print(f"\nTo retrain: cd pi-mono/.pi/skills/assistant && python3 train_classifiers.py --task canvas-intent")


def main():
    """Bootstrap canvas-intent training data."""
    import argparse
    parser = argparse.ArgumentParser(description="Bootstrap canvas-intent training data")
    parser.add_argument("--step", choices=["map-scenarios", "extract-ask", "label-with-scillm", "merge"])
    parser.add_argument("--all", action="store_true", help="Run all steps")
    args = parser.parse_args()

    if args.all:
        map_scenarios()
        extract_ask_queries()
        label_with_scillm()
        merge_all()
    elif args.step == "map-scenarios":
        map_scenarios()
    elif args.step == "extract-ask":
        extract_ask_queries()
    elif args.step == "label-with-scillm":
        label_with_scillm()
    elif args.step == "merge":
        merge_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
