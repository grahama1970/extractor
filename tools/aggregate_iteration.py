
import json
from pathlib import Path

def aggregate():
    base_path = Path("/mnt/storage12tb/extractor_corpus/results_iteration_1/results_iter1/")
    total_est_sections = 0
    total_act_sections = 0
    total_est_tables = 0
    total_act_tables = 0
    total_act_reqs = 0
    total_docs = 0
    qualities = {}
    completed = []

    for doc_dir in base_path.iterdir():
        if not doc_dir.is_dir():
            continue
        
        profile_path = doc_dir / "00_profile_detector/profile.json"
        report_path = doc_dir / "14_report_generator/json_output/final_report.json"
        
        if not report_path.exists():
            continue
            
        total_docs += 1
        completed.append(doc_dir.name)
        
        # Actuals
        try:
            with open(report_path, 'r') as f:
                report = json.load(f)
                stats = report.get("statistics", {})
                metrics = stats.get("metrics", {})
                
                total_act_sections += metrics.get("total_sections", 0)
                total_act_tables += metrics.get("total_tables", 0)
                total_act_reqs += metrics.get("requirements_extracted", 0)
                
                q = stats.get("quality_signal") or report.get("assessment", {}).get("quality_signal") or "UNKNOWN"
                qualities[q] = qualities.get(q, 0) + 1
        except Exception as e:
            print(f"Error reading report for {doc_dir.name}: {e}")

        # Estimates
        if profile_path.exists():
            try:
                with open(profile_path, 'r') as f:
                    profile = json.load(f)
                    # Try different estimate fields
                    est_sec = (profile.get("hierarchy", {}).get("estimated_sections") or 
                               profile.get("toc", {}).get("entry_count") or 0)
                    total_est_sections += est_sec
                    
                    est_tab = profile.get("elements", {}).get("estimated_table_count", 0)
                    total_est_tables += est_tab
            except Exception as e:
                print(f"Error reading profile for {doc_dir.name}: {e}")

    print(f"# Iteration 1 Interim Assessment Report (Docs Finished: {total_docs}/45)")
    print("\n## Fidelity Metrics")
    print(f"| Metric | Total Estimated | Total Actual | Fidelity (Ratio) |")
    print(f"| :--- | :--- | :--- | :--- |")
    
    def ratio(act, est):
        return f"{act/est:.2f}" if est > 0 else "N/A"

    print(f"| Sections | {total_est_sections} | {total_act_sections} | {ratio(total_act_sections, total_est_sections)} |")
    print(f"| Tables | {total_est_tables} | {total_act_tables} | {ratio(total_act_tables, total_est_tables)} |")
    print(f"| Requirements | TBD | {total_act_reqs} | N/A | (Jump from 0.00!)")
    
    print("\n## Quality Signals")
    for q, count in qualities.items():
        print(f"- **{q}**: {count} ({count/total_docs*100:.1f}%)")

if __name__ == "__main__":
    aggregate()
