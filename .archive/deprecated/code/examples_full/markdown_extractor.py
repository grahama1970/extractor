"""
Module: markdown_extractor.py
Description: Implementation of markdown extractor functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

Section Hierarchy Paths:")
        for section in section_data["sections"]:
            path_str = " > ".join([item["title"] for item in section.get("section_path", [])])
            print(f"[H{section['level']}] {section['title']} (hash: {next((item['hash'] for item in section['section_path'] if item['level'] == section['level']), '')})")
            print(f"  Path: {path_str}")
            print(f"  Hashes: {', '.join([item['hash'] for item in section.get('section_path', []) if item.get('hash')])}")
            print()

    # Output the section data
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(section_data, f, indent=2, ensure_ascii=False)
        print(f"Section data saved to {args.output}")
    else:
        if not args.dump_paths:
            print(json.dumps(section_data, indent=2, ensure_ascii=False))

    # Output cleaned markdown if requested
    if args.clean:
        cleaned_markdown = remove_breadcrumbs(markdown_content)
        clean_output = args.output.replace('.json', '_clean.md') if args.output else 'cleaned_output.md'
        with open(clean_output, 'w', encoding='utf-8') as f:
            f.write(cleaned_markdown)
        print(f"Cleaned markdown saved to {clean_output}")


if __name__ == "__main__":
    main()