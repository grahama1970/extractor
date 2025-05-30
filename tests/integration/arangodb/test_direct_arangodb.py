Structure verification:")
    for key in ['document', 'metadata', 'validation', 'raw_corpus']:
        print(f"- Has '{key}': {key in data}")
    
    if 'document' in data:
        doc_data = data['document']
        print(f"\nDocument details:")
        print(f"- ID: {doc_data.get('id')}")
        print(f"- Pages: {len(doc_data.get('pages', []))}")
        
        if doc_data.get('pages'):
            page_data = doc_data['pages'][0]
            print(f"- Blocks in page 0: {len(page_data.get('blocks', []))}")
            
            for block in page_data.get('blocks', []):
                print(f"  - {block['type']}: {block['text'][:50]}...")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()