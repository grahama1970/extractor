Document Structure:")
        print(f"- Document ID: {output_data.get('document', {}).get('id', 'N/A')}")
        print(f"- Total Pages: {len(output_data.get('document', {}).get('pages', []))}")
        
        # Count block types
        block_types = {}
        for page in output_data.get('document', {}).get('pages', []):
            for block in page.get('blocks', []):
                block_type = block.get('type', 'unknown')
                block_types[block_type] = block_types.get(block_type, 0) + 1
        
        print("\nBlock Type Distribution:")
        for block_type, count in sorted(block_types.items()):
            print(f"  - {block_type}: {count}")
        
        print(f"\nRaw Corpus Length: {len(output_data.get('raw_corpus', {}).get('full_text', ''))}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)