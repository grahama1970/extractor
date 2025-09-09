# Section Enhancer - What It Actually Does

You receive a section JSON that looks like this:

```json
{
    "section_id": 1,
    "uuid": "abc-123", 
    "blocks": [
        {
            "block_type": "SectionHeader",
            "text": "4.1.5.4. BHT (Branch Histoiy Table) submodule",  // OCR error
            "bbox": [100, 200, 500, 250],
            "page": 10
        },
        {
            "block_type": "Table",
            "text": "Signal|IO|Descripti|connexi|Type",  // Split header  
            "bbox": [100, 300, 500, 400],
            "page": 10
        },
        {
            "block_type": "Text",
            "text": "The BHT is implernented as a memoiy...",  // OCR errors
            "bbox": [100, 450, 500, 500], 
            "page": 10
        }
    ]
}
```

## Your Job: Clean It Up!

1. **Fix the broken text** using existing workers:
   - Fix "Histoiy" → "History"
   - Fix "implernented" → "implemented"  
   - Fix "memoiy" → "memory"
   - Fix "Descripti|on" → "Description"

2. **Use these existing tools**:
   ```bash
   # For text cleaning
   python src/extractor/core/processors/text_cleaning.py
   
   # For table fixing
   python src/extractor/core/processors/llm/llm_table.py
   
   # For equations
   python src/extractor/core/processors/llm/llm_equation.py
   
   # For creating section images
   python src/extractor/core/processors/semantic_section_processor.py
   ```

3. **Output a CLEAN section**:
   ```json
   {
       "section_id": 1,
       "uuid": "abc-123",
       "blocks": [
           {
               "block_type": "SectionHeader", 
               "text": "4.1.5.4. BHT (Branch History Table) submodule",  // FIXED!
               "original_text": "4.1.5.4. BHT (Branch Histoiy Table) submodule",
               "bbox": [100, 200, 500, 250],
               "page": 10
           },
           {
               "block_type": "Table",
               "text": "Signal|IO|Description|connection|Type",  // FIXED!
               "original_text": "Signal|IO|Descripti|connexi|Type",
               "bbox": [100, 300, 500, 400],
               "page": 10
           },
           {
               "block_type": "Text",
               "text": "The BHT is implemented as a memory...",  // FIXED!
               "original_text": "The BHT is implernented as a memoiy...",
               "bbox": [100, 450, 500, 500],
               "page": 10
           }
       ],
       "fixes_applied": [
           "Fixed OCR errors in header",
           "Repaired split table headers",
           "Corrected text spelling errors"
       ]
   }
   ```

## That's it!

Stage 8 takes dirty sections and makes them clean. It uses the workers we already have to fix:
- OCR errors
- Split words
- Broken tables
- Bad formatting

No magic, no 30 imaginary workers. Just use what exists to clean the text.