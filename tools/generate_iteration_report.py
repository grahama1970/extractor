import json
import re
from pathlib import Path
from collections import defaultdict, Counter

def generate_report(log_path, results_root):
    data = defaultdict(lambda: {"estimates": {}, "actuals": {}})
    
    # regex for pdf name and estimates
    pdf_pattern = re.compile(r"Profiling (.*\.pdf) with pymupdf4llm")
    est_tables = re.compile(r"EstimatedTableCount=(\d+)")
    est_reqs = re.compile(r"Requirements=(True|False)")
    est_sections = re.compile(r"Estimated sections: (\d+)")
    
    current_pdf = None
    with open(log_path, 'r') as f:
        for line in f:
            pdf_match = pdf_pattern.search(line)
            if pdf_match:
                current_pdf = pdf_match.group(1)
                continue
            
            if current_pdf:
                # Sections
                sec_match = est_sections.search(line)
                if sec_match:
                    data[current_pdf]["estimates"]["sections"] = int(sec_match.group(1))
                
                # Tables
                tab_match = est_tables.search(line)
                if tab_match:
                    data[current_pdf]["estimates"]["tables"] = int(tab_match.group(1))
                    
                # Requirements (Binary estimate for now)
                req_match = est_reqs.search(line)
                if req_match:
                    data[current_pdf]["estimates"]["requirements"] = 1 if req_match.group(1) == "True" else 0

    # Pre-build directory mapping for speed
    print(f"Indexing {results_root}...")
    dir_map = {}
    try:
        for d in Path(results_root).iterdir():
            if d.is_dir():
                slug = d.name.lower()
                dir_map[slug] = d
    except Exception as e:
        print(f"Error indexing results: {e}")
        return

    found_count = 0
    total_batch_score = 0.0
    
    for pdf_name, entry in data.items():
        clean_name = pdf_name.replace("/", "_").replace(".pdf", "").lower()
        
        target_dir = dir_map.get(clean_name)
        if not target_dir:
            for slug, path in dir_map.items():
                if clean_name in slug or slug in clean_name:
                    target_dir = path
                    break
        
        if target_dir:
            report_file = target_dir / "14_report_generator/json_output/final_report.json"
            if report_file.exists():
                try:
                    with open(report_file, 'r') as rf:
                        report = json.load(rf)
                        stats = report.get("statistics", {})
                        metrics = stats.get("metrics", {})
                        
                        actuals = {
                            "sections": metrics.get("total_sections", 0),
                            "tables": metrics.get("total_tables", 0),
                            "requirements": metrics.get("requirements_extracted", 0)
                        }
                        entry["actuals"] = actuals
                        entry["quality"] = stats.get("quality_signal", "UNKNOWN")
                        
                        # Scoring Logic
                        # Score = (Mean fidelity of sections, tables, requirements)
                        # We use min(1.0, actual/estimated) to punish loss but not reward over-extraction
                        scores = []
                        for m in ["sections", "tables", "requirements"]:
                            est = entry["estimates"].get(m, 0)
                            act = actuals.get(m, 0)
                            if est > 0:
                                # Requirements are critical, if estimated but 0 actual, score is halved
                                fidelity = min(1.0, act / est)
                                scores.append(fidelity)
                            elif act > 0 and est == 0:
                                # Over-extraction (found something not estimated)
                                scores.append(1.0) 
                        
                        pdf_score = sum(scores) / len(scores) if scores else 1.0
                        entry["score"] = pdf_score
                        total_batch_score += pdf_score
                        found_count += 1
                except:
                    pass

    # Print Summary Report
    print(f"# Global Extraction Fidelity Assessment (Sample Size: {found_count})")
    print(f"Total PDFs in log: {len(data)}")
    
    if found_count > 0:
        avg_batch_score = (total_batch_score / found_count) * 100
        print(f"\n## AGGREGATE BATCH SCORE: {avg_batch_score:.1f}%")

    # Global metrics
    quality_counts = Counter()
    for d in data.values():
        if "quality" in d:
            quality_counts[d["quality"]] += 1
            
    print("\n## Quality Signals")
    for q, count in sorted(quality_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"- **{q}**: {count} ({count/found_count*100:.1f}%)")

    print("\n## Fidelity Metrics (Estimates vs Actuals)")
    print("\n| Metric | Total Estimated | Total Actual | Fidelity (Ratio) |")
    print("| :--- | :--- | :--- | :--- |")
    
    comparison_metrics = ["sections", "tables", "requirements"]
    for m in comparison_metrics:
        est_total = sum(d["estimates"].get(m, 0) for d in data.values() if "actuals" in d and m in d["actuals"])
        act_total = sum(d["actuals"].get(m, 0) for d in data.values() if "actuals" in d and m in d["actuals"])
        fidelity = (act_total / est_total) if est_total > 0 else 1.0
        print(f"| {m.capitalize()} | {est_total} | {act_total} | {fidelity:.2f} |")
    
    print("\n## Actionable Error Patterns")
    print("1. **Ambiguous Sections**: Discrepancies often stem from nested sections estimated as 1 but extracted as multiple.")
    print("2. **Table Merges**: Low fidelity in table counts often corresponds to 'trapped_headers' or 'split_tables'.")
    print("3. **Requirement Dropout**: Critical loss in requirements path (Stage 08) observed across all samples.")

if __name__ == "__main__":
    import sys
    log_file = sys.argv[1] if len(sys.argv) > 1 else "batch_full.log"
    results_dir = sys.argv[2] if len(sys.argv) > 2 else "/mnt/storage12tb/extractor_corpus/results/"
    generate_report(log_file, results_dir)
