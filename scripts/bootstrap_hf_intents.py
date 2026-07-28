#!/usr/bin/env python3
"""Bootstrap canvas-intent training data from HuggingFace datasets.

Mines CLINC150 and StackOverflow datasets, remaps to our 7-label schema:
  CODE, COMPARE, EXPLAIN, NAVIGATE, QUERY, SEARCH, VISUALIZE

Also generates compound intent examples (CODE+VISUALIZE).

Usage:
    python scripts/bootstrap_hf_intents.py --step clinc150
    python scripts/bootstrap_hf_intents.py --step stackoverflow
    python scripts/bootstrap_hf_intents.py --step compound
    python scripts/bootstrap_hf_intents.py --all
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

TRAINING_DIR = Path.home() / ".pi" / "assistant" / "training_data" / "canvas-intent"

# ── CLINC150 intent → our label mapping ──────────────────────────────────
# CLINC150 has 150 intents across 10 domains.  We cherry-pick intents that
# semantically match our 7-label schema and rephrase the utterances to
# our data-canvas domain.
CLINC_INTENT_MAP = {
    # EXPLAIN intents
    "definition": "EXPLAIN",
    "meaning_of_life": "EXPLAIN",
    "what_is_your_name": "EXPLAIN",
    "what_can_i_ask_you": "EXPLAIN",
    "tell_joke": "EXPLAIN",
    "fun_fact": "EXPLAIN",
    "who_made_you": "EXPLAIN",
    "what_are_your_hobbies": "EXPLAIN",
    "do_you_have_pets": "EXPLAIN",
    "are_you_a_bot": "EXPLAIN",
    "how_old_are_you": "EXPLAIN",
    # SEARCH intents
    "find_phone": "SEARCH",
    "restaurant_reviews": "SEARCH",
    "restaurant_suggestion": "SEARCH",
    "shopping_list": "SEARCH",
    "shopping_list_update": "SEARCH",
    # NAVIGATE intents
    "directions": "NAVIGATE",
    "traffic": "NAVIGATE",
    "gas": "NAVIGATE",
    "uber": "NAVIGATE",
    # QUERY intents
    "balance": "QUERY",
    "bill_balance": "QUERY",
    "bill_due": "QUERY",
    "credit_score": "QUERY",
    "credit_limit": "QUERY",
    "interest_rate": "QUERY",
    "exchange_rate": "QUERY",
    "measurement_conversion": "QUERY",
    "calories": "QUERY",
    "nutrition_info": "QUERY",
    "time": "QUERY",
    "timer": "QUERY",
    "date": "QUERY",
    "weather": "QUERY",
    "flight_status": "QUERY",
    "insurance": "QUERY",
    "taxes": "QUERY",
    "min_payment": "QUERY",
    "pay_bill": "QUERY",
    "spending_history": "QUERY",
    "transactions": "QUERY",
    "last_maintenance": "QUERY",
    "mpg": "QUERY",
    "oil_change_when": "QUERY",
    "tire_change": "QUERY",
    "tire_pressure": "QUERY",
    "gas_type": "QUERY",
    # COMPARE intents (few in CLINC, but these have comparison semantics)
    "todo_list_update": "COMPARE",  # tracking changes
}

# ── Domain rephrasing templates ──────────────────────────────────────────
# We rephrase generic CLINC utterances to our data-canvas domain to make
# them more useful for training.
DOMAIN_REPHRASE = {
    "EXPLAIN": [
        "explain {concept}",
        "what does {concept} mean",
        "how does {concept} work",
        "tell me about {concept}",
        "describe {concept}",
        "what is {concept}",
        "why does {concept} matter",
    ],
    "SEARCH": [
        "find documents about {topic}",
        "search for {topic}",
        "locate PDFs related to {topic}",
        "which documents mention {topic}",
        "look up {topic} in the datalake",
    ],
    "NAVIGATE": [
        "open {item}",
        "go to {item}",
        "show me {item}",
        "take me to {item}",
        "view {item}",
    ],
    "QUERY": [
        "how many {metric}",
        "what is the {metric}",
        "count of {metric}",
        "total {metric}",
        "average {metric}",
    ],
    "COMPARE": [
        "compare {a} vs {b}",
        "difference between {a} and {b}",
        "rank {metric} across documents",
        "which has higher {metric}",
    ],
}

# Domain vocabulary for rephrasing
DOMAIN_CONCEPTS = [
    "table extraction", "section alignment", "content coverage",
    "figure fidelity", "equation extraction", "data quality",
    "bridge attributes", "taxonomy tags", "persona scoring",
    "convergence tracker", "quality gate", "remediation",
    "ArangoDB sync", "pipeline preset", "S05 table extractor",
    "merge classifier", "vision model", "Camelot parameters",
]
DOMAIN_TOPICS = [
    "compliance", "DO-178C", "MIL-STD", "NASA standards",
    "table extraction failures", "section alignment issues",
    "high-fidelity PDFs", "multi-column layouts", "scanned documents",
]
DOMAIN_METRICS = [
    "documents extracted", "tables detected", "pass rate",
    "average score", "fail percentage", "WARN count",
    "persona verdicts", "remediation jobs", "extraction time",
]


def harvest_clinc150() -> list[dict]:
    """Pull CLINC150 from HF, remap to our labels, rephrase to domain."""
    from datasets import load_dataset

    print("Loading CLINC150 from HuggingFace...")
    ds = load_dataset("clinc/clinc_oos", "plus", trust_remote_code=True)

    # Get label names
    label_names = ds["train"].features["intent"].names

    results = []
    seen = set()

    for split in ["train", "validation"]:
        for example in ds[split]:
            intent_name = label_names[example["intent"]]
            our_label = CLINC_INTENT_MAP.get(intent_name)
            if not our_label:
                continue

            text = example["text"].strip()
            if text in seen or len(text) < 5:
                continue
            seen.add(text)

            results.append({
                "input": {"text": text},
                "output": {"prediction": our_label},
                "teacher_grade": our_label,
                "source": f"clinc150_{intent_name}",
            })

    # Also generate domain-rephrased versions
    rng = random.Random(42)
    rephrased = []
    for label, templates in DOMAIN_REPHRASE.items():
        vocab = {
            "EXPLAIN": DOMAIN_CONCEPTS,
            "SEARCH": DOMAIN_TOPICS,
            "NAVIGATE": ["the dashboard", "page 5", "the settings panel",
                         "document details", "the quality report",
                         "the extraction log", "the persona results"],
            "QUERY": DOMAIN_METRICS,
            "COMPARE": DOMAIN_METRICS,
        }.get(label, DOMAIN_CONCEPTS)

        for _ in range(20):  # 20 examples per label
            template = rng.choice(templates)
            if "{concept}" in template or "{topic}" in template or "{item}" in template:
                fill = rng.choice(vocab)
                text = template.replace("{concept}", fill).replace("{topic}", fill).replace("{item}", fill)
            elif "{metric}" in template:
                text = template.replace("{metric}", rng.choice(DOMAIN_METRICS))
            elif "{a}" in template and "{b}" in template:
                a, b = rng.sample(vocab, 2)
                text = template.replace("{a}", a).replace("{b}", b)
            else:
                text = template

            if text not in seen:
                seen.add(text)
                rephrased.append({
                    "input": {"text": text},
                    "output": {"prediction": label},
                    "teacher_grade": label,
                    "source": "clinc150_rephrased",
                })

    all_results = results + rephrased

    out_path = TRAINING_DIR / "labels_hf_clinc.jsonl"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in all_results:
            f.write(json.dumps(r) + "\n")

    dist = Counter(r["teacher_grade"] for r in all_results)
    print(f"Harvested {len(results)} CLINC150 + {len(rephrased)} rephrased → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return all_results


def harvest_stackoverflow() -> list[dict]:
    """Pull StackOverflow question titles from HF → CODE label.

    These are genuine code/technical questions that train the CODE intent.
    """
    from datasets import load_dataset

    print("Loading StackOverflow questions from HuggingFace...")
    try:
        ds = load_dataset("pacovaldez/stackoverflow-questions", split="train")
    except Exception as e:
        print(f"Could not load stackoverflow dataset: {e}")
        print("Falling back to synthetic CODE examples...")
        return _generate_code_from_templates()

    results = []
    seen = set()

    # Sample code-related questions
    rng = random.Random(42)
    indices = list(range(len(ds)))
    rng.shuffle(indices)

    for idx in indices[:2000]:  # sample 2000
        example = ds[idx]
        title = (example.get("title") or "").strip()
        if not title or len(title) < 15 or title in seen:
            continue
        # Filter for code/technical questions
        if not _is_code_question(title):
            continue
        seen.add(title)
        results.append({
            "input": {"text": title},
            "output": {"prediction": "CODE"},
            "teacher_grade": "CODE",
            "source": "stackoverflow_hf",
        })
        if len(results) >= 150:
            break

    out_path = TRAINING_DIR / "labels_hf_stackoverflow.jsonl"
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"Harvested {len(results)} CODE examples from StackOverflow → {out_path}")
    return results


def _is_code_question(text: str) -> bool:
    """Filter for questions that are genuinely about code/implementation."""
    code_signals = [
        r"\b(how to|how do I|how does)\b",
        r"\b(function|method|class|module|import|implement)\b",
        r"\b(error|exception|bug|fix|debug)\b",
        r"\b(python|javascript|java|rust|typescript|c\+\+|sql)\b",
        r"\b(api|endpoint|server|client|request|response)\b",
        r"\b(algorithm|data structure|pattern|architecture)\b",
        r"\b(library|package|dependency|framework)\b",
        r"\b(code|script|program|compile|runtime)\b",
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in code_signals)


def _generate_code_from_templates() -> list[dict]:
    """Fallback: generate CODE examples from domain templates."""
    rng = random.Random(42)
    templates = [
        "How does the {module} work?",
        "What function handles {task}?",
        "Explain the {module} implementation",
        "Where is {task} defined in the codebase?",
        "What class implements {task}?",
        "How does {module} process {noun}?",
        "Debug the {task} failure",
        "What does {module} return?",
        "How is {task} tested?",
        "What parameters does {module} accept?",
    ]
    modules = [
        "S05 table extractor", "S07 JSON assembler", "S10 ArangoDB exporter",
        "section builder", "figure extractor", "merge classifier",
        "prompt builder", "reliability module", "scoring module",
        "convergence tracker", "inline reviewer", "pipeline runner",
        "marker extractor", "vision model", "profile detector",
    ]
    tasks = [
        "table extraction", "section alignment", "content coverage scoring",
        "persona evaluation", "remediation", "quality gate",
        "document ingestion", "embedding generation", "taxonomy tagging",
        "hybrid search", "ArangoDB sync", "batch review",
    ]
    nouns = ["documents", "tables", "sections", "figures", "equations", "chunks"]

    results = []
    seen = set()
    for _ in range(150):
        t = rng.choice(templates)
        text = t.format(
            module=rng.choice(modules),
            task=rng.choice(tasks),
            noun=rng.choice(nouns),
        )
        if text not in seen:
            seen.add(text)
            results.append({
                "input": {"text": text},
                "output": {"prediction": "CODE"},
                "teacher_grade": "CODE",
                "source": "template_code",
            })
    return results


def generate_compound_examples() -> list[dict]:
    """Generate compound CODE+VISUALIZE examples.

    Common pattern: "analyze X in the codebase and visualize/chart/plot it"
    These should route to VISUALIZE (final intent determines rendering).
    """
    rng = random.Random(42)

    code_topics = [
        "extraction quality trends", "pipeline step durations",
        "table detection accuracy", "merge classifier confidence scores",
        "S05 strategy selection distribution", "persona scoring weights",
        "document processing times", "error rates by pipeline step",
        "convergence trajectory", "remediation job counts",
        "ArangoDB sync latency", "embedding generation throughput",
        "content coverage ratios", "section alignment scores",
        "figure extraction success rates", "taxonomy tag distribution",
        "CWE findings by category", "skill usage frequency",
        "memory recall precision", "batch review verdict distribution",
    ]

    compound_templates = [
        # CODE+VISUALIZE → VISUALIZE (rendering intent dominates)
        ("analyze {topic} and show me a chart", "VISUALIZE"),
        ("how does {topic} work? Plot the results", "VISUALIZE"),
        ("explain {topic} with a visualization", "VISUALIZE"),
        ("chart the {topic} from the codebase", "VISUALIZE"),
        ("visualize {topic} across pipeline runs", "VISUALIZE"),
        ("graph the {topic} over time", "VISUALIZE"),
        ("show me a heatmap of {topic}", "VISUALIZE"),
        ("plot {topic} by document type", "VISUALIZE"),
        ("create a bar chart of {topic}", "VISUALIZE"),
        ("trend line for {topic}", "VISUALIZE"),
        # CODE+VISUALIZE → CODE (analysis intent dominates, no viz keyword)
        ("analyze the {topic} implementation and explain patterns", "CODE"),
        ("investigate {topic} and describe what you find", "CODE"),
        ("review the {topic} code and summarize", "CODE"),
        # CODE+QUERY → QUERY (data question dominates)
        ("what is the average {topic}", "QUERY"),
        ("how many {topic} are there", "QUERY"),
        ("count the {topic}", "QUERY"),
        # CODE+SEARCH → SEARCH (find intent dominates)
        ("find all modules related to {topic}", "SEARCH"),
        ("search for {topic} in the pipeline code", "SEARCH"),
        ("which files handle {topic}", "SEARCH"),
    ]

    results = []
    seen = set()

    for _ in range(100):
        template, label = rng.choice(compound_templates)
        topic = rng.choice(code_topics)
        text = template.format(topic=topic)

        if text not in seen:
            seen.add(text)
            results.append({
                "input": {"text": text},
                "output": {"prediction": label},
                "teacher_grade": label,
                "source": "compound_synthetic",
            })

    out_path = TRAINING_DIR / "labels_hf_compound.jsonl"
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    dist = Counter(r["teacher_grade"] for r in results)
    print(f"Generated {len(results)} compound examples → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return results


def main():
    """Bootstrap HuggingFace datasets via specified steps."""
    import argparse
    parser = argparse.ArgumentParser(description="Bootstrap from HuggingFace datasets")
    parser.add_argument("--step", choices=["clinc150", "stackoverflow", "compound"])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        harvest_clinc150()
        harvest_stackoverflow()
        generate_compound_examples()
    elif args.step == "clinc150":
        harvest_clinc150()
    elif args.step == "stackoverflow":
        harvest_stackoverflow()
    elif args.step == "compound":
        generate_compound_examples()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
