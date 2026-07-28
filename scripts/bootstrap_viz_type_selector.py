#!/usr/bin/env python3
"""Bootstrap viz-type-selector training data from d3_catalog keywords + scillm teacher.

Step 1: Generate synthetic query→viz_type pairs from d3_catalog.py keywords
Step 2: Generate data-shape-aware pairs (query + shape → viz_type)
Step 3: Bulk-label ambiguous pairs via scillm (DeepSeek V3.2)
Step 4: Merge all sources into training JSONL

Usage:
    python scripts/bootstrap_viz_type_selector.py --step generate-from-keywords
    python scripts/bootstrap_viz_type_selector.py --step generate-from-shapes
    python scripts/bootstrap_viz_type_selector.py --step label-with-scillm
    python scripts/bootstrap_viz_type_selector.py --step merge
    python scripts/bootstrap_viz_type_selector.py --all
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add d3_catalog to path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PI_MONO = _PROJECT_ROOT.parent / "pi-mono"
_SKILLS_DIR = _PI_MONO / ".pi" / "skills"
sys.path.insert(0, str(_SKILLS_DIR / "create-figure"))

from d3_catalog import (
    D3_VIZ_CATALOG,
    DataShape,
    RenderBackend,
    get_implemented_viz_types,
)

TRAINING_DIR = Path.home() / ".pi" / "assistant" / "training_data" / "viz-type-selector"
SCILLM_DIR = _PI_MONO / ".pi" / "skills" / "scillm"

# Domain nouns relevant to our datalake corpus
DOMAIN_NOUNS = [
    "compliance scores", "extraction quality", "table fidelity",
    "persona verdicts", "section alignment", "equation fidelity",
    "data quality", "content coverage", "ordering accuracy",
    "figure fidelity", "pipeline metrics", "convergence data",
    "document scores", "quality dimensions", "extraction results",
    "PDF processing times", "error rates", "pass rates",
    "fail rates", "warn rates", "grade distributions",
    "domain categories", "table counts", "formula counts",
    "page counts", "file sizes", "processing durations",
    "remediation actions", "escalation events", "taxonomy tags",
    "bridge attributes", "similarity scores", "embedding distances",
]

ENTITY_PAIRS = [
    ("Margaret", "Jennifer"), ("PASS", "FAIL"), ("lattice", "stream"),
    ("S04", "S05"), ("defense specs", "NASA standards"),
    ("tables", "figures"), ("sections", "equations"),
    ("before remediation", "after remediation"),
    ("week 1", "week 4"), ("batch A", "batch B"),
]

# Query templates per data shape
TEMPLATES_CATEGORICAL = [
    "show me a {keyword} of {noun}",
    "{keyword} for {noun}",
    "display {noun} as a {keyword}",
    "create a {keyword} showing {noun}",
    "{keyword} breakdown of {noun}",
    "what's the {keyword} for {noun}",
]

TEMPLATES_TIME_SERIES = [
    "show {noun} over time as a {keyword}",
    "{keyword} of {noun} trend",
    "plot {noun} {keyword} over the last month",
    "{keyword} showing {noun} trajectory",
    "how has {noun} changed — {keyword}",
]

TEMPLATES_COMPARISON = [
    "compare {entity_a} vs {entity_b} {noun} using a {keyword}",
    "{keyword} of {entity_a} and {entity_b} {noun}",
    "plot {noun} comparing {entity_a} versus {entity_b} as a {keyword}",
    "show {entity_a} vs {entity_b} on a {keyword}",
]

TEMPLATES_DISTRIBUTION = [
    "show the distribution of {noun} as a {keyword}",
    "{keyword} of {noun} spread",
    "what's the {keyword} for {noun} values",
    "{keyword} showing {noun} frequency",
]

TEMPLATES_HIERARCHY = [
    "show the {keyword} of {noun}",
    "{keyword} of document taxonomy",
    "display {noun} {keyword}",
    "{keyword} breakdown of the hierarchy",
]

TEMPLATES_MULTIVARIATE = [
    "show {noun} across all dimensions as a {keyword}",
    "{keyword} of {noun} multi-dimensional profile",
    "display {noun} on a {keyword}",
    "{keyword} comparing all quality metrics",
]

TEMPLATES_GENERIC = [
    "show me {noun}",
    "plot {noun}",
    "visualize {noun}",
    "display {noun}",
    "chart of {noun}",
    "graph {noun}",
    "what does the {noun} look like",
    "give me a view of {noun}",
]

# Map DataShape → template lists
SHAPE_TEMPLATES = {
    DataShape.CATEGORICAL: TEMPLATES_CATEGORICAL,
    DataShape.TIME_SERIES: TEMPLATES_TIME_SERIES,
    DataShape.BIVARIATE: TEMPLATES_COMPARISON,
    DataShape.MULTIVARIATE: TEMPLATES_MULTIVARIATE,
    DataShape.HIERARCHICAL: TEMPLATES_HIERARCHY,
    DataShape.DISTRIBUTION: TEMPLATES_DISTRIBUTION,
    DataShape.NETWORK: TEMPLATES_HIERARCHY,
    DataShape.FLOW: TEMPLATES_CATEGORICAL,
    DataShape.MATRIX: TEMPLATES_MULTIVARIATE,
    DataShape.GEOGRAPHIC: TEMPLATES_CATEGORICAL,
    DataShape.TABULAR: TEMPLATES_GENERIC,
    DataShape.TEXT: TEMPLATES_GENERIC,
}


def generate_from_keywords() -> list[dict]:
    """Step 1: Generate synthetic query→viz_type from d3_catalog keywords."""
    results = []
    seen = set()

    for name, viz in D3_VIZ_CATALOG.items():
        # Only train on implemented types (can expand later)
        if viz.backend == RenderBackend.NOT_YET:
            continue

        for keyword in viz.keywords:
            # Get templates for this viz's primary data shape
            primary_shape = viz.data_shapes[0] if viz.data_shapes else DataShape.CATEGORICAL
            templates = SHAPE_TEMPLATES.get(primary_shape, TEMPLATES_GENERIC)

            for template in templates:
                for noun in random.sample(DOMAIN_NOUNS, min(3, len(DOMAIN_NOUNS))):
                    if "{entity_a}" in template:
                        for ea, eb in random.sample(ENTITY_PAIRS, min(2, len(ENTITY_PAIRS))):
                            query = template.format(
                                keyword=keyword, noun=noun,
                                entity_a=ea, entity_b=eb,
                            )
                            if query not in seen:
                                seen.add(query)
                                results.append(_make_entry(query, name, "keyword_template", 0.9))
                    else:
                        query = template.format(keyword=keyword, noun=noun)
                        if query not in seen:
                            seen.add(query)
                            results.append(_make_entry(query, name, "keyword_template", 0.9))

    # Add generic queries (no keyword hint) — these are harder
    for noun in DOMAIN_NOUNS:
        for template in TEMPLATES_GENERIC:
            query = template.format(noun=noun)
            if query not in seen:
                seen.add(query)
                results.append(_make_entry(query, None, "generic_unlabeled", 0.0))

    # Shuffle and cap
    random.shuffle(results)

    # Write output
    out_path = TRAINING_DIR / "labels_keywords.jsonl"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)

    # Split labeled vs unlabeled
    labeled = [r for r in results if r["teacher_grade"] is not None]
    unlabeled = [r for r in results if r["teacher_grade"] is None]

    with open(out_path, "w") as f:
        for r in labeled:
            f.write(json.dumps(r) + "\n")

    unlabeled_path = TRAINING_DIR / "unlabeled_generic.jsonl"
    with open(unlabeled_path, "w") as f:
        for r in unlabeled:
            f.write(json.dumps(r) + "\n")

    from collections import Counter
    dist = Counter(r["teacher_grade"] for r in labeled)
    print(f"Generated {len(labeled)} keyword-labeled + {len(unlabeled)} unlabeled → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return results


def generate_from_shapes() -> list[dict]:
    """Step 2: Generate data-shape-aware pairs with explicit shape metadata."""
    results = []
    seen = set()

    for name, viz in D3_VIZ_CATALOG.items():
        if viz.backend == RenderBackend.NOT_YET:
            continue

        for shape in viz.data_shapes:
            # Create sample data shape descriptions
            data_shapes = _sample_data_shapes(shape, viz)

            for ds in data_shapes:
                # Queries that describe the data without mentioning chart type
                data_queries = [
                    f"I have {ds['description']}, what's the best way to show it",
                    f"best visualization for {ds['description']}",
                    f"how should I display {ds['description']}",
                ]
                for query in data_queries:
                    if query not in seen:
                        seen.add(query)
                        entry = _make_entry(query, name, "shape_template", 0.85)
                        entry["meta"]["data_shape"] = ds
                        results.append(entry)

    random.shuffle(results)

    out_path = TRAINING_DIR / "labels_shapes.jsonl"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    from collections import Counter
    dist = Counter(r["teacher_grade"] for r in results)
    print(f"Generated {len(results)} shape-labeled entries → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return results


def _sample_data_shapes(shape: DataShape, viz) -> list[dict]:
    """Generate realistic data shape descriptions for a given DataShape."""
    shapes = []

    if shape == DataShape.CATEGORICAL:
        for n in (3, 5, 10, 20):
            shapes.append({
                "row_count": n, "col_count": 2,
                "has_time_axis": False, "nested": False,
                "description": f"{n} categories with values",
            })
    elif shape == DataShape.TIME_SERIES:
        for n in (10, 30, 100):
            shapes.append({
                "row_count": n, "col_count": 2,
                "has_time_axis": True, "nested": False,
                "description": f"{n} time-series data points",
            })
    elif shape == DataShape.BIVARIATE:
        for n in (10, 50, 200):
            shapes.append({
                "row_count": n, "col_count": 2,
                "has_time_axis": False, "nested": False,
                "description": f"{n} x-y data points",
            })
    elif shape == DataShape.MULTIVARIATE:
        for n, c in ((5, 4), (10, 6), (20, 8)):
            shapes.append({
                "row_count": n, "col_count": c,
                "has_time_axis": False, "nested": False,
                "description": f"{n} rows with {c} numeric dimensions",
            })
    elif shape == DataShape.HIERARCHICAL:
        for n in (10, 30, 100):
            shapes.append({
                "row_count": n, "col_count": 3,
                "has_time_axis": False, "nested": True,
                "description": f"hierarchical data with {n} nodes",
            })
    elif shape == DataShape.DISTRIBUTION:
        for n in (20, 100, 500):
            shapes.append({
                "row_count": n, "col_count": 1,
                "has_time_axis": False, "nested": False,
                "description": f"{n} numeric values to show distribution",
            })
    elif shape == DataShape.NETWORK:
        for n in (5, 20, 50):
            shapes.append({
                "row_count": n, "col_count": 2,
                "has_time_axis": False, "nested": False,
                "description": f"network with {n} nodes and edges",
            })
    elif shape == DataShape.FLOW:
        for n in (3, 8, 15):
            shapes.append({
                "row_count": n, "col_count": 3,
                "has_time_axis": False, "nested": False,
                "description": f"{n} source-target-value flow records",
            })
    elif shape == DataShape.MATRIX:
        for n in (4, 8, 16):
            shapes.append({
                "row_count": n, "col_count": n,
                "has_time_axis": False, "nested": False,
                "description": f"{n}x{n} matrix of values",
            })
    else:
        shapes.append({
            "row_count": 10, "col_count": 3,
            "has_time_axis": False, "nested": False,
            "description": "tabular data with 10 rows",
        })

    return shapes


def label_with_scillm(max_queries: int = 800) -> list[dict]:
    """Step 3: Bulk-label unlabeled/ambiguous queries via scillm."""
    unlabeled_path = TRAINING_DIR / "unlabeled_generic.jsonl"
    if not unlabeled_path.exists():
        print("No unlabeled queries. Run --step generate-from-keywords first.")
        return []

    queries = []
    for line in unlabeled_path.read_text().splitlines():
        if line.strip():
            queries.append(json.loads(line))

    if len(queries) > max_queries:
        queries = queries[:max_queries]

    # Build the list of valid viz types (only implemented ones)
    implemented = get_implemented_viz_types()
    type_list = "\n".join(f"- {v.name}: {v.description}" for v in implemented)

    system_prompt = f"""You are a visualization type selector for a data canvas.

