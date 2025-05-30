Structure verification:")
        print(f"- Has 'document' key: {'document' in output_data}")
        print(f"- Has 'metadata' key: {'metadata' in output_data}")
        print(f"- Has 'validation' key: {'validation' in output_data}")
        print(f"- Has 'raw_corpus' key: {'raw_corpus' in output_data}")
        
        if 'document' in output_data:
            doc = output_data['document']
            print(f"- Document ID: {doc.get('id', 'N/A')}")
            print(f"- Pages: {len(doc.get('pages', []))}")
            
            # Count blocks
            total_blocks = 0
            block_types = {}
            for page in doc.get('pages', []):
                for block in page.get('blocks', []):
                    total_blocks += 1
                    block_type = block.get('type', 'unknown')
                    block_types[block_type] = block_types.get(block_type, 0) + 1
            
            print(f"- Total blocks: {total_blocks}")
            print("\nBlock type distribution:")
            for btype, count in sorted(block_types.items()):
                print(f"  - {btype}: {count}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)