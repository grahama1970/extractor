Analyzing tables in output...")
        analyze_tables(output_data)
        
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()

def analyze_tables(data):
    """Analyze tables in the output to check for metadata"""
    tables_found = 0
    tables_with_metadata = 0
    
    def find_tables(obj, path=""):
        nonlocal tables_found, tables_with_metadata
        
        if isinstance(obj, dict):
            # Check various ways tables might be represented
            is_table = False
            if obj.get("type") == "table":
                is_table = True
            elif obj.get("block_type") == "Table":
                is_table = True
            elif obj.get("block_type") == "11":  # Numeric block type for table
                is_table = True
            
            if is_table:
                tables_found += 1
                metadata = obj.get("metadata", {})
                print(f"\nTable {tables_found} at {path}:")
                print(f"  ID: {obj.get('id', obj.get('block_id', 'N/A'))}")
                print(f"  Has metadata: {bool(metadata)}")
                
                if metadata:
                    tables_with_metadata += 1
                    print(f"  Extraction method: {metadata.get('extraction_method', 'N/A')}")
                    print(f"  Quality score: {metadata.get('quality_score', 'N/A')}")
                    if metadata.get('extraction_details'):
                        print(f"  Extraction details: {json.dumps(metadata['extraction_details'], indent=4)}")
                    if metadata.get('merge_info'):
                        print(f"  Merge info: {json.dumps(metadata['merge_info'], indent=4)}")
                else:
                    # Check if metadata might be in a different location
                    if 'extraction_method' in obj:
                        print(f"  Found extraction_method at block level: {obj['extraction_method']}")
                
            for key, value in obj.items():
                find_tables(value, f"{path}.{key}")
                
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_tables(item, f"{path}[{i}]")
    
    find_tables(data)
    
    print(f"\n\nSummary:")
    print(f"Total tables found: {tables_found}")
    print(f"Tables with metadata: {tables_with_metadata}")
    
    if tables_found > 0 and tables_with_metadata == 0:
        print("\n⚠️  WARNING: No tables have metadata! The enhanced table processor may not be working correctly.")
        print("Check if the enhanced_table processor is being registered properly.")

if __name__ == "__main__":
    main()