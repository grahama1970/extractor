=== EXTRACTION ANALYSIS ===")
    
    # Count different element types
    counts = {
        "pages": 0,
        "sections": 0,
        "tables": 0,
        "figures": 0,
        "equations": 0,
        "code_blocks": 0,
        "text_blocks": 0
    }
    
    tables_info = []
    
    def analyze_element(obj, path=""):
        if isinstance(obj, dict):
            elem_type = obj.get("type", obj.get("block_type", ""))
            
            if elem_type in ["Table", "table", "11"]:
                counts["tables"] += 1
                table_info = {
                    "path": path,
                    "id": obj.get("id", obj.get("block_id", "unknown")),
                    "metadata": obj.get("metadata", {}),
                    "has_extraction_method": "extraction_method" in obj.get("metadata", {}),
                    "has_quality_score": "quality_score" in obj.get("metadata", {}),
                    "has_merge_info": "merge_info" in obj.get("metadata", {})
                }
                tables_info.append(table_info)
                
            elif elem_type in ["Figure", "figure", "19"]:
                counts["figures"] += 1
            elif elem_type in ["Equation", "equation", "13"]:
                counts["equations"] += 1
            elif elem_type in ["Code", "code", "14"]:
                counts["code_blocks"] += 1
            elif elem_type in ["Text", "text", "22"]:
                counts["text_blocks"] += 1
            elif elem_type in ["SectionHeader", "section_header", "20"]:
                counts["sections"] += 1
            elif elem_type in ["Page", "page", "7"]:
                counts["pages"] += 1
            
            # Recurse into nested elements
            for key, value in obj.items():
                analyze_element(value, f"{path}.{key}")
                
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                analyze_element(item, f"{path}[{i}]")
    
    analyze_element(data)
    
    # Print summary
    print("\nElement counts:")
    for elem_type, count in counts.items():
        print(f"  {elem_type}: {count}")
    
    print(f"\nTable Analysis:")
    print(f"Total tables found: {len(tables_info)}")
    
    if tables_info:
        tables_with_metadata = sum(1 for t in tables_info if t["metadata"])
        print(f"Tables with metadata: {tables_with_metadata}")
        
        for i, table in enumerate(tables_info):
            print(f"\nTable {i+1}:")
            print(f"  ID: {table['id']}")
            print(f"  Path: {table['path']}")
            print(f"  Has metadata: {bool(table['metadata'])}")
            if table['metadata']:
                print(f"  Has extraction_method: {table['has_extraction_method']}")
                print(f"  Has quality_score: {table['has_quality_score']}")
                print(f"  Has merge_info: {table['has_merge_info']}")
                if table['metadata'].get('extraction_method'):
                    print(f"  Extraction method: {table['metadata']['extraction_method']}")
                if table['metadata'].get('extraction_details'):
                    print(f"  Extraction details: {json.dumps(table['metadata']['extraction_details'], indent=4)}")
    
    # Check ground truth expectations
    print("\n=== GROUND TRUTH COMPARISON ===")
    print("Expected elements from 'Absolute Zero' paper:")
    print("- Multiple sections with hierarchical structure")
    print("- Table 1: Performance comparison table")
    print("- Multiple mathematical equations")
    print("- Code blocks showing algorithms")
    print("- Multiple figures")
    
    if counts["tables"] == 0:
        print("\n⚠️  WARNING: No tables found! Expected at least Table 1 (performance comparison)")
    if counts["equations"] == 0:
        print("⚠️  WARNING: No equations found! Expected multiple mathematical formulas")
    if counts["code_blocks"] == 0:
        print("⚠️  WARNING: No code blocks found! Expected algorithm listings")

if __name__ == "__main__":
    main()