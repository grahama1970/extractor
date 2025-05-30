#!/usr/bin/env python3
"""
Example of how hierarchical sections would be flattened for ArangoDB
"""
import json

def flatten_for_arangodb(hierarchical_doc):
    """Flatten hierarchical document for ArangoDB insertion"""
    flattened_sections = []
    
    def flatten_section(section, parent_id=None):
        # Create flattened section for ArangoDB
        flat_section = {
            "_key": section["section_hash"],  # Use hash as key
            "id": section["id"],
            "title": section["header"]["text"],
            "section_number": section["metadata"]["section_number"],
            "depth_level": section["metadata"]["depth_level"],
            
            # Full breadcrumb for reconstruction
            "hierarchy_titles": section["metadata"]["hierarchy_titles"],
            "hierarchy_hashes": section["metadata"]["hierarchy_hashes"],
            
            # Direct parent reference (for graph queries)
            "parent_hash": parent_id,
            
            # Content metadata
            "summary": section["metadata"]["summary"],
            "word_count": section["metadata"]["word_count"],
            "has_images": section["metadata"]["content_types"]["has_images"],
            "has_tables": section["metadata"]["content_types"]["has_tables"],
            
            # Content blocks in order
            "content_blocks": section["content_blocks"]
        }
        
        flattened_sections.append(flat_section)
        
        # Recursively flatten subsections
        for subsection in section.get("subsections", []):
            flatten_section(subsection, section["section_hash"])
    
    # Start with top-level sections
    for section in hierarchical_doc["sections"]:
        flatten_section(section)
    
    return flattened_sections

# Load the test output
with open("hierarchical_output.json", "r") as f:
    doc = json.load(f)

# Flatten for ArangoDB
flattened = flatten_for_arangodb(doc)

print("FLATTENED SECTIONS FOR ARANGODB")
print("="*50)

for section in flattened:
    print(f"\nSection Key: {section['_key']}")
    print(f"Title: {section['title']}")
    print(f"Parent Hash: {section['parent_hash']}")
    print(f"Breadcrumb Titles: {' > '.join(section['hierarchy_titles'])}")
    print(f"Breadcrumb Hashes: {' > '.join(section['hierarchy_hashes'])}")
    print(f"Depth: {section['depth_level']}")
    print(f"Content blocks: {len(section['content_blocks'])}")

# Show example AQL query to reconstruct hierarchy
print("\n" + "="*50)
print("Example AQL Query to Get Section with Parents:")
print("="*50)
print("""
// Get a section and all its parents
LET section = DOCUMENT('sections/f12902b591010af4')
LET parent_hashes = section.hierarchy_hashes

FOR hash IN parent_hashes
    LET parent_section = DOCUMENT(CONCAT('sections/', hash))
    RETURN {
        hash: hash,
        title: parent_section.title,
        depth: parent_section.depth_level
    }
""")