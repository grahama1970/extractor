")
    
    # Create a mock document
    document = Document(filepath="test.pdf", pages=[])
    
    # Create a page
    page = Page(page_id=0, polygon=PolygonBox(polygon=[[0, 0], [595, 0], [595, 842], [0, 842]]))
    
    # Create sample blocks
    title_block = Text(
        id="title1",
        polygon=PolygonBox(polygon=[[50, 50], [545, 50], [545, 100], [50, 100]]),
        text_lines=["Main Document Title"]
    )
    title_block.block_type = BlockTypes.Title
    
    section1 = SectionHeader(
        id="section1",
        polygon=PolygonBox(polygon=[[50, 150], [545, 150], [545, 200], [50, 200]]),
        text_lines=["Introduction"],
        level=1
    )
    
    text1 = Text(
        id="text1",
        polygon=PolygonBox(polygon=[[50, 220], [545, 220], [545, 300], [50, 300]]),
        text_lines=["This is the introduction text."]
    )
    
    section2 = SectionHeader(
        id="section2",
        polygon=PolygonBox(polygon=[[50, 350], [545, 350], [545, 400], [50, 400]]),
        text_lines=["Methods"],
        level=1
    )
    
    section2_1 = SectionHeader(
        id="section2_1",
        polygon=PolygonBox(polygon=[[50, 420], [545, 420], [545, 470], [50, 470]]),
        text_lines=["Data Collection"],
        level=2
    )
    
    text2 = Text(
        id="text2",
        polygon=PolygonBox(polygon=[[50, 490], [545, 490], [545, 570], [50, 570]]),
        text_lines=["Description of data collection methods."]
    )
    
    # Add blocks to page
    page.children = [title_block, section1, text1, section2, section2_1, text2]
    document.pages.append(page)
    
    # Process document with breadcrumbs
    enhanced_blocks = add_breadcrumbs_to_document(document)
    
    # Display results
    print("Enhanced Document Structure with Breadcrumbs:\n")
    for i, block in enumerate(enhanced_blocks):
        print(f"Block {i + 1}:")
        print(f"  Type: {block['type']}")
        print(f"  Text: {block.get('text', 'N/A')}")
        print(f"  Page: {block['page']}")
        print(f"  Section Path: {block['section_path']}")
        print(f"  Section Level: {block['section_level']}")
        print(f"  Parent Sections: {block['parent_sections']}")
        print()
    
    # Output as JSON-like structure
    import json
    print("\nJSON Output:")
    json_output = []
    for block in enhanced_blocks:
        json_block = {
            "type": block['type'],
            "text": block.get('text', ''),
            "page": block['page'],
            "section_path": block['section_path'],
            "section_level": block['section_level']
        }
        json_output.append(json_block)
    
    print(json.dumps(json_output, indent=2))