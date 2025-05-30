" + "="*80)
    print("EVALUATING ARANGODB OUTPUT")
    print("="*80 + "\n")
    
    # Check for required top-level fields
    required_fields = ['document', 'metadata', 'validation', 'raw_corpus']
    missing_fields = [field for field in required_fields if field not in output_data]
    
    if missing_fields:
        print(f"❌ Missing required top-level fields: {missing_fields}")
        return False
    else:
        print("✅ All required top-level fields present")
    
    # Evaluate document structure
    print("\n📄 Document Structure:")
    doc = output_data.get('document', {})
    
    if 'id' in doc:
        print(f"  ✅ Document ID: {doc['id']}")
    else:
        print("  ❌ Missing document ID")
    
    if 'pages' in doc:
        print(f"  ✅ Pages: {len(doc['pages'])} pages found")
        
        # Check first page structure
        if doc['pages']:
            first_page = doc['pages'][0]
            if 'blocks' in first_page:
                print(f"  ✅ Blocks: {len(first_page['blocks'])} blocks in first page")
                
                # Analyze block types
                block_types = {}
                for page in doc['pages']:
                    for block in page.get('blocks', []):
                        block_type = block.get('type', 'unknown')
                        block_types[block_type] = block_types.get(block_type, 0) + 1
                
                print("\n  📊 Block Type Distribution:")
                for block_type, count in sorted(block_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"    - {block_type}: {count}")
            else:
                print("  ❌ No blocks found in first page")
    else:
        print("  ❌ No pages found")
    
    # Evaluate metadata
    print("\n📋 Metadata:")
    metadata = output_data.get('metadata', {})
    metadata_fields = ['title', 'filepath', 'page_count', 'processing_time', 'language']
    
    for field in metadata_fields:
        if field in metadata:
            value = metadata[field]
            if value is not None:
                print(f"  ✅ {field}: {value}")
            else:
                print(f"  ⚠️  {field}: null")
        else:
            print(f"  ❌ Missing {field}")
    
    # Evaluate validation
    print("\n✅ Validation:")
    validation = output_data.get('validation', {})
    if 'corpus_validation' in validation:
        cv = validation['corpus_validation']
        print(f"  ✅ Corpus validation performed: {cv.get('performed', False)}")
        print(f"  ✅ Threshold: {cv.get('threshold', 'N/A')}")
        print(f"  ✅ Raw corpus length: {cv.get('raw_corpus_length', 0)}")
    else:
        print("  ❌ No corpus validation data")
    
    # Evaluate raw corpus
    print("\n📝 Raw Corpus:")
    raw_corpus = output_data.get('raw_corpus', {})
    if 'full_text' in raw_corpus:
        full_text = raw_corpus['full_text']
        print(f"  ✅ Full text length: {len(full_text)} characters")
        print(f"  ✅ Preview: {full_text[:100]}...")
    else:
        print("  ❌ No full text found")
    
    if 'pages' in raw_corpus:
        print(f"  ✅ Page-level text: {len(raw_corpus['pages'])} pages")
    
    # Check for table metadata (from our enhancements)
    print("\n📊 Table Metadata (Enhanced Features):")
    table_count = 0
    tables_with_metadata = 0
    
    for page in doc.get('pages', []):
        for block in page.get('blocks', []):
            if block.get('type') == 'table':
                table_count += 1
                if 'metadata' in block:
                    meta = block['metadata']
                    if any(key in meta for key in ['extraction_method', 'extraction_details', 'quality_score', 'merge_info']):
                        tables_with_metadata += 1
    
    if table_count > 0:
        print(f"  ✅ Tables found: {table_count}")
        print(f"  ✅ Tables with metadata: {tables_with_metadata}")
        
        # Show sample table metadata
        for page in doc.get('pages', []):
            for block in page.get('blocks', []):
                if block.get('type') == 'table' and 'metadata' in block:
                    print(f"\n  📊 Sample Table Metadata:")
                    meta = block['metadata']
                    for key, value in meta.items():
                        if key in ['extraction_method', 'extraction_details', 'quality_score', 'merge_info']:
                            print(f"    - {key}: {value}")
                    break
            else:
                continue
            break
    else:
        print("  ℹ️  No tables found in document")
    
    # Overall evaluation
    print("\n" + "="*80)
    print("OVERALL EVALUATION")
    print("="*80)
    
    issues = []
    if missing_fields:
        issues.append(f"Missing top-level fields: {missing_fields}")
    if 'id' not in doc:
        issues.append("Missing document ID")
    if not doc.get('pages'):
        issues.append("No pages found")
    if not raw_corpus.get('full_text'):
        issues.append("No full text extracted")
    
    if issues:
        print("\n❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n⚠️  The output may need adjustments for ArangoDB ingestion")
    else:
        print("\n✅ Output meets all basic ArangoDB requirements!")
        print("✅ Ready for ingestion with document_to_arangodb()")
    
    return len(issues) == 0

def main():
    """Main function."""
    
    pdf_path = "."
    output_dir = "."
    
    # Convert PDF
    output_path, output_data = convert_pdf_for_arangodb(pdf_path, output_dir)
    
    if output_data:
        # Evaluate output
        meets_requirements = evaluate_arangodb_output(output_data)
        
        # Show sample for import
        if meets_requirements:
            print("\n📦 Ready to import with:")
            print("```python")
            print("from marker.arangodb.importers import document_to_arangodb")
            print()
            print(f"with open('{output_path}', 'r') as f:")
            print("    marker_output = json.load(f)")
            print()
            print("doc_key, stats = document_to_arangodb(")
            print("    marker_output,")
            print("    db_host='localhost',")
            print("    db_port=8529,")
            print("    db_name='documents',")
            print("    username='root',")
            print("    password='password'")
            print(")")
            print("```")

if __name__ == "__main__":
    main()