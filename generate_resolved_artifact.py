
import duckdb
from pathlib import Path

# Connect
con = duckdb.connect('data/results/pipeline/pipeline.duckdb', read_only=True)
output_path = Path('/home/graham/.gemini/antigravity/brain/e798a01e-b43d-4bf8-8404-0a8308348507/pdf_object_order.md.resolved')

print(f'Generating {output_path}...')

# 1. Fetch Merged Content (Text/Tables/Figs)
# Join with source tables to get image path
rows = con.execute('''
    SELECT mc.sort_order, mc.type, mc.content, mc.page, mc.section_id, 
           CASE 
             WHEN mc.type = 'figure' THEN f.image_path 
             WHEN mc.type = 'table' THEN t.image_path 
             ELSE NULL 
           END as image_path
    FROM merged_content mc
    LEFT JOIN figures f ON mc.asset_id = f.id AND mc.type = 'figure'
    LEFT JOIN tables t ON mc.asset_id = t.id AND mc.type = 'table'
    ORDER BY mc.sort_order
''').fetchall()

# 2. Fetch Requirements by Section
# (Handle empty requirements table case gracefully)
try:
    reqs = con.execute('SELECT section_id, id, text, confidence FROM requirements').fetchall()
except Exception:
    reqs = []

# 3. Fetch Lean4 Proofs
try:
    proofs = con.execute('SELECT requirement_id, lean4_code, compilation_status FROM lean4_proofs').fetchall()
    proofs_map = {p[0]: p for p in proofs}
except Exception:
    proofs_map = {}

reqs_by_section = {}
for r in reqs:
    sec_id = r[0]
    reqs_by_section.setdefault(sec_id, []).append(r)

lines = []
lines.append('# Resolved PDF Object Order & Format (BHT_CV32A65X)')
lines.append('> **Context:** This document represents the serialized stream presented to the LLM.')
lines.append('> **Legend:** `[TYPE]` | Order: `Page X (Y=...)`')
lines.append('')

current_page = -1

for r in rows:
    sort_order, obj_type, content, page, section_id, image_path = r
    
    # Format Sort Order
    # sort_order is page * 10000 + y0.
    y_coord = int(sort_order % 10000)
    order_str = f"Page {page+1} (Y={y_coord})"
    
    if page != current_page:
        lines.append(f'\n## --- Page {page+1} ---\n')
        current_page = page

    # Header
    lines.append(f'### [{obj_type.upper()}] (Order: {order_str})')
    
    if image_path:
         lines.append(f'> **Image:** `{image_path}`')
    
    if not content:
        lines.append('*(Empty Content)*')
        if obj_type == 'figure':
            lines.append('> *Note: Figure description missing (Step 06b likely skipped).*')
    else:
        if obj_type == 'table':
            lines.append('```csv')
            lines.append(content.strip())
            lines.append('```')
        elif obj_type == 'text':
            lines.append(content.strip())
            
            # CHECK FOR REQUIREMENTS LINKED TO THIS SECTION
            if section_id in reqs_by_section:
                section_reqs = reqs_by_section[section_id]
                if section_reqs:
                     lines.append('\n> **Extracted Requirements for this Section (Displayed Inline):**')
                     for req in section_reqs:
                         # Truncate text for readability if too long
                         rtext = req[2]
                         if len(rtext) > 100: rtext = rtext[:100] + "..."
                         lines.append(f'> - **[{req[1]}]** {rtext} (Conf: {req[3]})')
                         
                         # Check for Lean4 Proof
                         req_id = req[1] # This is internal ID? No wait, req[1] returned by SELECT is `id` (the UUID one)
                         if req_id in proofs_map:
                             pmap = proofs_map[req_id]
                             status = pmap[2]
                             code = pmap[1]
                             if code:
                                 lines.append(f'>   - **Lean4 Theorem** ({status}):')
                                 lines.append('>     ```lean4')
                                 # Indent code for blockquote compatibility
                                 for cl in code.splitlines():
                                     lines.append(f'>     {cl}')
                                 lines.append('>     ```')
                             else:
                                 lines.append(f'>   - **Lean4 Theorem** ({status}): (No code generated)')
                     lines.append('')
                     # Clear them so we don't print again for next text block in same section
                     del reqs_by_section[section_id]
                     
        elif obj_type == 'figure':
            lines.append(f'> **Figure Description:** {content.strip()}')
        elif obj_type == 'section':
             lines.append(f'# {content.strip()}')
             
    lines.append('')

output_path.write_text('\n'.join(lines))
print('Done.')
con.close()
