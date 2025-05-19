#!/usr/bin/env python3
"""
Show compact section structure - essential fields only
"""
import json

with open("hierarchical_output.json", "r") as f:
    doc = json.load(f)

# Get subsection to show breadcrumbs
section = doc["sections"][0]["subsections"][0]  # Section 1.1

# Compact structure showing only essential fields
compact = {
    "id": section["id"],
    "hash": section["section_hash"],
    "title": section["header"]["text"],
    "number": section["metadata"]["section_number"],
    "breadcrumb_titles": section["metadata"]["hierarchy_titles"],
    "breadcrumb_hashes": section["metadata"]["hierarchy_hashes"], 
    "content": [
        f"{block['type']}: {block.get('html', '')[:30]}..."
        for block in section["content_blocks"]
    ]
}

print("COMPACT SECTION STRUCTURE")
print(json.dumps(compact, indent=2))