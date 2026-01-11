
import re
from pathlib import Path

def audit_file(path):
    print(f"Auditing structure of {path}...")
    with open(path, 'r') as f:
        lines = f.readlines()
        
    structure = []
    current_section = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Detect Section
        if line.startswith("## ") and "ID: section_" in line:
            sec_id = re.search(r"ID: (section_\d+)", line).group(1)
            structure.append(f"section {sec_id.split('_')[1]}")
            current_section = sec_id
            continue
            
        # Detect Table
        if line.startswith("### Table"):
            structure.append("table")
            continue
        
        # Detect Figure
        if line.startswith("### Figure") or line.startswith("![Figure]"):
            # Avoid dupes if both lines exist close
            if structure and structure[-1] == "figure":
                continue
            structure.append("figure")
            continue
            
        # Detect Requirement
        if "> **[REQ-" in line or "| REQ-" in line or "| **[REQ-" in line:
            # Table-based reqs or Blockquote reqs
            if structure and structure[-1] == "requirement":
                continue
            structure.append("requirement")
            continue
            
        # Detect Text
        # Heuristic: non-empty, not special structure, not table row
        if line and not line.startswith(("#", ">", "|", "!")):
             if structure and structure[-1] == "text":
                 continue
             structure.append("text")

    print("\n--- Detected Structure ---")
    for s in structure:
        print(s)

if __name__ == "__main__":
    audit_file("/home/graham/.gemini/antigravity/brain/e798a01e-b43d-4bf8-8404-0a8308348507/walkthrough.md.resolved")
