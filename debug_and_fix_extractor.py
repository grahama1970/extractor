#!/usr/bin/env python3
"""Debug and fix the extractor section parsing issue"""

import sys
sys.path.insert(0, '/home/graham/workspace/experiments/extractor/src')

# Force reload
if 'extractor.unified_extractor_v2' in sys.modules:
    del sys.modules['extractor.unified_extractor_v2']

from extractor.core.converters.pdf import convert_single_pdf
from extractor.unified_extractor_v2 import parse_surya_sections, extract_to_unified_json
import json

print("🔍 DEBUGGING EXTRACTOR SECTION PARSING")
print("=" * 70)

# Step 1: Get raw markdown from PDF
pdf_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
print("\n1️⃣ Extracting raw markdown from PDF...")

result = convert_single_pdf(pdf_path, max_pages=5)

# Handle different return types
if hasattr(result, 'markdown'):
    markdown = result.markdown
elif hasattr(result, 'text_content'):
    markdown = result.text_content
else:
    markdown = str(result)

print(f"   Markdown length: {len(markdown)} chars")

# Step 2: Examine the markdown structure
print("\n2️⃣ Examining markdown structure...")
lines = markdown.split('\n')[:50]  # First 50 lines

print("   First 50 lines:")
for i, line in enumerate(lines):
    if line.strip():
        print(f"   {i+1:3d}: {line[:80]}...")

# Step 3: Test the parser
print("\n3️⃣ Testing enhanced parser...")
sections = parse_surya_sections(markdown)
print(f"   Found {len(sections)} sections")

# Show all sections
print("\n   All sections found:")
for i, sec in enumerate(sections[:20]):  # First 20
    print(f"   {i+1:3d}. [L{sec['level']}] {sec['title'][:60]}...")

# Step 4: Test full extraction
print("\n4️⃣ Testing full extraction pipeline...")
full_result = extract_to_unified_json(pdf_path)
full_sections = full_result.get('vertices', {}).get('sections', [])
print(f"   Full pipeline found {len(full_sections)} sections")

# Step 5: Diagnose the issue
print("\n5️⃣ DIAGNOSIS:")
if len(sections) > 50 and len(full_sections) < 10:
    print("   ❌ Parser works but full pipeline doesn't use it!")
    print("   🔧 FIX: Ensure extract_to_unified_json uses the enhanced parser")
elif len(sections) < 10:
    print("   ❌ Parser not detecting headers properly")
    print("   🔧 FIX: Improve header detection regex")
else:
    print("   ✅ Everything working correctly!")

# Save debug info
debug_info = {
    "markdown_length": len(markdown),
    "parser_sections": len(sections),
    "full_pipeline_sections": len(full_sections),
    "sample_markdown": markdown[:2000],
    "sample_sections": [{"title": s["title"], "level": s["level"]} for s in sections[:10]]
}

with open('/home/graham/workspace/experiments/extractor/debug_info.json', 'w') as f:
    json.dump(debug_info, f, indent=2)

print("\n💾 Debug info saved to debug_info.json")
print("\n✅ Debug complete")