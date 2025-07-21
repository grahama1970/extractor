"""
Module: arangodb_import.py
Description: ArangoDB graph database interactions

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

")
    
    # Also save document metadata as a separate file
    metadata = arangodb_output.document_metadata
    metadata["_key"] = doc_id  # Use doc_id as the _key for the document
    metadata_path = os.path.join(output_dir, f"documents_{doc_id}.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(metadata))
    
    # Print summary
    print(f"\nArangoDB Import Files:")
    print(f"- Objects file: {import_path}")
    print(f"- Document metadata: {metadata_path}")
    print(f"- Total objects: {len(import_lines)}")
    
    # Print command for arangoimport
    print(f"\nImport commands:")
    print(f"arangoimport --collection {collection_name} --file {import_path} --type jsonl")
    print(f"arangoimport --collection documents --file {metadata_path} --type json")
    
    return import_path, metadata_path


def main():
    parser = argparse.ArgumentParser(description="Prepare ArangoDB import files from documents")
    parser.add_argument("input", help="Input PDF file")
    parser.add_argument("--collection", "-c", help="ArangoDB collection name", default="content_objects")
    parser.add_argument("--output", "-o", help="Output directory", default="arangodb_import")
    parser.add_argument("--id", help="Document ID (defaults to filename)")
    parser.add_argument("--pages", "-p", help="Page range (e.g., 0-3)", default="0-")
    parser.add_argument("--no-images", action="store_true", help="Skip image processing")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Parse page range
    page_range = args.pages.split('-')
    start_page = int(page_range[0])
    end_page = None if len(page_range) < 2 or not page_range[1] else int(page_range[1])
    
    # Process document
    process_document(
        input_path=args.input,
        output_dir=args.output,
        collection_name=args.collection,
        doc_id=args.id,
        start_page=start_page,
        end_page=end_page,
        process_images=not args.no_images
    )


if __name__ == "__main__":
    main()