Given a user query about data, select the BEST visualization type from this list:

{type_list}

Consider:
1. What kind of data the user likely has (categorical, time series, distribution, etc.)
2. What insight they want (comparison, trend, composition, distribution, relationship)
3. Whether the visualization type can handle the implied data shape

Respond as JSON: {{"viz_type": "type_name", "confidence": 0.0-1.0, "reason": "brief explanation"}}"""

    prompts_path = TRAINING_DIR / "scillm_prompts.jsonl"
    with open(prompts_path, "w") as f:
        for q in queries:
            text = q.get("input", {}).get("text", "")
            combined = f"{system_prompt}\n\nSelect viz type for: \"{text}\""
            f.write(json.dumps({"prompt": combined}) + "\n")

    print(f"Prepared {len(queries)} prompts → {prompts_path}")

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
    env.pop("VIRTUAL_ENV", None)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=env)
    if result.returncode != 0:
        print(f"scillm batch failed: {result.stderr[:500]}")
        return []

    # Parse output
    labeled = []
    valid_types = {v.name for v in implemented}

    if output_path.exists():
        for i, line in enumerate(output_path.read_text().splitlines()):
            if not line.strip() or i >= len(queries):
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue

            label_data = _parse_viz_label(resp, valid_types)
            if not label_data:
                continue

            entry = {
                "input": queries[i]["input"],
                "output": {"prediction": label_data["viz_type"], "confidence": label_data.get("confidence", 0.8)},
                "teacher_grade": label_data["viz_type"],
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


def _parse_viz_label(resp: dict, valid_types: set[str]) -> Optional[dict]:
    """Extract viz_type from scillm response."""
    text = resp.get("text") or resp.get("content") or resp.get("response") or ""
    if isinstance(text, dict):
        vt = text.get("viz_type", "")
        if vt in valid_types:
            return {"viz_type": vt, "confidence": text.get("confidence", 0.8)}

    if isinstance(text, str):
        match = re.search(r'\{[^}]+\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
                vt = parsed.get("viz_type", "")
                if vt in valid_types:
                    return {"viz_type": vt, "confidence": parsed.get("confidence", 0.8)}
            except json.JSONDecodeError:
                pass

        # Fallback: look for type name in text
        for vt in valid_types:
            if vt in text.lower():
                return {"viz_type": vt, "confidence": 0.7}

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
            # Skip entries without a label
            grade = entry.get("teacher_grade")
            if not grade:
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
    dist = Counter(e.get("teacher_grade", "UNKNOWN") for e in all_entries)
    print(f"Merged {len(all_entries)} unique labels → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    print(f"\nTo train: /classifier-lab text-benchmark "
          f"--labels-jsonl {out_path} "
          f"--backbones 'sentence-transformers/all-MiniLM-L6-v2'")


def _make_entry(query: str, viz_type: Optional[str], source: str, confidence: float) -> dict:
    """Build a dictionary entry from query, visualization type, source, and confidence."""
    return {
        "input": {"text": query},
        "output": {"prediction": viz_type, "confidence": confidence} if viz_type else {},
        "teacher_grade": viz_type,
        "source": source,
        "meta": {},
    }


def generate_natural_queries() -> list[dict]:
    """Step 5: Generate diverse natural-language queries that don't follow templates.

    These cover real-world phrasing patterns:
    - Conversational ("hey can you show me...")
    - Domain-specific jargon ("pull up the DO-178C compliance matrix")
    - Implicit viz type (user describes what they want to see, not the chart type)
    - Multi-intent borderline cases
    """
    results = []
    seen = set()

    # Natural query → viz_type pairs (hand-curated for quality)
    NATURAL_PAIRS = [
        # Bar variants
        ("what are the top 10 most common extraction failures", "bar"),
        ("rank the documents by quality score", "hbar"),
        ("how do the different pipeline strategies compare", "grouped_bar"),
        ("show positive vs negative score changes after remediation", "diverging_bar"),
        ("how many documents in each quality grade", "bar"),
        ("which categories have the most documents", "bar"),
        ("breakdown of document types by domain", "stacked_bar"),

        # Line/time
        ("how has extraction quality improved over the past month", "line"),
        ("plot the convergence curve for the last 500 extractions", "line"),
        ("overlay Margaret and Jennifer scores over time", "multi_line"),
        ("give me a quick inline trend of pass rates", "sparkline"),
        ("show the daily processing throughput", "area"),
        ("visualize how different quality dimensions stack up over time", "stacked_area"),
        ("plot the slope between week 1 and week 4 scores", "slope"),

        # Distribution
        ("what's the spread of content_coverage scores", "histogram"),
        ("box plot of table_fidelity by domain", "box_plot"),

        # Scatter/bubble
        ("plot table count vs quality score for each document", "scatter"),
        ("scatter of page count against processing time", "scatter"),
        ("show document size vs extraction time with error count as bubble size", "bubble"),

        # Hierarchy/flow
        ("show the document taxonomy as a tree", "treemap"),
        ("sunburst of bridge_tags → domain → document type", "sunburst"),
        ("flow diagram of pipeline stages and where documents fail", "sankey"),
        ("how do documents flow from extraction through scoring to memory", "sankey"),

        # Network
        ("show the relationship graph between documents and shared taxonomy", "force_graph"),

        # Radial/comparison
        ("radar chart comparing Margaret vs Jennifer scoring profiles", "radar"),
        ("spider chart of all 7 quality dimensions for this document", "radar"),
        ("compare the 5 quality metrics side by side on a radar", "radar"),
        ("parallel coordinates of all quality dimensions for top-50 documents", "parallel_coords"),

        # Matrix
        ("heatmap of persona agreement rates across quality dimensions", "heatmap"),
        ("confusion matrix of predicted vs actual quality grades", "confusion_matrix"),

        # KPI/simple
        ("what's the current overall extraction quality score", "gauge"),
        ("show me the pass rate as a big number", "gauge"),
        ("how close are we to the 0.95 target", "gauge"),
        ("percentage of documents that pass both personas", "gauge"),

        # Specialty
        ("show the ROC curve for the merge classifier", "roc_curve"),
        ("funnel of documents from extraction → scoring → pass → memory", "funnel"),
        ("give me a ratio of pass/warn/fail as a pie chart", "pie"),
        ("donut showing the proportion of each domain category", "donut"),
        ("show all the data in a table", "table"),
        ("give me a dot plot of scores per document", "dot_plot"),
        ("waterfall of how each quality dimension contributes to the total", "waterfall"),

        # Ambiguous — user describes insight, not chart
        ("I want to see which documents improved the most after remediation", "diverging_bar"),
        ("which pipeline step takes the longest", "bar"),
        ("are there any outliers in processing time", "box_plot"),
        ("how concentrated are the scores around the mean", "histogram"),
        ("is there a correlation between page count and quality score", "scatter"),
        ("show me everything about this document's quality profile", "radar"),
        ("what does the pipeline flow look like end to end", "sankey"),
        ("let me see the numbers in a grid", "table"),
    ]

    for query, viz_type in NATURAL_PAIRS:
        if query not in seen:
            seen.add(query)
            results.append(_make_entry(query, viz_type, "natural_curated", 0.95))

    # Also generate light variants (different phrasing of same intent)
    PREFIXES = ["hey ", "can you ", "please ", "I need a ", "pull up ", ""]
    SUFFIXES = ["", " please", " for me", " real quick", " — make it big"]

    for query, viz_type in NATURAL_PAIRS[:30]:  # Limit variants
        prefix = random.choice(PREFIXES)
        suffix = random.choice(SUFFIXES)
        variant = f"{prefix}{query}{suffix}"
        if variant not in seen:
            seen.add(variant)
            results.append(_make_entry(variant, viz_type, "natural_variant", 0.9))

    out_path = TRAINING_DIR / "labels_natural.jsonl"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    from collections import Counter
    dist = Counter(r["teacher_grade"] for r in results)
    print(f"Generated {len(results)} natural queries → {out_path}")
    for cls, count in sorted(dist.items()):
        print(f"  {cls}: {count}")
    return results


def generate_adversarial() -> list[dict]:
    """Step 6: Generate adversarial examples that test classifier boundaries.

    Covers:
    - Chart type mentioned but wrong for the data ("pie chart of time series")
    - Multiple chart types mentioned ("bar or line chart")
    - Negations ("don't show me a pie chart")
    - Domain jargon that could confuse
    """
    results = []
    seen = set()

    # Queries where the correct answer contradicts a naive keyword match
    ADVERSARIAL_PAIRS = [
        # Mentions "pie" but data is temporal → line is better
        ("show me a pie chart of scores over time", "pie"),  # user explicitly asked
        # Mentions multiple — pick the first explicit one
        ("bar chart or maybe a line chart of quality scores", "bar"),
        # Generic insight queries → correct viz depends on data shape
        ("what's trending in the extraction metrics", "line"),
        ("summarize the quality data visually", "bar"),
        ("give me an overview of everything", "table"),
        # Jargon that could confuse
        ("pull up the DO-178C compliance matrix", "table"),
        ("show the SPARTA taxonomy bridge attributes", "radar"),
        ("Margaret's scoring breakdown for MIL-STD-1553", "radar"),
        ("Jennifer's defense document verdict distribution", "bar"),
        # Very short queries
        ("scores", "bar"),
        ("convergence", "line"),
        ("taxonomy", "treemap"),
        ("comparison", "grouped_bar"),
        # Very long queries
        (
            "I want to understand how the extraction quality has changed over the "
            "last two weeks, specifically for defense specification documents that "
            "contain tables, and compare lattice vs stream strategies",
            "multi_line",
        ),
        # Edge cases
        ("show nothing", "text"),
        ("just the raw data please", "table"),
        ("a simple number — what's the pass rate", "gauge"),
    ]

    for query, viz_type in ADVERSARIAL_PAIRS:
        if query not in seen:
            seen.add(query)
            results.append(_make_entry(query, viz_type, "adversarial", 0.85))

    out_path = TRAINING_DIR / "labels_adversarial.jsonl"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"Generated {len(results)} adversarial examples → {out_path}")
    return results


def train_setfit():
    """Step 7: Train SetFit classifier from merged training data.

    Calls /classifier-lab or trains directly using SetFit library.
    """
    merged_path = TRAINING_DIR / "labels_merged.jsonl"
    if not merged_path.exists():
        print("No merged data. Run --step merge first.")
        return

    # Check for classifier-lab
    classifier_lab = _SKILLS_DIR / "classifier-lab" / "run.sh"
    if classifier_lab.exists():
        cmd = [
            str(classifier_lab), "text-benchmark",
            "--labels-jsonl", str(merged_path),
            "--backbones", "sentence-transformers/all-MiniLM-L6-v2",
            "--task", "viz-type-selector",
            "--output-dir", str(Path.home() / ".pi" / "models" / "classifiers" / "viz_type_selector_setfit"),
        ]
        print(f"Running: {' '.join(cmd)}")
        env = {**os.environ}
        env.pop("VIRTUAL_ENV", None)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
        print(result.stdout[-2000:] if result.stdout else "")
        if result.returncode != 0:
            print(f"Training failed: {result.stderr[:500]}")
    else:
        print(f"classifier-lab not found at {classifier_lab}")
        print("Manual training: pip install setfit && python -c 'from setfit import ...'")


def main():
    """Execute specified step for bootstrapping viz-type-selector training data."""
    import argparse
    parser = argparse.ArgumentParser(description="Bootstrap viz-type-selector training data")
    parser.add_argument("--step", choices=[
        "generate-from-keywords", "generate-from-shapes",
        "generate-natural", "generate-adversarial",
        "label-with-scillm", "merge", "train-setfit",
    ])
    parser.add_argument("--all", action="store_true", help="Run all steps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)

    if args.all:
        generate_from_keywords()
        generate_from_shapes()
        generate_natural_queries()
        generate_adversarial()
        label_with_scillm()
        merge_all()
    elif args.step == "generate-from-keywords":
        generate_from_keywords()
    elif args.step == "generate-from-shapes":
        generate_from_shapes()
    elif args.step == "generate-natural":
        generate_natural_queries()
    elif args.step == "generate-adversarial":
        generate_adversarial()
    elif args.step == "label-with-scillm":
        label_with_scillm()
    elif args.step == "merge":
        merge_all()
    elif args.step == "train-setfit":
        train_setfit()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
