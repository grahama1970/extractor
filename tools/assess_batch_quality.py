import json
from pathlib import Path
from collections import Counter

def assess_batch(manifest_path: str):
    count = 0
    qualities = Counter()
    estimates_vs_actual = Counter()
    failures = Counter()
    
    with open(manifest_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                count += 1
                qualities[data.get('quality', 'UNKNOWN')] += 1
                
                # Compare estimated (from s00) vs actual (section_count)
                # Note: We need to pull the estimate from the corresponding 
                # result folder's scanned_pdf.json if not in manifest
                
                if data.get('status') != 'SUCCESS':
                    failures[data.get('error', 'Unknown Error')[:50]] += 1
                    
            except Exception as e:
                pass
                
    print(f"Total Processed: {count}")
    print("\nQuality Distribution:")
    for k, v in qualities.items():
        print(f"  {k}: {v} ({v/count*100:.1f}%)")
        
    print("\nTop Failures:")
    for k, v in failures.most_common(5):
        print(f"  {v}: {k}")

if __name__ == "__main__":
    import sys
    assess_batch(sys.argv[1])
